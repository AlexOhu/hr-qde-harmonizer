"""
Registriert die Test-Fixture tests/fixtures/satellite_kqr.ttl als Satelliten-KQR
ueber POST /kqr/ (Funktionsgruppe 1).

Voraussetzung: API laeuft (uvicorn app.api.main:app --reload).
"""

from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]

fixture = (ROOT / "tests" / "fixtures" / "satellite_kqr.ttl").read_text(encoding="utf-8")
files = {"file": ("satellite.ttl", fixture, "text/turtle")}
data = {"name": "satellite", "source_format": "turtle", "is_hub": False}

resp = requests.post("http://localhost:8000/kqr/", files=files, data=data)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.json()}")
