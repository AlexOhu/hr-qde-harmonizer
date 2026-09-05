"""
Funktionsgruppe 2: Klassifikationsprozess steuern.

Liefert Fortschrittsinformationen (Schrittanzahl, Prozent, geschätzte
Restzeit) für die UI, um die "Gulf of Evaluation" (Norman) zu adressieren
(vgl. Abschnitt 3.8.3). Vorbedingungen (Neo4j-Verbindung, LLM-Endpunkt)
werden vor Start explizit geprüft und zurückgegeben.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services import classification_service

router = APIRouter()


class PairResetRequest(BaseModel):
    """Nutzlast fuer POST /classification/pair/reset. justification und
    author sind Pflichtfelder (Accountability-Prinzip, vgl.
    MappingReviewRequest in mappings.py)."""

    justification: str
    author: str


@router.post("/start")
def start_classification(
    kqr_a_id: str, kqr_b_id: str, project_id: str = Query(default="default")
) -> dict:
    """
    Startet Schritt 2 (Embedding & Vorfilter) gefolgt von Schritt 3
    (LLM-Klassifikation) für zwei ausgewählte KQR als Hintergrundjob
    innerhalb eines Projekts.
    """
    try:
        job_id = classification_service.start_classification_job(
            kqr_a_id, kqr_b_id, project_id=project_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"job_id": job_id}


@router.get("/")
def list_classification_jobs(project_id: str = Query(default="default")) -> list[dict]:
    """Alle bekannten Klassifikationsjobs eines Projekts mit Fortschritt --
    mehrere Jobs können parallel laufen (je ein eigener Hintergrund-Thread),
    daher zeigt dies nicht nur den zuletzt gestarteten (vgl.
    Transparency-Prinzip, Abschnitt 3.8.3)."""
    return classification_service.list_jobs(project_id=project_id)


@router.get("/{job_id}/progress")
def get_progress(job_id: str, project_id: str = Query(default="default")) -> dict:
    """Fortschritt eines laufenden Klassifikationsjobs (Prozent, aktueller Schritt)."""
    try:
        return classification_service.get_job_progress(job_id, project_id=project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{job_id}/pause")
def pause_classification(job_id: str, project_id: str = Query(default="default")) -> dict:
    """Pausiert einen laufenden Job (Mixed-Initiative: gezielter Stopp vor
    dem nächsten teuren LLM-Aufruf, kein Datenverlust dank inkrementeller
    Persistenz in mapping_service)."""
    try:
        return classification_service.pause_job(job_id, project_id=project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{job_id}/resume")
def resume_classification(job_id: str, project_id: str = Query(default="default")) -> dict:
    """Setzt einen pausierten Job fort."""
    try:
        return classification_service.resume_job(job_id, project_id=project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/preconditions")
def check_preconditions() -> dict:
    """Prüft Neo4j-Verbindung und LLM-Endpunkt-Erreichbarkeit vor Prozessstart."""
    return classification_service.check_preconditions()


@router.post("/pair/reset")
def reset_pair(
    kqr_a_id: str,
    kqr_b_id: str,
    payload: PairResetRequest,
    project_id: str = Query(default="default"),
) -> dict:
    """
    Setzt ein KQR-Paar vollstaendig zurueck: entfernt alle Mappings und die
    zugrunde liegenden Klassifikationsergebnisse dieses Paares, damit ein
    erneuter POST /classification/start das Paar komplett neu klassifiziert
    statt bereits erledigte Paare zu ueberspringen. Anders als "Erneut
    versuchen" (Resume eines gescheiterten/unterbrochenen Laufs) ist dies
    eine bewusst destruktive Aktion und erfordert deshalb Begruendung und
    Autor.
    """
    try:
        return classification_service.reset_pair(
            kqr_a_id, kqr_b_id, payload.justification, payload.author, project_id=project_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/pair/reset-events")
def list_pair_reset_events(project_id: str = Query(default="default")) -> list[dict]:
    """Protokollierte Paar-Resets eines Projekts, neueste zuerst
    (Transparency-Prinzip: sichtbar machen, dass und warum ein Paar
    zurueckgesetzt wurde)."""
    return classification_service.list_reset_events(project_id=project_id)
