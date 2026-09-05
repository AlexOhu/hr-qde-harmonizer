"""
Einmalige Migration bestehender Projektdaten auf das Datenmodell v0.2.

HINWEIS: Dieser Lauf ist abgeschlossen und historisch. Das hier erzeugte Feld
``source_relation`` wurde inzwischen wieder entfernt; ein aktueller
Datenbestand wird von ``scripts/20_migrate_relationtype_to_predicate.py`` auf
das MappingPredicate-Vokabular gebracht. Nicht erneut ausführen.

Drei Umstellungen in einem Lauf, weil sie dieselben Dateien anfassen:

1. mappings.json: match_type -> mapping_justification (SEMAPV-CURIE).
   struct/lex -> semapv:StructuralMatching, llm/lex+llm/llm+struct ->
   semapv:LLMBasedMatching. Ein Record mit mapping_source="manual" bekommt
   unabhaengig vom alten match_type semapv:MappingReview, weil das Verfahren
   dort die menschliche Entscheidung war, nicht der urspruengliche Algorithmus.

2. mappings.json: review_status und source_relation ergaenzen. Bereits
   persistierte Mappings sind ausnahmslos Mitglieder der konjunkten Menge K
   (RELATED/UNRESOLVED wurden vor v0.2 verworfen) und bekommen daher
   review_status="conjunct".

3. mappings.json: Backfill der fehlenden RELATED/UNRESOLVED-Faelle aus
   classification_results.json. Genau diese Faelle waren vor v0.2 nicht
   persistiert, hatten keine mapping_id und waren ueber /mappings/ nicht
   erreichbar -- der offene Punkt, den dieser Ausbau schliesst.

4. disjoint_decisions.json: Strategienamen auf das Vokabular v0.2 umstellen
   (standalone_class -> own_class, anchor_to_root -> attach_to_skeleton,
   excluded -> out_of_scope).

Der Lauf ist idempotent: bereits migrierte Dateien bleiben unveraendert.
Von jeder geaenderten Datei wird vorher eine .bak-Kopie mit Zeitstempel
angelegt.

Aufruf:
    python scripts/16_migrate_match_type_to_justification.py           # Probelauf
    python scripts/16_migrate_match_type_to_justification.py --apply   # schreibt
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.schemas import (  # noqa: E402
    LEGACY_DISJOINT_STRATEGY,
    LEGACY_MATCH_TYPE_JUSTIFICATION,
    MappingJustification,
    RelationType,
)

logger = logging.getLogger("migrate_v0_2")

PROJECTS_DIR = Path(__file__).resolve().parents[1] / "data" / "projects"

# Vor v0.2 landeten RELATED/UNRESOLVED nicht in mappings.json. "UNRESOLVED"
# ist heute kein RelationType-Wert mehr, hier als historisches Literal.
_OPEN_RELATIONS = {RelationType.RELATED.value, "UNRESOLVED"}


def _justification_for(record: dict) -> str:
    if record.get("mapping_source") == "manual":
        return MappingJustification.MAPPING_REVIEW.value
    legacy = str(record.get("match_type", ""))
    return LEGACY_MATCH_TYPE_JUSTIFICATION.get(
        legacy, MappingJustification.LLM_BASED_MATCHING
    ).value


def _relation_from_predicate(predicate_id: str) -> str | None:
    """Umkehrung von RelationType.to_skos_predicate() fuer die eindeutigen
    Faelle. skos:relatedMatch bleibt offen -- vor v0.2 konnte ein K-Mapping
    dieses Praedikat nicht tragen, der Fall tritt also nicht auf."""
    return {
        "skos:exactMatch": RelationType.EQUIVALENT.value,
        "skos:broadMatch": RelationType.A_SUBSUMES_B.value,
        "skos:narrowMatch": RelationType.B_SUBSUMES_A.value,
    }.get(predicate_id)


def _migrate_mapping_record(record: dict) -> bool:
    """Aktualisiert einen Record in-place. True, wenn sich etwas geaendert hat."""
    changed = False
    if "match_type" in record:
        record["mapping_justification"] = _justification_for(record)
        del record["match_type"]
        changed = True
    if "review_status" not in record:
        record["review_status"] = "conjunct"
        changed = True
    if "source_relation" not in record:
        record["source_relation"] = _relation_from_predicate(record.get("predicate_id", ""))
        changed = True
    if "context_loss_note" not in record:
        record["context_loss_note"] = None
        changed = True
    return changed


def _backfill_open_reviews(mappings: list[dict], results: list[dict]) -> list[dict]:
    """Erzeugt Mapping-Records fuer RELATED/UNRESOLVED-Ergebnisse, die vor
    v0.2 nur als ClassificationResult existierten. Labels stammen aus den
    bereits persistierten Mappings, soweit dort vorhanden; sonst tritt die URI
    an ihre Stelle, damit der Backfill nicht an einer abgemeldeten KQR-Datei
    scheitert."""
    from uuid import uuid4

    known_pairs = {(m["subject_id"], m["object_id"]) for m in mappings}
    label_by_uri: dict[str, str] = {}
    kqr_by_uri: dict[str, str | None] = {}
    for m in mappings:
        label_by_uri.setdefault(m["subject_id"], m["subject_label"])
        label_by_uri.setdefault(m["object_id"], m["object_label"])
        kqr_by_uri.setdefault(m["subject_id"], m.get("subject_kqr_id"))
        kqr_by_uri.setdefault(m["object_id"], m.get("object_kqr_id"))

    created: list[dict] = []
    for result in results:
        relation = result.get("final_relation")
        if relation not in _OPEN_RELATIONS:
            continue
        subject_id = result["pair"]["concept_a"]
        object_id = result["pair"]["concept_b"]
        if (subject_id, object_id) in known_pairs:
            continue
        majority = next(
            (r["reasoning"] for r in result.get("runs", []) if r.get("relation") == relation),
            "",
        )
        created.append({
            "mapping_id": str(uuid4()),
            "subject_id": subject_id,
            "subject_label": label_by_uri.get(subject_id, subject_id),
            "subject_kqr_id": kqr_by_uri.get(subject_id),
            "object_id": object_id,
            "object_label": label_by_uri.get(object_id, object_id),
            "object_kqr_id": kqr_by_uri.get(object_id),
            "predicate_id": "skos:relatedMatch",
            "mapping_confidence": result.get("mapping_confidence", 0.0),
            "mapping_tool": "HR-QDE-Harmonizer-v0.1",
            "mapping_justification": MappingJustification.LLM_BASED_MATCHING.value,
            "mapping_source": "algorithmic",
            "author": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "justification": majority,
            "review_status": "open",
            "source_relation": relation,
            "context_loss_note": None,
        })
        known_pairs.add((subject_id, object_id))
    return created


def _migrate_decision_record(record: dict) -> bool:
    changed = False
    legacy = LEGACY_DISJOINT_STRATEGY.get(str(record.get("strategy")))
    if legacy is not None:
        record["strategy"] = legacy.value
        changed = True
    if "context_loss_note" not in record:
        record["context_loss_note"] = None
        changed = True
    return changed


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _write(path: Path, data: list[dict], apply: bool) -> None:
    if not apply:
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    shutil.copy2(path, path.with_suffix(f".json.bak.{stamp}"))
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def migrate_project(project_dir: Path, apply: bool) -> dict[str, int]:
    counts = {"justification": 0, "status": 0, "backfilled": 0, "strategies": 0}

    mappings_path = project_dir / "mappings.json"
    if mappings_path.exists():
        mappings = _load(mappings_path)
        for record in mappings:
            if "match_type" in record:
                counts["justification"] += 1
            if _migrate_mapping_record(record):
                counts["status"] += 1
        backfilled = _backfill_open_reviews(
            mappings, _load(project_dir / "classification_results.json")
        )
        counts["backfilled"] = len(backfilled)
        if counts["status"] or backfilled:
            _write(mappings_path, mappings + backfilled, apply)

    decisions_path = project_dir / "disjoint_decisions.json"
    if decisions_path.exists():
        decisions = _load(decisions_path)
        counts["strategies"] = sum(1 for record in decisions if _migrate_decision_record(record))
        if counts["strategies"]:
            _write(decisions_path, decisions, apply)

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="Änderungen schreiben (sonst nur Probelauf)"
    )
    parser.add_argument("--projects-dir", type=Path, default=PROJECTS_DIR)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not args.projects_dir.exists():
        logger.info("Kein Projektverzeichnis unter %s -- nichts zu migrieren.", args.projects_dir)
        return

    total = {"justification": 0, "status": 0, "backfilled": 0, "strategies": 0}
    for project_dir in sorted(p for p in args.projects_dir.iterdir() if p.is_dir()):
        counts = migrate_project(project_dir, args.apply)
        if any(counts.values()):
            logger.info(
                "%s: %d x match_type -> mapping_justification, %d Records ergaenzt, "
                "%d offene Reviews nachgetragen, %d Strategien umbenannt",
                project_dir.name,
                counts["justification"],
                counts["status"],
                counts["backfilled"],
                counts["strategies"],
            )
        for key in total:
            total[key] += counts[key]

    mode = "geschrieben" if args.apply else "PROBELAUF, nichts geschrieben"
    logger.info(
        "Gesamt (%s): %d x match_type migriert, %d Records ergaenzt, "
        "%d offene Reviews nachgetragen, %d Strategien umbenannt.",
        mode,
        total["justification"],
        total["status"],
        total["backfilled"],
        total["strategies"],
    )


if __name__ == "__main__":
    main()
