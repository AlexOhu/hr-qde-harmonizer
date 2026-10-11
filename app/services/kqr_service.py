"""
Orchestrierung für Funktionsgruppe 1 (KQR einpflegen und Status verwalten).

Persistenz-Design dieses Ausbaus: KQR-Registry-Metadaten liegen als JSON
unter data/kqr_registry.json, formalisiertes Turtle unter
data/formalized/<kqr_id>.ttl, Rohdaten unter data/raw/<kqr_id>.<ext> —
alles ohne Hard-Requirement auf eine laufende Neo4j-Instanz. Neo4j-
Materialisierung (import_turtle) wird best-effort versucht, ein
nicht erreichbares Neo4j blockiert die Registrierung nicht.

Pipeline-Schritte (formalize.py, embed.py) werden hier orchestriert, kennen
sich aber untereinander nicht (CLAUDE.md-Architekturprinzip).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import numpy as np
from rdflib import Graph

from app.config import settings
from app.graph.neo4j_client import get_driver, import_turtle
from app.models.schemas import KQR, Concept, KQRStatus
from app.pipeline.step1_formalization.formalize import parse_concepts, validate_formalization
from app.pipeline.step2_embedding_prefilter.embed import embed_concepts

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RAW_DIR = DATA_DIR / "raw"
FORMALIZED_DIR = DATA_DIR / "formalized"
REGISTRY_PATH = DATA_DIR / "kqr_registry.json"

# Ausgangsformate, die bereits SKOS-konformes Turtle sind (Tabelle
# "kqr_formate": Direktimport für ESCO/ELM). PDF/XML/CSV erfordern den
# (in diesem Ausbau nicht automatisiert angestoßenen) Formalisierungsschritt.
_DIRECT_IMPORT_FORMATS = {"rdf", "turtle"}

_registry: dict[str, KQR] = {}
_validation_errors: dict[str, list[str]] = {}
_concepts_cache: dict[str, list[Concept]] = {}
_graph_cache: dict[str, Graph] = {}
_embeddings_cache: dict[str, dict[str, np.ndarray]] = {}


class KQRValidationError(ValueError):
    """Strukturfehler eines kuratierten SKOS-Imports.

    Die Route übersetzt diesen Fehler in eine 422-Antwort. Die Details bleiben
    damit beim Upload sichtbar, statt als flüchtiger Zustand eines roh
    registrierten Frameworks gespeichert zu werden.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "kqr"


def _unique_id(base_slug: str) -> str:
    if base_slug not in _registry:
        return base_slug
    suffix = 2
    while f"{base_slug}_{suffix}" in _registry:
        suffix += 1
    return f"{base_slug}_{suffix}"


def _load_registry() -> dict[str, KQR]:
    if not REGISTRY_PATH.exists():
        return {}
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {item["id"]: KQR(**item) for item in data}


def _save_registry() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        json.dumps(
            [kqr.model_dump(mode="json") for kqr in _registry.values()],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _parse_graph(turtle_text: str) -> Graph:
    graph = Graph()
    graph.parse(data=turtle_text, format="turtle")
    return graph


def _normalise_direct_import(content: bytes, source_format: str) -> str:
    """Parst Turtle bzw. RDF/XML und serialisiert es kanonisch als Turtle."""
    format_by_source = {"turtle": "turtle", "rdf": "xml"}
    rdf_format = format_by_source[source_format]
    try:
        source_text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise KQRValidationError(["Die Datei muss UTF-8-kodiert sein: " + str(exc)]) from exc

    graph = Graph()
    try:
        graph.parse(data=source_text, format=rdf_format)
    except Exception as exc:
        format_label = "Turtle" if source_format == "turtle" else "RDF/XML"
        raise KQRValidationError([format_label + " konnte nicht geparst werden: " + str(exc)]) from exc
    return str(graph.serialize(format="turtle"))


def reload_registry() -> None:
    """Lädt die Registry neu von der Platte (primär für Tests nützlich)."""
    global _registry
    _registry = _load_registry()
    _validation_errors.clear()
    _concepts_cache.clear()
    _graph_cache.clear()
    _embeddings_cache.clear()


_registry = _load_registry()


def register_kqr(
    name: str,
    source_format: str,
    filename: str,
    content: bytes,
    is_hub: bool = False,
) -> KQR:
    """
    Nimmt einen neuen KQR entgegen (FA1). Bereits SKOS-konforme Quellen
    (source_format "rdf"/"turtle") werden sofort validiert und geparst;
    andere Formate bleiben im Status ROH, bis der (administrative,
    einmalige) Formalisierungsschritt separat durchgeführt wurde
    (vgl. VH1.3 — kein Gegenstand dieses Ausbaus für PDF/XML).
    """
    kqr_id = _unique_id(_slugify(name))
    ext = Path(filename).suffix or f".{source_format}"

    kqr = KQR(
        id=kqr_id,
        name=name,
        namespace_uri=f"http://hr-qde.org/harmonised/{kqr_id}/",
        source_format=source_format,
        status=KQRStatus.ROH,
        is_hub=is_hub,
    )

    if source_format in _DIRECT_IMPORT_FORMATS:
        turtle_text = _normalise_direct_import(content, source_format)
        errors = validate_formalization(turtle_text, kqr, strict=False)
        if errors:
            raise KQRValidationError(errors)

        RAW_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_DIR / f"{kqr_id}{ext}").write_bytes(content)
        FORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
        (FORMALIZED_DIR / f"{kqr_id}.ttl").write_text(turtle_text, encoding="utf-8")

        concepts = parse_concepts(turtle_text, kqr_id)
        _concepts_cache[kqr_id] = concepts
        _graph_cache[kqr_id] = _parse_graph(turtle_text)

        kqr.status = KQRStatus.FORMALISIERT
        kqr.concept_count = len(concepts)
        _registry[kqr_id] = kqr

        try:
            driver = get_driver(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
            import_turtle(driver, turtle_text)
            driver.close()
        except Exception as exc:  # Neo4j ist optionale Materialisierung, kein Hard-Requirement.
            logger.warning("Neo4j-Materialisierung für '%s' übersprungen: %s", kqr_id, exc)
    else:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_DIR / f"{kqr_id}{ext}").write_bytes(content)

    _registry[kqr_id] = kqr
    _save_registry()
    return kqr


