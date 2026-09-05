"""
Demo-Setup: prueft, dass die API laeuft, und registriert die fuer eine
Live-Demo benoetigten drei KQR (ESCO als Hub, satellite und DQR als
Satelliten) ueber POST /kqr/, falls sie nicht bereits in der Registry
vorhanden sind. DQR wird auch bei verbleibenden Validierungsfehlern
registriert (Status bleibt dann 'roh') -- fuer die Demo zaehlt hier
Vollstaendigkeit der Registry, nicht der Status jedes einzelnen KQR.

Voraussetzung: data/formalized/esco_v1_2_ict_ausschnitt.ttl und
data/formalized/dqr.ttl existieren (vgl. scripts/01_esco_formalize.py,
scripts/04_dqr_augment.py). Die API muss noch nicht laufen -- das Skript
wartet mit Retry-Logic darauf (uvicorn app.api.main:app --reload).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

try:  # Windows-Konsolen laufen oft mit cp1252 -- ✓/✗ brauchen UTF-8.
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://localhost:8000"

# (KQR-Id/Name, Quelldatei, is_hub)
KQR_FILES: list[tuple[str, Path, bool]] = [
    ("esco_v1_2_ict_ausschnitt", ROOT / "data" / "formalized" / "esco_v1_2_ict_ausschnitt.ttl", True),
    ("satellite", ROOT / "tests" / "fixtures" / "satellite_kqr.ttl", False),
    ("dqr", ROOT / "data" / "formalized" / "dqr.ttl", False),
]


def wait_for_api(base_url: str, retries: int = 10, delay: float = 2.0) -> bool:
    """Wartet, bis GET /docs erfolgreich antwortet (API-Start kann dauern)."""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(f"{base_url}/docs", timeout=5)
            if resp.status_code == 200:
                print(f"API erreichbar ({base_url}).")
                return True
        except requests.exceptions.RequestException:
            pass
        print(f"API noch nicht erreichbar (Versuch {attempt}/{retries}), warte {delay}s...")
        time.sleep(delay)
    return False


def existing_ids(base_url: str) -> set[str]:
    resp = requests.get(f"{base_url}/kqr/", timeout=30)
    resp.raise_for_status()
    return {kqr["id"] for kqr in resp.json()}


def register(base_url: str, kqr_id: str, path: Path, is_hub: bool) -> None:
    if not path.exists():
        print(f"{kqr_id}: uebersprungen ({path} nicht gefunden).")
        return

    content = path.read_bytes()
    resp = requests.post(
        f"{base_url}/kqr/",
        data={"name": kqr_id, "source_format": "turtle", "is_hub": str(is_hub)},
        files={"file": (path.name, content, "text/turtle")},
        timeout=120,
    )
    resp.raise_for_status()
    kqr = resp.json()
    print(f"{kqr_id}: registriert (id={kqr['id']}, status={kqr['status']})")


def print_summary(base_url: str, kqr_id: str) -> None:
    resp = requests.get(f"{base_url}/kqr/{kqr_id}/status", timeout=30)
    if resp.status_code == 404:
        print(f"{kqr_id}: nicht in Registry gefunden.")
        return
    resp.raise_for_status()
    data = resp.json()
    kqr = data["kqr"]
    errors = data.get("validation_errors", [])

    print(
        f"{kqr_id}: status={kqr['status']} concepts={kqr.get('concept_count')} "
        f"is_hub={kqr['is_hub']} validation_errors={len(errors)}"
    )
    for err in errors[:5]:
        print(f"    - {err}")
    if len(errors) > 5:
        print(f"    ... ({len(errors) - 5} weitere)")


def main() -> None:
    if not wait_for_api(BASE_URL):
        print(f"\n✗ API unter {BASE_URL} nicht erreichbar. Bitte zuerst starten:")
        print("    uvicorn app.api.main:app --reload")
        raise SystemExit(1)

    registered = existing_ids(BASE_URL)
    for kqr_id, path, is_hub in KQR_FILES:
        if kqr_id in registered:
            print(f"{kqr_id}: bereits vorhanden, ueberspringe Registrierung.")
        else:
            register(BASE_URL, kqr_id, path, is_hub)

    print("\n--- Status-Zusammenfassung ---")
    for kqr_id, _, _ in KQR_FILES:
        print_summary(BASE_URL, kqr_id)

    print("\n✓ Setup komplett, ready for demo")


if __name__ == "__main__":
    main()
