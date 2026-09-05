"""
Eingabeprüfung für Enum-Felder, die als Freitext ankommen.

Warum nicht direkt Pydantic-Enums in den Request-Modellen: FastAPI beantwortet
eine Enum-Verletzung mit HTTP 422. Für die Entscheidungsvokabulare aus FZ3.2
ist aber HTTP 400 gefordert, insbesondere für den Wert "pending" -- der kein
unzulässiger Wert im Sinne eines Tippfehlers ist, sondern das ausdrückliche
Fehlen einer Entscheidung und damit nichts, was gespeichert werden dürfte.

Beide Funktionen werden von /mappings/{id}/review und
/disjoint/concepts/{id}/decide gemeinsam genutzt, damit dasselbe Vokabular
nicht an zwei Stellen mit abweichenden Fehlermeldungen geprüft wird.
"""

from __future__ import annotations

from fastapi import HTTPException

from app.models.schemas import DisjointStrategy, MappingPredicate

_PENDING_HINT = (
    "'pending' ist kein entscheidbarer Wert, sondern das Fehlen einer Entscheidung."
)


def parse_review_predicate(value: str | None) -> MappingPredicate:
    """SKOS-Prädikat des Konjunkt-Zweigs. HTTP 400 bei fehlendem oder
    unzulässigem Wert."""
    if value is None:
        raise HTTPException(
            status_code=400, detail="predicate ist im Konjunkt-Zweig ein Pflichtfeld."
        )
    try:
        return MappingPredicate(value)
    except ValueError as exc:
        allowed = ", ".join(p.value for p in MappingPredicate)
        detail = f"Unzulässiges predicate '{value}' (erlaubt: {allowed})."
        if value == "pending":
            detail = f"{detail} {_PENDING_HINT}"
        raise HTTPException(status_code=400, detail=detail) from exc


def parse_disjoint_strategy(value: str | None) -> DisjointStrategy:
    """Integrationsstrategie des Disjunkt-Zweigs. HTTP 400 bei fehlendem oder
    unzulässigem Wert. Strategienamen vor v0.2 (standalone_class,
    anchor_to_root, excluded) bleiben über DisjointStrategy._missing_()
    gültig und werden auf die aktuellen Werte abgebildet."""
    if value is None:
        raise HTTPException(
            status_code=400, detail="strategy ist im Disjunkt-Zweig ein Pflichtfeld."
        )
    try:
        return DisjointStrategy(value)
    except ValueError as exc:
        allowed = ", ".join(s.value for s in DisjointStrategy)
        detail = f"Unzulässige strategy '{value}' (erlaubt: {allowed})."
        if value == "pending":
            detail = f"{detail} {_PENDING_HINT}"
        raise HTTPException(status_code=400, detail=detail) from exc


def require_context_loss_note(strategy: DisjointStrategy, note: str | None) -> None:
    """MAP_TO_NEAREST ohne Kontextverlust-Vermerk ist unzulässig (HTTP 400):
    das Anhängen an das nächstgelegene Konzept verliert Bedeutung, und dieser
    Verlust muss dokumentiert sein, statt in der Ontologie unsichtbar zu
    bleiben (Accountability-Prinzip)."""
    if strategy == DisjointStrategy.MAP_TO_NEAREST and not (note or "").strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "context_loss_note ist bei strategy='map_to_nearest' ein Pflichtfeld: "
                "der Kontextverlust beim Anhängen an das nächstgelegene Konzept ist zu vermerken."
            ),
        )
