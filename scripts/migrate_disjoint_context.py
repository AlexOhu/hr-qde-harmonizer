"""
Einmalige Migration: context_kqr_ids in bestehende disjoint_decisions.json
nachtragen.

Hintergrund: DisjointConceptDecision hat seit dem Ausbau ein Feld
context_kqr_ids -- die KQR-Kombination, gegen die ein disjunktes Konzept zum
Entscheidungszeitpunkt geprueft wurde. Bereits persistierte Datensaetze
tragen dieses Feld noch nicht. suggest_reusable_decision() schlaegt einen
Datensatz mit leerem context_kqr_ids bewusst NICHT zur Wiederverwendung vor,
weil seine Vergleichsmenge unbekannt ist. Diese Migration fuellt das Feld,
damit vorhandene Entscheidungen wieder nutzbar werden.

WICHTIG -- NAEHERUNG, KEINE EXAKTE REKONSTRUKTION:
Als context_kqr_ids wird der AKTUELLE Stand von project.kqr_ids eingetragen.
Das ist nicht zwingend die KQR-Kombination, die zum tatsaechlichen
Entscheidungszeitpunkt aktiv war (ein KQR kann seither hinzugefuegt oder
entfernt worden sein). Die Migration nimmt an, dass der aktuelle Projekt-
zuschnitt dem Entscheidungszeitpunkt hinreichend nahe kommt. Wo das nicht
zutrifft, muss die Entscheidung manuell neu getroffen werden.

Nur Datensaetze OHNE context_kqr_ids (bzw. mit leerer Liste) werden
angefasst. Der Lauf ist damit idempotent. Von jeder geaenderten Datei wird
vorher eine .bak-Kopie mit Zeitstempel angelegt (Muster wie im Projekt
etabliert: disjoint_decisions.json.bak.<ISO-Zeitstempel>).

Aufruf:
    python scripts/migrate_disjoint_context.py           # Probelauf (zeigt Beispiel-Diffs)
    python scripts/migrate_disjoint_context.py --apply    # schreibt
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

logger = logging.getLogger("migrate_disjoint_context")

PROJECTS_DIR = Path(__file__).resolve().parents[1] / "data" / "projects"

_APPROX_NOTE = (
    "!!! context_kqr_ids = AKTUELLER Stand von project.kqr_ids, NICHT der "
    "historische Stand zum Entscheidungszeitpunkt. Das ist eine NAEHERUNG, "
    "keine exakte Rekonstruktion."
)


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _needs_migration(record: dict) -> bool:
    return not record.get("context_kqr_ids")


def _sample_diff(record: dict, context_kqr_ids: list[str]) -> str:
    before = json.dumps(record, indent=2, ensure_ascii=False)
    after = json.dumps(
        {**record, "context_kqr_ids": context_kqr_ids}, indent=2, ensure_ascii=False
    )
    return "\n".join(["--- vorher", before, "+++ nachher", after])


def _write(path: Path, data: list[dict]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_suffix(f".json.bak.{stamp}")
    shutil.copy2(path, backup)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return backup


def migrate_project(project_dir: Path, apply: bool) -> dict:
    """Migriert ein einzelnes Projektverzeichnis. Gibt eine Kennzahl-Struktur
    zurueck; schreibt nur bei apply=True."""
    decisions_path = project_dir / "disjoint_decisions.json"
    project_path = project_dir / "project.json"

    decisions = _load(decisions_path)
    if not decisions:
        return {"project": project_dir.name, "total": 0, "migrated": 0, "skipped": 0}

    if not project_path.exists():
        logger.warning(
            "%s: disjoint_decisions.json vorhanden, aber keine project.json -- "
            "context_kqr_ids kann nicht bestimmt werden, Projekt uebersprungen.",
            project_dir.name,
        )
        return {"project": project_dir.name, "total": len(decisions), "migrated": 0, "skipped": len(decisions)}

    project = json.loads(project_path.read_text(encoding="utf-8"))
    context_kqr_ids = sorted(project.get("kqr_ids", []))

    to_migrate = [d for d in decisions if _needs_migration(d)]
    already = len(decisions) - len(to_migrate)

    logger.info("")
    logger.info("=== Projekt %s ===", project_dir.name)
    logger.info("project.kqr_ids (aktuell, sortiert): %s", context_kqr_ids)
    logger.info(
        "%d Entscheidungen gesamt, %d ohne context_kqr_ids, %d bereits gesetzt.",
        len(decisions),
        len(to_migrate),
        already,
    )

    for sample in to_migrate[:2]:
        logger.info(
            "\nBeispiel-Diff (concept_id=%s):\n%s",
            sample.get("concept_id"),
            _sample_diff(sample, context_kqr_ids),
        )

    if to_migrate:
        logger.info("\n%s", _APPROX_NOTE)

    if apply and to_migrate:
        for record in to_migrate:
            record["context_kqr_ids"] = context_kqr_ids
        backup = _write(decisions_path, decisions)
        logger.info("Geschrieben. Backup: %s", backup.name)

    return {
        "project": project_dir.name,
        "total": len(decisions),
        "migrated": len(to_migrate),
        "skipped": already,
    }


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

    results = []
    for project_dir in sorted(p for p in args.projects_dir.iterdir() if p.is_dir()):
        results.append(migrate_project(project_dir, args.apply))

    mode = "GESCHRIEBEN" if args.apply else "PROBELAUF -- nichts geschrieben"
    total_migrated = sum(r["migrated"] for r in results)
    logger.info("")
    logger.info("------------------------------------------------------------")
    for r in results:
        if r["total"]:
            logger.info(
                "%-55s total=%4d  migriert=%4d  bereits=%4d",
                r["project"],
                r["total"],
                r["migrated"],
                r["skipped"],
            )
    logger.info("------------------------------------------------------------")
    logger.info("Gesamt (%s): %d Datensaetze zu migrieren.", mode, total_migrated)
    logger.info("")
    logger.info("%s", _APPROX_NOTE)


if __name__ == "__main__":
    main()
