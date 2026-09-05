"""
FZ3.3: Integrationsstrategie für disjunkte Konzepte (D1 ∪ D2).

Mixed-Initiative-UI (Seite 3b): das System schlägt eine Strategie vor
(suggest), der Benutzer entscheidet verbindlich (decide) inkl. Begründung
und Autor (Accountability-Prinzip, FA4).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.schemas import Concept, DisjointConceptDecision
from app.services import disjoint_service, project_service

from ._input_validation import parse_disjoint_strategy, require_context_loss_note

router = APIRouter()


class DisjointDecisionRequest(BaseModel):
    """Formular-Nutzlast für die Integrationsentscheidung (UC-FZ3.3, FA4)."""

    # strategy kommt als Freitext an und wird in der Route geprüft, damit ein
    # unzulässiger Wert (insbesondere "pending") HTTP 400 statt 422 ergibt --
    # dieselbe Regel wie in PUT /mappings/{id}/review.
    strategy: str
    justification: str
    author: str
    anchor_class: str | None = None  # bei attach_to_skeleton: Skelett-Zielklasse
    context_loss_note: str | None = None  # Pflicht bei map_to_nearest


@router.get("/concepts", response_model=list[Concept])
def list_disjoint_concepts(
    kqr_id: str | None = None,
    kqr_a_id: str | None = None,
    kqr_b_id: str | None = None,
    project_id: str = Query(default="default"),
) -> list[Concept]:
    """
    Alle disjunkten Konzepte eines Projekts, optional gefiltert auf ein KQR.
    Sind kqr_a_id UND kqr_b_id gesetzt, wird stattdessen die paarbezogene
    Berechnung verwendet (nur Mappings dieses einen Paares als Grundmenge,
    siehe disjoint_service.list_disjoint_concepts_for_pair) statt der
    projektweiten Matched-Menge; kqr_id wird in diesem Fall ignoriert.
    """
    if kqr_a_id is not None and kqr_b_id is not None:
        return disjoint_service.list_disjoint_concepts_for_pair(kqr_a_id, kqr_b_id, project_id=project_id)
    return disjoint_service.list_disjoint_concepts(kqr_id=kqr_id, project_id=project_id)


@router.get("/concepts/{concept_id:path}/suggest")
def suggest_strategy(concept_id: str, project_id: str = Query(default="default")) -> dict:
    """Heuristischer Strategievorschlag (Mixed Initiative), keine Bindung."""
    try:
        concept = disjoint_service.find_concept(concept_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "concept_id": concept_id,
        "suggested_strategy": disjoint_service.suggest_strategy(concept, project_id=project_id),
    }


@router.get("/{concept_id:path}/suggest-reuse", response_model=DisjointConceptDecision | None)
def suggest_reuse(
    concept_id: str, project_id: str = Query(default="default")
) -> DisjointConceptDecision | None:
    """Bietet eine bereits in einem anderen Projekt getroffene
    Integrationsentscheidung fuer concept_id zur Wiederverwendung an, sofern
    sie gegen mindestens dieselbe KQR-Vergleichsmenge getroffen wurde wie die
    aktuell im Projekt vorliegende (context_kqr_ids ist Obermenge der
    aktuellen project.kqr_ids). null, wenn nichts passt. Reine
    Lese-Operation: die Uebernahme bleibt ein separater POST
    .../decide-Aufruf mit eigener Begruendung (Accountability-Prinzip)."""
    try:
        current_kqr_ids = project_service.get_project(project_id).kqr_ids
    except KeyError:
        current_kqr_ids = []
    return disjoint_service.suggest_reusable_decision(concept_id, current_kqr_ids)


@router.post("/concepts/{concept_id:path}/decide", response_model=DisjointConceptDecision)
def decide(
    concept_id: str, payload: DisjointDecisionRequest, project_id: str = Query(default="default")
) -> DisjointConceptDecision:
    """Persistiert die Integrationsentscheidung für ein disjunktes Konzept."""
    strategy = parse_disjoint_strategy(payload.strategy)
    require_context_loss_note(strategy, payload.context_loss_note)
    if not payload.justification.strip():
        raise HTTPException(status_code=422, detail="Begründung ist Pflichtfeld (FA4).")
    try:
        return disjoint_service.decide(
            concept_id=concept_id,
            strategy=strategy,
            justification=payload.justification,
            author=payload.author,
            anchor_class=payload.anchor_class,
            context_loss_note=payload.context_loss_note,
            project_id=project_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        # project_service.ensure_writable(): Projekt ist ein schreibgeschuetzter
        # Snapshot (ADR-06). Ohne diesen Zweig quittierte die Route das mit 500,
        # obwohl es ein Zustandskonflikt ist -- analog zu classification.start.
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/decisions", response_model=list[DisjointConceptDecision])
def list_decisions(project_id: str = Query(default="default")) -> list[DisjointConceptDecision]:
    return disjoint_service.list_decisions(project_id=project_id)


@router.get("/summary")
def summary(
    kqr_a_id: str | None = None,
    kqr_b_id: str | None = None,
    project_id: str = Query(default="default"),
) -> dict:
    """Projektweite Zusammenfassung, oder -- wenn kqr_a_id UND kqr_b_id
    gesetzt sind -- die paarbezogene Zusammenfassung für genau dieses
    KQR-Paar (siehe disjoint_service.get_summary_for_pair)."""
    if kqr_a_id is not None and kqr_b_id is not None:
        return disjoint_service.get_summary_for_pair(kqr_a_id, kqr_b_id, project_id=project_id)
    return disjoint_service.get_summary(project_id=project_id)
