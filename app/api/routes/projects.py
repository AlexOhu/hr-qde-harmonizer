"""
Projektverwaltung: kapselt KQR-Auswahl und alle daraus resultierenden
Artefakte (Mappings, Entscheidungen, Clustering) pro Projekt (ADR-13).

Snapshot (ADR-13): ein eingefrorenes, schreibgeschütztes Projekt --
erscheint als eigener Eintrag in der Projektliste und dokumentiert einen
Zwischenstand, ohne das Ursprungsprojekt zu verändern.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.schemas import Project, ProjectPipelineStatus, ProjectStatus
from app.services import project_service

router = APIRouter()


class ProjectCreateRequest(BaseModel):
    name: str
    kqr_ids: list[str]
    description: str | None = None
    hub_kqr_id: str | None = None
    kqr_scopes: dict[str, str] | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class SnapshotRequest(BaseModel):
    version_label: str


class ForkRequest(BaseModel):
    new_name: str
    new_kqr_ids: list[str]


class KqrRemovalRequest(BaseModel):
    """Nutzlast fuer DELETE /projects/{project_id}/kqr/{kqr_id}. author ist
    Pflichtfeld (Accountability-Prinzip, analog PairResetRequest);
    justification ueberschreibt bei Bedarf die automatisch generierte
    Systembegruendung der betroffenen Paar-Resets (vgl.
    project_service.remove_kqr_from_project)."""

    author: str
    justification: str | None = None


@router.get("/", response_model=list[Project])
def list_projects() -> list[Project]:
    """Alle Projekte, absteigend nach updated_at."""
    return project_service.list_projects()


@router.post("/", response_model=Project, status_code=201)
def create_project(payload: ProjectCreateRequest) -> Project:
    return project_service.create_project(
        name=payload.name,
        kqr_ids=payload.kqr_ids,
        description=payload.description,
        hub_kqr_id=payload.hub_kqr_id,
        kqr_scopes=payload.kqr_scopes,
    )


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str) -> Project:
    try:
        return project_service.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{project_id}", response_model=Project)
def update_project(project_id: str, payload: ProjectUpdateRequest) -> Project:
    try:
        return project_service.update_project(
            project_id, name=payload.name, description=payload.description
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{project_id}/pipeline-status", response_model=ProjectPipelineStatus)
def get_pipeline_status(project_id: str) -> ProjectPipelineStatus:
    try:
        return project_service.get_pipeline_status(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{project_id}/kqr/{kqr_id}")
def remove_kqr_from_project(project_id: str, kqr_id: str, payload: KqrRemovalRequest) -> dict:
    """
    Entfernt einen KQR projekt-scoped (Funktionsgruppe 1). Guenstig und
    reversibel: der KQR bleibt in der globalen Registry, nur dieses Projekt
    verliert die Referenz. Setzt dabei alle betroffenen Paare zurueck (vgl.
    project_service.remove_kqr_from_project).
    """
    try:
        return project_service.remove_kqr_from_project(
            project_id, kqr_id, author=payload.author, justification=payload.justification
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/snapshot", response_model=Project)
def create_snapshot(project_id: str, payload: SnapshotRequest) -> Project:
    try:
        return project_service.create_snapshot(project_id, payload.version_label)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{project_id}/fork", response_model=Project)
def fork_project(project_id: str, payload: ForkRequest) -> Project:
    try:
        return project_service.fork_project(project_id, payload.new_name, payload.new_kqr_ids)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str) -> None:
    try:
        target = project_service.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if target.status == ProjectStatus.ACTIVE:
        remaining_active = [
            p for p in project_service.list_projects() if p.status == ProjectStatus.ACTIVE and p.project_id != project_id
        ]
        if not remaining_active:
            raise HTTPException(
                status_code=409, detail="Das letzte aktive Projekt kann nicht gelöscht werden."
            )

    project_service.delete_project(project_id)
