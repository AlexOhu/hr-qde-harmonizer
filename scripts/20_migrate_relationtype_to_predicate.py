"""
Einmalige Migration bestehender Projektdaten: RelationType/source_relation
raus, MappingPredicate rein.

Hintergrund: Das persistierte und über die API ausgetauschte Vokabular ist
jetzt ausschließlich MappingPredicate (die SKOS-CURIEs). RelationType ist
klassifikationsschritt-intern und kennt UNRESOLVED nicht mehr; ein fehlender
Mehrheitsentscheid ist final_relation=None bzw. predicate_id=None. Das
Schattenfeld source_relation entfällt.

Zwei Dateien pro Projekt:

1. mappings.json
   - source_relation wird aus jedem Record entfernt.
   - War source_relation == "UNRESOLVED" UND review_status == "open", dann
     bekommt der Record predicate_id = null (offenes Paar ohne
     Mehrheitsentscheid, das erst im Review ein Prädikat erhält). Ein offenes
     RELATED-Ergebnis behält skos:relatedMatch.

2. classification_results.json
   - final_relation == "UNRESOLVED" wird zu null.

Der Lauf ist idempotent: bereits migrierte Dateien bleiben unverändert. Von
jeder geänderten Datei wird vorher eine .bak-Kopie mit Zeitstempel angelegt.
Der Model-Validator in app/models/schemas.py akzeptiert den alten Aufbau
weiterhin beim Laden, damit Snapshots und Forks ohne diesen Lauf ladbar
bleiben; die Migration bringt nur den Datenbestand auf der Platte in Form.

Aufruf:
    python scripts/20_migrate_relationtype_to_predicate.py           # Probelauf
    python scripts/20_migrate_relationtype_to_predicate.py --apply   # schreibt
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

logger = logging.getLogger("migrate_relationtype_to_predicate")

PROJECTS_DIR = Path(__file__).resolve().parents[1] / "data" / "projects"

_NO_CONSENSUS_TOKENS = {"UNRESOLVED", "unresolved"}


def _migrate_mapping_record(record: dict) -> bool:
    """Aktualisiert einen Record in-place. True, wenn sich etwas geändert hat."""
    if "source_relation" not in record:
        return False
    legacy = record.pop("source_relation")
    if legacy in _NO_CONSENSUS_TOKENS and record.get("review_status") == "open":
        record["predicate_id"] = None
    return True


def _migrate_result_record(record: dict) -> bool:
    """final_relation == "UNRESOLVED" -> None."""
    if record.get("final_relation") in _NO_CONSENSUS_TOKENS:
        record["final_relation"] = None
        return True
    return False


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _write(path: Path, data: list[dict], apply: bool) -> None:
    if not apply:
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    shutil.copy2(path, path.with_suffix(f".json.bak.{stamp}"))
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def migrate_project(project_dir: Path, apply: bool) -> dict[str, int]:
    counts = {"mappings": 0, "no_consensus": 0, "results": 0}

    mappings_path = project_dir / "mappings.json"
    if mappings_path.exists():
        mappings = _load(mappings_path)
        for record in mappings:
            had_none = record.get("source_relation") in _NO_CONSENSUS_TOKENS
            if _migrate_mapping_record(record):
                counts["mappings"] += 1
                if had_none and record.get("review_status") == "open":
                    counts["no_consensus"] += 1
        if counts["mappings"]:
            _write(mappings_path, mappings, apply)

    results_path = project_dir / "classification_results.json"
    if results_path.exists():
        results = _load(results_path)
        counts["results"] = sum(1 for record in results if _migrate_result_record(record))
        if counts["results"]:
            _write(results_path, results, apply)

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

    total = {"mappings": 0, "no_consensus": 0, "results": 0}
    for project_dir in sorted(p for p in args.projects_dir.iterdir() if p.is_dir()):
        counts = migrate_project(project_dir, args.apply)
        if any(counts.values()):
            logger.info(
                "%s: %d Mappings ohne source_relation, davon %d -> predicate_id=null, "
                "%d ClassificationResults final_relation=null",
                project_dir.name,
                counts["mappings"],
                counts["no_consensus"],
                counts["results"],
            )
        for key in total:
            total[key] += counts[key]

    mode = "geschrieben" if args.apply else "PROBELAUF, nichts geschrieben"
    logger.info(
        "Gesamt (%s): %d Mappings migriert, %d als 'kein Konsens' (predicate_id=null), "
        "%d ClassificationResults.",
        mode,
        total["mappings"],
        total["no_consensus"],
        total["results"],
    )


if __name__ == "__main__":
    main()