def list_kqr() -> list[KQR]:
    return list(_registry.values())


def get_kqr(kqr_id: str) -> KQR:
    if kqr_id not in _registry:
        raise KeyError(f"KQR '{kqr_id}' nicht gefunden.")
    return _registry[kqr_id]


def get_validation_errors(kqr_id: str) -> list[str]:
    return _validation_errors.get(kqr_id, [])


def get_concepts(kqr_id: str) -> list[Concept]:
    if kqr_id not in _concepts_cache:
        kqr = get_kqr(kqr_id)
        if kqr.status == KQRStatus.ROH:
            raise ValueError(f"KQR '{kqr_id}' ist noch nicht formalisiert.")
        ttl_path = FORMALIZED_DIR / f"{kqr_id}.ttl"
        _concepts_cache[kqr_id] = parse_concepts(ttl_path.read_text(encoding="utf-8"), kqr_id)
    return _concepts_cache[kqr_id]


def get_graph(kqr_id: str) -> Graph:
    if kqr_id not in _graph_cache:
        ttl_path = FORMALIZED_DIR / f"{kqr_id}.ttl"
        _graph_cache[kqr_id] = _parse_graph(ttl_path.read_text(encoding="utf-8"))
    return _graph_cache[kqr_id]


def delete_kqr(kqr_id: str) -> None:
    """
    Loescht einen KQR endgueltig aus der globalen Registry (destruktive
    Gegenoperation zu register_kqr): Registry-Eintrag, formalisiertes
    Turtle, Rohdatei sowie Embeddings-/Graph-/Konzept-Cache werden entfernt.

    Anders als project_service.remove_kqr_from_project() betrifft dies nicht
    nur ein einzelnes Projekt, sondern alle -- deshalb ist die Loeschung
    gesperrt, solange irgendein Projekt kqr_id noch referenziert (ADR-13:
    KQR-Rohdaten sind projektuebergreifend global). Eine Kuratorin muss den
    KQR zuerst aus jedem betroffenen Projekt entfernen.
    """
    get_kqr(kqr_id)  # KeyError, wenn unbekannt

    # Lokaler Import: project_service importiert seinerseits kqr_service
    # innerhalb von Funktionen (_migrate_legacy_data, get_pipeline_status);
    # ein Modulimport auf oberster Ebene waere hier zirkulaer.
    from app.services import project_service

    referencing = [
        project.name for project in project_service.list_projects() if kqr_id in project.kqr_ids
    ]
    if referencing:
        raise ValueError(
            f"KQR '{kqr_id}' wird noch von folgenden Projekten referenziert: "
            f"{', '.join(referencing)}. Zuerst dort entfernen."
        )

    _registry.pop(kqr_id, None)
    _validation_errors.pop(kqr_id, None)
    _concepts_cache.pop(kqr_id, None)
    _graph_cache.pop(kqr_id, None)
    _embeddings_cache.pop(kqr_id, None)
    _save_registry()

    formalized_path = FORMALIZED_DIR / f"{kqr_id}.ttl"
    if formalized_path.exists():
        formalized_path.unlink()

    if RAW_DIR.exists():
        for raw_file in RAW_DIR.glob(f"{kqr_id}.*"):
            raw_file.unlink()


def get_embeddings(kqr_id: str) -> dict[str, np.ndarray]:
    """Berechnet (bzw. liefert gecacht) die Embeddings eines KQR und hebt den
    Status bei Erfolg auf 'bereit' (Voraussetzung für die Klassifikation,
    vgl. Action Constraint in Funktionsgruppe 1)."""
    if kqr_id not in _embeddings_cache:
        concepts = get_concepts(kqr_id)
        _embeddings_cache[kqr_id] = embed_concepts(concepts, settings.embedding_model)

        kqr = get_kqr(kqr_id)
        if kqr.status == KQRStatus.FORMALISIERT:
            kqr.status = KQRStatus.BEREIT
            _save_registry()

    return _embeddings_cache[kqr_id]
