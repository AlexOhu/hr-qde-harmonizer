"""
FastAPI-Einstiegspunkt. Bündelt die Routen der fünf Funktionsgruppen
(vgl. Abschnitt 3.8.3):

1. KQR-Verwaltung        -> routes/kqr.py
2. Klassifikation         -> routes/classification.py
3. Ergebnisliste/Mappings -> routes/mappings.py
4. SSSOM-Vorschau         -> routes/mappings.py (Teil der Ergebnisliste)
5. Export                 -> routes/export.py

Zusätzlich (FZ3.3): Integrationsstrategie für disjunkte Konzepte
-> routes/disjoint.py (eigene Seite 3b, kein Teil der fünf Kern-Funktionsgruppen).

Start: uvicorn app.api.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import classification, disjoint, export, kqr, mappings, projects

app = FastAPI(
    title="HR-QDE Harmonizer API",
    description="Prototyp zur Harmonisierung von Kompetenz-, Qualifikations- "
    "und Berufsrahmenwerken (KQR).",
    version="0.1.0",
)

# Das React-Frontend (frontend/, Vite-Dev-Server auf Port 5173) laeuft als
# eigener Origin und spricht diese API direkt per fetch() an. Ohne CORS
# blockt der Browser jede Antwort. Erlaubte Origins sind ueber
# CORS_ALLOW_ORIGINS (.env, kommagetrennt) konfigurierbar; Default deckt
# den Vite-Dev-Server ab. expose_headers ist noetig, damit das Frontend
# den Dateinamen aus Content-Disposition der Export-Downloads lesen kann.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(projects.router, prefix="/projects", tags=["Projektverwaltung"])
app.include_router(kqr.router, prefix="/kqr", tags=["KQR-Verwaltung"])
app.include_router(classification.router, prefix="/classification", tags=["Klassifikation"])
app.include_router(mappings.router, prefix="/mappings", tags=["Ergebnisliste"])
app.include_router(export.router, prefix="/export", tags=["Export"])
app.include_router(disjoint.router, prefix="/disjoint", tags=["disjoint"])


@app.get("/health")
def health() -> dict:
    """Einfacher Health-Check, u.a. für die Statuszeilen in Funktionsgruppe 2."""
    return {"status": "ok"}
