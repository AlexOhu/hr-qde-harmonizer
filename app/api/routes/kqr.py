"""
Funktionsgruppe 1: KQR einpflegen und Status verwalten (FA1).

Deckt den in Abschnitt 3.8.3 beschriebenen Ablauf ab: Ein KQR durchläuft
die Zustände roh -> formalisiert -> bereit. Eine Weiterleitung zur
Klassifikation (Funktionsgruppe 2) ist erst möglich, wenn mindestens ein
KQR den Status 'bereit' hat (Action Constraint).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.models.schemas import KQR
from app.services import kqr_service

router = APIRouter()
_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "resources" / "kqr-skos-template.ttl"


@router.get("/", response_model=list[KQR])
def list_kqr() -> list[KQR]:
    """Listet alle eingepflegten KQR mit ihrem aktuellen Status."""
    return kqr_service.list_kqr()


@router.get("/template")
def download_skos_template() -> FileResponse:
    """Liefert die kommentierte Vorlage für den kuratierten SKOS-Import."""
    return FileResponse(
        _TEMPLATE_PATH,
        filename="hrqde-kqr-skos-vorlage.ttl",
        media_type="text/turtle; charset=utf-8",
    )


@router.post("/", response_model=KQR)
async def upload_kqr(
    name: str = Form(...),
    source_format: str = Form(...),
    is_hub: bool = Form(False),
    file: UploadFile = File(...),
) -> KQR:
    """
    Nimmt einen kuratierten KQR entgegen. Valide SKOS-Dateien werden als
    ``formalisiert`` registriert; Strukturfehler werden als 422 samt
    konzeptbezogener Fehlerliste zurückgegeben und nicht registriert.
    """
    content = await file.read()
    try:
        return kqr_service.register_kqr(
            name=name,
            source_format=source_format,
            filename=file.filename or name,
            content=content,
            is_hub=is_hub,
        )
    except kqr_service.KQRValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": "Die Datei erfüllt das SKOS-Importschema nicht.", "errors": exc.errors},
        ) from exc


@router.delete("/{kqr_id}", status_code=204)
def delete_kqr(kqr_id: str) -> None:
    """
    Loescht einen KQR endgueltig aus der globalen Registry (destruktiv).
    Gesperrt, solange irgendein Projekt ihn noch referenziert -- eine
    Kuratorin muss ihn zuerst dort entfernen
    (DELETE /projects/{project_id}/kqr/{kqr_id}).
    """
    try:
        kqr_service.delete_kqr(kqr_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{kqr_id}/status")
def get_status(kqr_id: str) -> dict:
    """Statuszeile für Funktionsgruppe 2 (Vorbedingungen vor Klassifikationsstart)."""
    try:
        kqr = kqr_service.get_kqr(kqr_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "kqr": kqr.model_dump(mode="json"),
        "validation_errors": kqr_service.get_validation_errors(kqr_id),
    }


@router.post("/{kqr_id}/embed", response_model=KQR)
def trigger_embedding(kqr_id: str) -> KQR:
    """
    Berechnet Embeddings für einen KQR mit Status 'formalisiert' und setzt
    den Status bei Erfolg auf 'bereit'. Ermöglicht die Statuskorrektur ohne
    erneutes Hochladen der Datei (Funktionsgruppe 1, UCSD: Visibility of
    System State).
    """
    try:
        kqr = kqr_service.get_kqr(kqr_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if kqr.status.value == "roh":
        raise HTTPException(
            status_code=409,
            detail=(
                f"KQR '{kqr_id}' hat Status 'roh'. Bitte laden Sie zuerst "
                "eine valide Turtle-Datei hoch."
            ),
        )

    try:
        kqr_service.get_embeddings(kqr_id)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Embedding-Berechnung für '{kqr_id}' fehlgeschlagen: {exc}",
        ) from exc

    return kqr_service.get_kqr(kqr_id)
