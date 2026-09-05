"""
Pflegt die in Schritt 1 formalisierten KQR-Entwuerfe (data/formalized/
*_draft.ttl) ueber die laufende API ein (POST /kqr/), analog zum
Direktimport-Pfad in Tabelle "kqr_formate". register_kqr validiert
rdf/turtle-Uploads dabei selbst noch einmal -- ein Entwurf mit
verbleibenden Fehlern bleibt im Status 'roh', statt die Registrierung
abzulehnen.

Voraussetzung: API laeuft (uvicorn app.api.main:app --reload).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
FORMALIZED_DIR = ROOT / "data" / "formalized"

# (Dateiname in data/formalized/, KQR-Name, is_hub)
KQR_FILES: list[tuple[str, str, bool]] = [
    ("esco_ict_draft.ttl", "ESCO v1.2 (ICT-Ausschnitt)", True),
    ("ecf_draft.ttl", "e-CF 3.0", False),
]


def register(base_url: str, filename: str, name: str, is_hub: bool, existing_names: set[str]) -> None:
    if name in existing_names:
        print(f"{name}: uebersprungen (bereits in der Registry vorhanden).")
        return

    path = FORMALIZED_DIR / filename
    if not path.exists():
        print(f"{name}: uebersprungen ({filename} nicht gefunden -- erst 01_/03_*.py ausfuehren).")
        return

    content = path.read_bytes()
    response = httpx.post(
        f"{base_url}/kqr/",
        data={"name": name, "source_format": "turtle", "is_hub": str(is_hub)},
        files={"file": (filename, content, "text/turtle")},
        timeout=120,
    )
    response.raise_for_status()
    kqr = response.json()
    print(f"{name}: id={kqr['id']} status={kqr['status']} concepts={kqr.get('concept_count')}")

    if kqr["status"] == "roh":
        status_resp = httpx.get(f"{base_url}/kqr/{kqr['id']}/status", timeout=30)
        errors = status_resp.json().get("validation_errors", [])
        print(f"  Status blieb 'roh' -- {len(errors)} Validierungsfehler:")
        for err in errors[:10]:
            print(f"    - {err}")
        if len(errors) > 10:
            print(f"    ... ({len(errors) - 10} weitere)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API-Basis-URL")
    args = parser.parse_args()

    existing = httpx.get(f"{args.base_url}/kqr/", timeout=30).json()
    existing_names = {kqr["name"] for kqr in existing}

    for filename, name, is_hub in KQR_FILES:
        register(args.base_url, filename, name, is_hub, existing_names)


if __name__ == "__main__":
    main()
