"""
Registriert e-CF und DQR (Satelliten-KQR) ueber die laufende API (POST
/kqr/) und wartet je KQR aktiv auf Status 'bereit' (GET /kqr/{id}/status),
analog zum Ablauf in scripts/05_register_all.py -- hier jedoch mit
Polling, falls die Embedding-Berechnung (Abschnitt "Vektorindex") den
Status nicht synchron mit der Registrierungs-Antwort anhebt.

Voraussetzung: API laeuft (uvicorn app.api.main:app --reload).
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
FORMALIZED_DIR = ROOT / "data" / "formalized"

POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 120

# (Dateiname in data/formalized/, KQR-Name, is_hub)
KQR_FILES: list[tuple[str, str, bool]] = [
    ("ecf_draft.ttl", "ecf", False),
    ("dqr_translated.ttl", "dqr", False),
]


def register(base_url: str, filename: str, name: str, is_hub: bool) -> dict:
    path = FORMALIZED_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"{name}: {filename} nicht gefunden.")

    content = path.read_bytes()
    response = httpx.post(
        f"{base_url}/kqr/",
        data={"name": name, "source_format": "turtle", "is_hub": str(is_hub)},
        files={"file": (filename, content, "text/turtle")},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def wait_until_bereit(base_url: str, kqr_id: str, name: str) -> dict:
    """Pollt GET /kqr/{id}/status bis Status 'bereit' erreicht ist oder
    POLL_TIMEOUT_S ueberschritten wird."""
    deadline = time.monotonic() + POLL_TIMEOUT_S
    status_kqr: dict = {}

    while True:
        status_resp = httpx.get(f"{base_url}/kqr/{kqr_id}/status", timeout=30)
        status_resp.raise_for_status()
        status_data = status_resp.json()
        status_kqr = status_data["kqr"]

        if status_kqr["status"] == "bereit":
            return status_kqr

        if time.monotonic() >= deadline:
            errors = status_data.get("validation_errors", [])
            print(f"  Timeout nach {POLL_TIMEOUT_S}s -- letzter Status: {status_kqr['status']}")
            for err in errors[:10]:
                print(f"    - {err}")
            return status_kqr

        time.sleep(POLL_INTERVAL_S)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API-Basis-URL")
    args = parser.parse_args()

    summaries: list[str] = []
    for filename, name, is_hub in KQR_FILES:
        kqr = register(args.base_url, filename, name, is_hub)
        print(f"{name}: id={kqr['id']} status={kqr['status']} concepts={kqr.get('concept_count')}")

        final = wait_until_bereit(args.base_url, kqr["id"], name)
        summaries.append(f"{name}: {final.get('concept_count')} Konzepte, status={final['status']}")

    print()
    for line in summaries:
        print(line)


if __name__ == "__main__":
    main()
