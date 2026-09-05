"""
Funktionsgruppe 5: Export.

Drei Exportoptionen (Abschnitt 3.8.3):
1. Harmonisierte Ontologie im OWL-Format
2. Vollständige Mapping-Tabelle als SSSOM-TSV
3. Prüfbericht mit offenen manuellen Entscheidungen (Accountability-Prinzip)

Ein Gatekeeping-Mechanismus soll den Export bei ungelösten Konflikten
(UNRESOLVED-Einträgen) explizit hervorheben, nicht stillschweigend
ausblenden — vgl. "Zusammenfassungsanzeige der offenen Einträge oberhalb
der Export-Schaltflächen" im Wireframe (Abb. 3.7).

Ontologie-Export (OWL/Turtle/JSON-LD) und Prüfbericht setzen auf der in
FZ2.3 abgeleiteten Kernstruktur (HDBSCAN-Clustering/DAG, siehe
ontology_service) auf; ohne vorheriges Clustering ist der Export blockiert
(HTTP 409 — Zustandsproblem, kein dauerhaft unimplementierter Endpunkt).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import settings
from app.models.schemas import ClusterResult
from app.pipeline.step4_export.ontology_export import export_audit_report, export_ontology
from app.pipeline.step4_export.sssom_writer import write_sssom_tsv
from app.services import disjoint_service, mapping_service, ontology_service, project_service

router = APIRouter()

_FORMAT_EXTENSIONS = {"turtle": "ttl", "xml": "rdf", "json-ld": "jsonld"}
_FORMAT_MEDIA_TYPES = {
    "turtle": "text/turtle",
    "xml": "application/rdf+xml",
    "json-ld": "application/ld+json",
}


def _sssom_dir(project_id: str) -> Path:
    return project_service.get_project_data_dir(project_id) / "sssom"


def _ontology_dir(project_id: str) -> Path:
    return project_service.get_project_data_dir(project_id) / "ontology"


def _audit_dir(project_id: str) -> Path:
    return project_service.get_project_data_dir(project_id) / "audit"


@router.get("/summary")
def export_summary(project_id: str = Query(default="default")) -> dict:
    """
    Gatekeeping-Zahlen vor den Export-Buttons: offene Einträge
    (no_consensus_pairs/related_pairs/low_confidence_mappings/disjunkt) plus
    die Coverage-Bilanz.

    Die Coverage-Quote weist vier Felder aus statt nur eine Zahl:
    coverage_resolved (finalisierte HubMappings), coverage_total (Nenner,
    K ∪ C_conf, ausdrücklich inklusive offener Reviews), coverage_ratio und
    open_review_count. Fielen offene Paare aus dem Nenner, meldete ein
    Projekt mit sieben entschiedenen und drei offenen Paaren eine Quote von
    1,0 statt 0,7.
    """
    summary = mapping_service.get_open_review_summary(project_id=project_id)
    coverage = mapping_service.get_coverage_summary(project_id=project_id)
    disjoint_summary = disjoint_service.get_summary(project_id=project_id)
    return {**summary, **coverage, "disjoint_open": disjoint_summary["open"]}


@router.get("/clusters", response_model=list[ClusterResult])
def get_clusters(project_id: str = Query(default="default")) -> list[ClusterResult]:
    """Zeigt den Status des zuletzt ausgeführten Clustering-Laufs (Seite 5,
    Statusanzeige vor dem Ontologie-Export)."""
    return ontology_service.get_cluster_results(project_id=project_id)


@router.post("/clusters/run", response_model=list[ClusterResult])
def run_clusters(kqr_ids: str, project_id: str = Query(default="default")) -> list[ClusterResult]:
    """
    Startet Schritt 2c (HDBSCAN-Clustering, FZ2.3) für die angegebenen KQR.
    kqr_ids: kommagetrennte Liste von KQR-IDs.
    """
    ids = [kqr_id.strip() for kqr_id in kqr_ids.split(",") if kqr_id.strip()]
    if not ids:
        raise HTTPException(status_code=422, detail="kqr_ids darf nicht leer sein.")
    try:
        return ontology_service.run_clustering(ids, project_id=project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/ontology")
def export_ontology_endpoint(fmt: str = "turtle", project_id: str = Query(default="default")) -> FileResponse:
    """
    Exportiert die harmonisierte Ontologie (turtle | xml | json-ld).

    Setzt auf der in FZ2.3 abgeleiteten Kernstruktur (HDBSCAN-Clustering/DAG)
    auf — wurde noch kein Clustering-Lauf ausgeführt, ist der Export blockiert.
    """
    clusters = ontology_service.get_harmonised_clusters(project_id=project_id)
    if not clusters:
        raise HTTPException(
            status_code=409,
            detail="Clustering noch nicht ausgeführt, POST /export/clusters/run zuerst.",
        )

    if fmt not in _FORMAT_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"Unbekanntes Format '{fmt}'.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = _ontology_dir(project_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"ontology_{timestamp}.{_FORMAT_EXTENSIONS[fmt]}"

    mappings = mapping_service.list_mappings(project_id=project_id)
    disjoint_decisions = disjoint_service.list_decisions(project_id=project_id)
    export_ontology(mappings, clusters, disjoint_decisions, fmt, output_path)

    return FileResponse(
        path=output_path, filename=output_path.name, media_type=_FORMAT_MEDIA_TYPES[fmt]
    )


@router.post("/sssom")
def export_sssom_endpoint(project_id: str = Query(default="default")) -> FileResponse:
    """Exportiert die vollständige Mapping-Tabelle eines Projekts als SSSOM-TSV."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = _sssom_dir(project_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"export_{timestamp}.tsv"

    mappings = mapping_service.list_mappings(project_id=project_id)
    write_sssom_tsv(mappings, output_path, settings.mapping_confidence_threshold)

    return FileResponse(
        path=output_path, filename=output_path.name, media_type="text/tab-separated-values"
    )


@router.post("/audit-report")
def export_audit_report_endpoint(project_id: str = Query(default="default")) -> FileResponse:
    """Exportiert den Prüfbericht mit offenen manuellen Entscheidungen eines Projekts."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = _audit_dir(project_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"audit_{timestamp}.md"

    mappings = mapping_service.list_mappings(project_id=project_id)
    unresolved = mapping_service.get_unresolved_mappings(project_id=project_id)
    export_audit_report(mappings, unresolved, output_path)

    return FileResponse(path=output_path, filename=output_path.name, media_type="text/markdown")
