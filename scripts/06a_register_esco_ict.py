"""
Registriert den ICT-gefilterten ESCO-Datensatz (data/raw/esco-v1.2.1-ict-filtered.ttl)
als Hub-KQR ueber POST /kqr/ (Funktionsgruppe 1).

Voraussetzung: API laeuft (uvicorn app.api.main:app --reload).
"""

from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]

esco_ttl = (ROOT / "data" / "raw" / "esco-v1.2.1-ict-filtered.ttl").read_text(encoding="utf-8")
files = {"file": ("esco-ict.ttl", esco_ttl, "text/turtle")}
data = {"name": "esco-ict", "source_format": "turtle", "is_hub": True}

resp = requests.post("http://localhost:8000/kqr/", files=files, data=data)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.json()}")
