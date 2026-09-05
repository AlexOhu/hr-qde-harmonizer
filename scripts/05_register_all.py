"""
Registriert die drei finalen KQR-Entwuerfe (ESCO als Hub, e-CF und DQR als
Satelliten) ueber die laufende API (POST /kqr/) und prueft anschliessend je
KQR den Status via GET /kqr/{kqr_id}/status -- analog zum Ablauf in
scripts/04_register_kqrs.py, hier jedoch fuer den kompletten Satz an
KQR, der fuer die Klassifikation (Funktionsgruppe 2) benoetigt wird.

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
    ("esco.ttl", "ESCO v1.2.1 (ICT-filtered)", True),
    ("ecf_draft.ttl", "e-CF 3.0", False),
    ("dqr.ttl", "DQR 2013", False),
]


def register(base_url: str, filename: str, name: str, is_hub: bool) -> dict | None:
    path = FORMALIZED_DIR / filename
    if not path.exists():
        print(f"{name}: uebersprungen ({filename} nicht gefunden).")
        return None

    content = path.read_bytes()
    response = httpx.post(
        f"{base_url}/kqr/",
        data={"name": name, "source_format": "turtle", "is_hub": str(is_hub)},
        files={"file": (filename, content, "text/turtle")},
        timeout=120,
    )
    response.raise_for_status()
    kqr = response.json()

    status_resp = httpx.get(f"{base_url}/kqr/{kqr['id']}/status", timeout=30)
    status_resp.raise_for_status()
    status_data = status_resp.json()
    status_kqr = status_data["kqr"]
    errors = status_data.get("validation_errors", [])

    print(
        f"{name}: status={status_kqr['status']} "
        f"concepts={status_kqr.get('concept_count')} "
        f"validation_errors={len(errors)}"
    )
    for err in errors[:10]:
        print(f"    - {err}")
    if len(errors) > 10:
        print(f"    ... ({len(errors) - 10} weitere)")

    return status_kqr


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000", help="API-Basis-URL")
    args = parser.parse_args()

    registered = 0
    ready = 0
    for filename, name, is_hub in KQR_FILES:
        kqr = register(args.base_url, filename, name, is_hub)
        if kqr is not None:
            registered += 1
            if kqr["status"] == "bereit":
                ready += 1

    print(f"\n{registered} KQR registriert, {ready} bereit fuer Klassifikation")


if __name__ == "__main__":
    main()
