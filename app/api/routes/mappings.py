"""
Funktionsgruppe 3: Ergebnisliste der erzeugten Mappings, mit Filterfunktion
für Status='Manuell' bzw. niedrige Konfidenz (Mixed-Initiative-Prinzip, FA2/FA3).

Seit v0.2 enthält die Ergebnisliste auch die noch offenen RELATED/UNRESOLVED-
Paare (ReviewStatus.OPEN). Sie sind über PUT /mappings/{mapping_id}/review
entscheidbar, das die Weiche konjunkt/disjunkt aus FZ3.2 abbildet.

Funktionsgruppe 4: SSSOM-Vorschau der strukturierten Metadaten
(Transparency-Prinzip).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.models.schemas import Mapping, ReviewStatus
from app.services import mapping_service

from ._input_validation import (
    parse_disjoint_strategy,
    parse_review_predicate,
    require_context_loss_note,
)

router = APIRouter()


class MappingUpdateRequest(BaseModel):
    """Formular-Nutzlast für die manuelle Mapping-Entscheidung (UC3, FA3/FA4).

    predicate ist ein MappingPredicate-CURIE (skos:exactMatch, skos:closeMatch,
    skos:broadMatch, skos:narrowMatch, skos:relatedMatch).
    """

    predicate: str
    justification: str
    author: str


class MappingReviewRequest(BaseModel):
    """
    Nutzlast der Konjunkt/Disjunkt-Weiche (FZ3.2).

    Bewusst keine Pydantic-Enums für predicate/strategy: eine
    Enum-Verletzung beantwortet FastAPI mit HTTP 422, gefordert ist für
    unzulässige Werte (insbesondere "pending") aber HTTP 400. Die Prüfung
    passiert deshalb in app/api/routes/_input_validation.py.
    """

    decision: str  # "conjunct" | "disjunct"
    predicate: str | None = None  # nur im Konjunkt-Zweig
    confidence: float = 1.0
    strategy: str | None = None  # nur im Disjunkt-Zweig
    context_loss_note: str | None = None  # Pflicht bei strategy="map_to_nearest"
    justification: str | None = None
    author: str | None = None


@router.get("/config")
def get_config() -> dict:
    """
    Liefert die serverseitige Konfidenz-Schwelle (VH1.7), damit UI-Seiten
    Status-Anzeigen ('automatisch akzeptiert' vs. 'manuelle Entscheidung
    erforderlich') konsistent zu list_mappings(only_manual_review=True)
    berechnen, statt den Schwellenwert lokal zu duplizieren.
    """
    return {"mapping_confidence_threshold": settings.mapping_confidence_threshold}


@router.get("/", response_model=list[Mapping])
def list_mappings(
    only_manual_review: bool = False,
    min_confidence: float | None = None,
    kqr_id: str | None = None,
    kqr_a_id: str | None = None,
    kqr_b_id: str | None = None,
    review_status: ReviewStatus | None = None,
    project_id: str = Query(default="default"),
) -> list[Mapping]:
    """
    Liefert die Ergebnisliste eines Projekts, einschließlich der noch offenen
    Paare (RELATED oder ohne LLM-Mehrheitsentscheid). Jeder Eintrag trägt
    review_status (open | conjunct | disjunct); bei offenen Paaren
    unterscheidet predicate_id (skos:relatedMatch bzw. None) die beiden Fälle,
    damit die Oberfläche "wartet auf manuelle Entscheidung" ausweisen kann,
    statt solche Einträge auszublenden.

    only_manual_review grenzt auf Einträge ein, die eine Entscheidung
    erfordern (offener Review oder Konfidenz unterhalb des Schwellenwerts).
    kqr_id grenzt auf ein beteiligtes KQR ein. Sind kqr_a_id UND kqr_b_id
    gesetzt, grenzt das stattdessen paarbezogen auf genau dieses KQR-Paar ein
    (kqr_id bleibt für Rückwärtskompatibilität als Einzel-KQR-Filter erhalten).
    """
    return mapping_service.list_mappings(
        only_manual_review=only_manual_review,
        min_confidence=min_confidence,
        kqr_id=kqr_id,
        kqr_a_id=kqr_a_id,
        kqr_b_id=kqr_b_id,
        review_status=review_status,
        project_id=project_id,
    )


@router.put("/{mapping_id}/review", response_model=Mapping)
def review_mapping(
    mapping_id: str, payload: MappingReviewRequest, project_id: str = Query(default="default")
) -> Mapping:
    """
    Entscheidet ein offenes Kandidatenpaar (FZ3.2).

    Konjunkt: das Paar wird mit dem gewählten SKOS-Prädikat finalisiert,
    mapping_justification=semapv:MappingReview, Konfidenz standardmäßig 1.0.

    Disjunkt: das Subjektkonzept erhält eine Integrationsstrategie und damit
    den Typ harm:HarmonisedConcept. strategy='map_to_nearest' verlangt einen
    context_loss_note und widmet das geprüfte Paar zu einem
    skos:relatedMatch-Mapping um.
    """
    predicate = strategy = None
    if payload.decision == "conjunct":
        predicate = parse_review_predicate(payload.predicate)
    elif payload.decision == "disjunct":
        strategy = parse_disjoint_strategy(payload.strategy)
        require_context_loss_note(strategy, payload.context_loss_note)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unbekannte decision '{payload.decision}' (erlaubt: conjunct, disjunct).",
        )

    try:
        return mapping_service.review_mapping(
            mapping_id,
            decision=payload.decision,
            predicate=predicate,
            confidence=payload.confidence,
            strategy=strategy,
            context_loss_note=payload.context_loss_note,
            justification=payload.justification,
            author=payload.author,
            project_id=project_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{mapping_id}", response_model=Mapping)
def update_mapping(
    mapping_id: str, payload: MappingUpdateRequest, project_id: str = Query(default="default")
) -> Mapping:
    """
    Manuelle Mapping-Entscheidung anlegen/korrigieren (FA3), inkl.
    verpflichtender Provenance-Angaben (FA4: Begründung, Zeitstempel, Autor).
    """
    if not payload.justification.strip():
        raise HTTPException(status_code=422, detail="Begründung ist Pflichtfeld (FA4).")
    try:
        return mapping_service.update_mapping(
            mapping_id, payload.predicate, payload.justification, payload.author, project_id=project_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/sssom-preview")
def sssom_preview(limit: int = 5, project_id: str = Query(default="default")) -> dict:
    """
    Zeigt eine strukturierte Vorschau der SSSOM-Metadaten und eines
    exemplarischen Mapping-Eintrags (Funktionsgruppe 4, Transparency-Prinzip).
    """
    return mapping_service.sssom_preview(limit=limit, project_id=project_id)
