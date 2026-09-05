"""
Backfill fuer subject_kqr_id/object_kqr_id auf bereits persistierten Mappings
(data/mappings.json), die vor Einfuehrung dieser Felder erzeugt wurden.

Herkunfts-KQR laesst sich nicht zuverlaessig aus der Konzept-URI allein
ableiten: mehrere Registry-Eintraege (z.B. e_cf_3_0, e_cf_3_0_2, e_cf_3_0_3,
ecf) wurden im Laufe der Arbeit mit identischen Konzept-URIs mehrfach
registriert (wiederholte Testlaeufe). Eindeutig ist nur, welche KQR-Paare
tatsaechlich klassifiziert wurden -- das steht in data/classification_jobs.json
(kqr_a_id/kqr_b_id je Job). Nur aus diesen tatsaechlich verwendeten KQR wird
daher die URI->kqr_id-Lookup-Tabelle gebaut; taucht eine URI in mehreren
davon auf (echter Konflikt statt blosser Doppel-Registrierung), bleibt das
Feld unbefuellt und wird als Konflikt gemeldet statt geraten.

Nicht Teil der Klassifikationslogik selbst (Schritt 2/3) -- reines
Migrations-Skript fuer bereits existierende Daten, daher hier und nicht in
app/services/.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import kqr_service  # noqa: E402

DATA_DIR = ROOT / "data"
MAPPINGS_PATH = DATA_DIR / "mappings.json"
JOBS_PATH = DATA_DIR / "classification_jobs.json"


def _job_kqr_ids() -> set[str]:
    """KQR-IDs, die in mindestens einem tatsaechlich gestarteten
    Klassifikationsjob als kqr_a_id oder kqr_b_id auftauchen -- unabhaengig
    vom Job-Status (auch 'interrupted'/'failed' persistieren bereits
    Mappings ueber add_mappings())."""
    if not JOBS_PATH.exists():
        return set()
    jobs = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    ids: set[str] = set()
    for job in jobs.values():
        ids.add(job["kqr_a_id"])
        ids.add(job["kqr_b_id"])
    return ids


def _build_uri_lookup(kqr_ids: set[str]) -> tuple[dict[str, str], dict[str, set[str]]]:
    """uri -> kqr_id fuer eindeutige URIs, plus uri -> {kqr_ids} fuer
    Konfliktfaelle (dieselbe URI unter mehreren tatsaechlich verwendeten
    KQR-IDs), die bewusst nicht aufgeloest werden."""
    candidates: dict[str, set[str]] = defaultdict(set)
    for kqr_id in sorted(kqr_ids):
        try:
            concepts = kqr_service.get_concepts(kqr_id)
        except (KeyError, ValueError, FileNotFoundError) as exc:
            print(f"  Ueberspringe '{kqr_id}': {exc}")
            continue
        for concept in concepts:
            candidates[concept.uri].add(kqr_id)

    lookup: dict[str, str] = {}
    conflicts: dict[str, set[str]] = {}
    for uri, ids in candidates.items():
        if len(ids) == 1:
            lookup[uri] = next(iter(ids))
        else:
            conflicts[uri] = ids
    return lookup, conflicts


def main() -> None:
    if not MAPPINGS_PATH.exists():
        raise SystemExit(f"Keine Mappings gefunden unter {MAPPINGS_PATH}.")

    kqr_ids = _job_kqr_ids()
    if not kqr_ids:
        raise SystemExit(f"Keine Klassifikationsjobs gefunden unter {JOBS_PATH} -- nichts zu tun.")
    print(f"KQR-IDs aus Klassifikationsjobs: {sorted(kqr_ids)}")

    lookup, conflicts = _build_uri_lookup(kqr_ids)
    print(f"{len(lookup)} eindeutige Konzept-URIs, {len(conflicts)} Konfliktfaelle.")

    mappings = json.loads(MAPPINGS_PATH.read_text(encoding="utf-8"))

    updated = 0
    already_set = 0
    unresolved: set[str] = set()
    unresolved_conflict: set[str] = set()

    for mapping in mappings:
        changed = False
        for side in ("subject", "object"):
            field = f"{side}_kqr_id"
            uri = mapping[f"{side}_id"]

            if mapping.get(field):
                already_set += 1
                continue
            if uri in lookup:
                mapping[field] = lookup[uri]
                changed = True
            elif uri in conflicts:
                unresolved_conflict.add(uri)
            else:
                unresolved.add(uri)
        if changed:
            updated += 1

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = MAPPINGS_PATH.with_suffix(f".json.bak.{timestamp}")
    shutil.copy2(MAPPINGS_PATH, backup_path)
    print(f"Backup geschrieben nach {backup_path}")

    MAPPINGS_PATH.write_text(json.dumps(mappings, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{updated} von {len(mappings)} Mappings aktualisiert.")
    print(f"{already_set} Feld(er) waren bereits befuellt (uebersprungen).")
    if unresolved_conflict:
        print(f"{len(unresolved_conflict)} URIs mit Konflikt (mehrdeutig, nicht befuellt), z.B.:")
        for uri in list(unresolved_conflict)[:5]:
            print(f"  - {uri} -> {sorted(conflicts[uri])}")
    if unresolved:
        print(f"{len(unresolved)} URIs ohne Treffer (kein bekanntes KQR), z.B.:")
        for uri in list(unresolved)[:5]:
            print(f"  - {uri}")


if __name__ == "__main__":
    main()
