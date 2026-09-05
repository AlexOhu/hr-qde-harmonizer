"""
Verwaltet Projekte als eigenständige Datencontainer.

Persistenz-Design:
- Projektmetadaten in data/projects/{project_id}/project.json
- Projektspezifische Laufzeitdaten im selben Verzeichnis:
    classification_jobs.json, mappings.json, classification_results.json,
    disjoint_decisions.json, clusters.json, clusters_dag.json, sssom/, ontology/
- Globale KQR-Daten (kqr_registry.json, formalized/, raw/, Embeddings)
  bleiben unverändert unter data/ — sie werden zwischen Projekten geteilt
  (ADR-01).

Namenskonvention: project_id ist ein slugifizierter Name + Zeitstempel-Suffix,
z.B. "esco_ecf_dqr_20260730T142233Z".
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.models.schemas import KQRPairStatus, Project, ProjectPipelineStatus, ProjectStatus

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Datendateien/-verzeichnisse, die pro Projekt gehalten werden (vgl. ADR-02).
_LEGACY_FILES = (
    "mappings.json",
    "classification_results.json",
    "classification_jobs.json",
    "disjoint_decisions.json",
    "clusters.json",
    "clusters_dag.json",
)
_LEGACY_DIRS = ("sssom", "ontology")


def _projects_dir() -> Path:
    """Wird bei jedem Aufruf aus DATA_DIR neu berechnet, damit Tests
    project_service.DATA_DIR monkeypatchen können (analog kqr_service)."""
    return DATA_DIR / "projects"


def _project_dir(project_id: str) -> Path:
    return _projects_dir() / project_id


def get_project_data_dir(project_id: str) -> Path:
    """Gibt data/projects/{project_id}/ zurück. Hilfsfunktion für andere Services."""
    return _project_dir(project_id)


def _project_path(project_id: str) -> Path:
    return _project_dir(project_id) / "project.json"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "projekt"


def _new_project_id(name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{_slugify(name)}_{timestamp}"


def _read_project(path: Path) -> Project:
    return Project(**json.loads(path.read_text(encoding="utf-8")))


def _write_project(project: Project) -> None:
    project_dir = _project_dir(project.project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    _project_path(project.project_id).write_text(
        json.dumps(project.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def create_project(
    name: str,
    kqr_ids: list[str],
    description: str | None = None,
    hub_kqr_id: str | None = None,
    kqr_scopes: dict[str, str] | None = None,
) -> Project:
    """Erstellt ein neues Projekt und legt das Verzeichnis an.

    kqr_scopes: optionale Scope-Konfiguration je KQR fuer den Vorfilter
    (prefilter.filter_by_scope): kqr_id -> "all" | "container_only" |
    "leaf_only" | "level_only". Fehlt ein Eintrag, gilt "all".
    """
    project_id = _new_project_id(name)
    project = Project(
        project_id=project_id,
        name=name,
        description=description,
        kqr_ids=kqr_ids,
        kqr_scopes=kqr_scopes or {},
        hub_kqr_id=hub_kqr_id,
    )
    _write_project(project)
    return project


def list_projects() -> list[Project]:
    """Alle Projekte, absteigend nach updated_at sortiert."""
    projects_dir = _projects_dir()
    if not projects_dir.exists():
        return []
    projects: list[Project] = []
    for entry in projects_dir.iterdir():
        project_file = entry / "project.json"
        if project_file.exists():
            projects.append(_read_project(project_file))
    return sorted(projects, key=lambda p: p.updated_at, reverse=True)


def get_project(project_id: str) -> Project:
    """KeyError wenn nicht gefunden."""
    path = _project_path(project_id)
    if not path.exists():
        raise KeyError(f"Projekt '{project_id}' nicht gefunden.")
    return _read_project(path)


def update_project(
    project_id: str, name: str | None = None, description: str | None = None
) -> Project:
    """Aktualisiert Name/Beschreibung; updated_at wird gesetzt."""
    project = get_project(project_id)
    update: dict = {"updated_at": datetime.utcnow()}
    if name is not None:
        update["name"] = name
    if description is not None:
        update["description"] = description
    updated = project.model_copy(update=update)
    _write_project(updated)
    return updated


def ensure_writable(project_id: str) -> None:
    """Wirft ValueError, wenn project_id ein bestehendes SNAPSHOT-Projekt
    referenziert (Invariante 2 des Refactoring-Plans). Unbekannte project_id
    (z. B. der rückwärtskompatible Default-Fall ohne project.json) gilt als
    schreibbar."""
    try:
        project = get_project(project_id)
    except KeyError:
        return
    if project.status == ProjectStatus.SNAPSHOT:
        raise ValueError(
            f"Projekt '{project_id}' ist ein Snapshot (schreibgeschützt)."
        )


def remove_kqr_from_project(
    project_id: str, kqr_id: str, author: str, justification: str | None = None
) -> dict:
    """
    Entfernt einen KQR aus einem einzelnen Projekt (ADR-01: KQR-Rohdaten
    sind projektuebergreifend global, Projekte referenzieren nur kqr_ids).
    Anders als kqr_service.delete_kqr() ist dies eine guenstige, reversible
    Operation: der KQR bleibt in der globalen Registry erhalten und kann
    dem Projekt spaeter erneut hinzugefuegt werden.

    Der Hub eines Projekts kann nicht auf diesem Weg entfernt werden: ohne
    Hub wuerde _select_hub_and_satellite() im naechsten Klassifikationslauf
    still in eine andere Richtung umschwenken. Eine Kuratorin muss zuerst
    einen neuen Hub bestimmen.

    Alle Paare dieses Projekts, an denen kqr_id beteiligt ist, werden ueber
    classification_service.reset_pair() zurueckgesetzt (Mappings und
    Klassifikationsergebnisse geloescht), damit kein verwaister Bestand fuer
    ein nicht mehr referenziertes Framework zurueckbleibt -- die bestehende
    Reset-Logik wird dafuer wiederverwendet, nicht dupliziert. Der Reset ist
    selbst protokollpflichtig (Accountability-Prinzip): ohne eigene
    Begruendung erhaelt er eine Systembegruendung.
    """
    ensure_writable(project_id)
    project = get_project(project_id)

    if kqr_id == project.hub_kqr_id:
        raise ValueError(
            f"KQR '{kqr_id}' ist Hub dieses Projekts, zuerst neuen Hub bestimmen."
        )

    # Lokaler Import: classification_service importiert seinerseits
    # project_service auf Modulebene, ein Modulimport in Gegenrichtung waere
    # zirkulaer (gleiches Muster wie get_pipeline_status).
    from app.services import classification_service

    reset_justification = (
        justification.strip()
        if justification and justification.strip()
        else f"KQR '{kqr_id}' aus Projekt entfernt."
    )

    pairs: set[tuple[str, str]] = set()
    for job in classification_service.list_jobs(project_id=project_id):
        kqr_a_id, kqr_b_id = job["kqr_a_id"], job["kqr_b_id"]
        if kqr_id in (kqr_a_id, kqr_b_id):
            pairs.add(tuple(sorted((kqr_a_id, kqr_b_id))))

    for kqr_a_id, kqr_b_id in pairs:
        classification_service.reset_pair(
            kqr_a_id, kqr_b_id, reset_justification, author, project_id=project_id
        )

    updated = project.model_copy(
        update={
            "kqr_ids": [k for k in project.kqr_ids if k != kqr_id],
            "updated_at": datetime.utcnow(),
        }
    )
    _write_project(updated)

    return {"removed_pairs": len(pairs), "was_hub": False}


def create_snapshot(project_id: str, version_label: str) -> Project:
    """
    Kopiert alle projektspezifischen Datendateien in ein neues Projekt-
    verzeichnis (shutil.copytree). Das neue Projekt erhält status=SNAPSHOT
    und parent_project_id=project_id. Das Original bleibt unverändert.
    Artefakte unter sssom/ und ontology/ werden mitkopiert.
    """
    source = get_project(project_id)
    new_id = _new_project_id(f"{source.name}_{version_label}")
    new_dir = _project_dir(new_id)
    shutil.copytree(_project_dir(project_id), new_dir, dirs_exist_ok=True)

    snapshot = source.model_copy(
        update={
            "project_id": new_id,
            "status": ProjectStatus.SNAPSHOT,
            "parent_project_id": project_id,
            "version_label": version_label,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )
    _write_project(snapshot)
    return snapshot


def fork_project(project_id: str, new_name: str, new_kqr_ids: list[str]) -> Project:
    """
    Erstellt ein neues ACTIVE-Projekt mit anderem KQR-Set.
    Keine Daten werden übernommen — leerer Start mit anderen KQRs.
    parent_project_id zeigt auf die Quelle (Dokumentation der Herkunft).
    """
    get_project(project_id)  # KeyError, wenn Quelle nicht existiert
    forked = Project(
        project_id=_new_project_id(new_name),
        name=new_name,
        kqr_ids=new_kqr_ids,
        status=ProjectStatus.ACTIVE,
        parent_project_id=project_id,
    )
    _write_project(forked)
    return forked


def delete_project(project_id: str) -> None:
    """Löscht Projektverzeichnis und Metadaten."""
    project_dir = _project_dir(project_id)
    if not project_dir.exists():
        raise KeyError(f"Projekt '{project_id}' nicht gefunden.")
    shutil.rmtree(project_dir)


def get_pipeline_status(project_id: str) -> ProjectPipelineStatus:
    """
    Aggregiert KQRPairStatus für alle KQR-Paare, die im Projekt klassifiziert
    wurden (aus classification_jobs.json des Projekts), plus Disjoint-
    Zusammenfassung und Clustering-Status. Ruft classification_service,
    mapping_service, disjoint_service und ontology_service mit project_id auf.

    Lokale Imports vermeiden einen Zirkelimport (diese Services importieren
    ihrerseits project_service für die Pfadauflösung).
    """
    from app.services import classification_service, disjoint_service, kqr_service, mapping_service, ontology_service
    from app.models.schemas import ReviewStatus

    project = get_project(project_id)

    jobs = classification_service.list_jobs(project_id=project_id)

    def _kqr_name(kqr_id: str) -> str:
        try:
            return kqr_service.get_kqr(kqr_id).name
        except KeyError:
            return kqr_id

    kqr_pairs: list[KQRPairStatus] = []
    for job in jobs:
        kqr_a_id, kqr_b_id = job["kqr_a_id"], job["kqr_b_id"]
        pair_mappings = mapping_service.list_mappings_for_pair(kqr_a_id, kqr_b_id, project_id=project_id)
        # Offene Fälle ohne LLM-Mehrheitsentscheid (predicate_id=None) sind
        # seit v0.2 selbst Teil von pair_mappings und müssen nicht mehr aus
        # einer zweiten Quelle nachgeschlagen werden.
        pair_unresolved = [
            m
            for m in pair_mappings
            if m.review_status == ReviewStatus.OPEN and m.predicate_id is None
        ]
        # needs_review() ist die gemeinsame Definition mit
        # list_mappings(only_manual_review=True): offener Review ODER
        # Konfidenz unter der Schwelle. Ohne sie zählte die Projektübersicht
        # anders als die Mapping-Liste, die dieselben Fälle anzeigt.
        pending = sum(1 for m in pair_mappings if mapping_service.needs_review(m))
        pair_disjoint = disjoint_service.get_summary_for_pair(kqr_a_id, kqr_b_id, project_id=project_id)
        kqr_pairs.append(
            KQRPairStatus(
                kqr_a_id=kqr_a_id,
                kqr_a_name=_kqr_name(kqr_a_id),
                kqr_b_id=kqr_b_id,
                kqr_b_name=_kqr_name(kqr_b_id),
                job_status=job["status"],
                job_id=job["job_id"],
                error=job.get("error"),
                total_pairs=job["total_pairs"],
                classified_pairs=job["done_pairs"],
                mappings_count=len(pair_mappings),
                pending_review_count=pending,
                unresolved_count=len(pair_unresolved),
                disjoint_total=pair_disjoint["total_disjoint"],
                disjoint_decided=pair_disjoint["decided"],
                disjoint_open=pair_disjoint["open"],
            )
        )

    disjoint_summary = disjoint_service.get_summary(project_id=project_id)
    clusters = ontology_service.get_cluster_results(project_id=project_id)

    # pending_review_count schließt offene Paare (RELATED oder ohne
    # Mehrheitsentscheid) bereits ein; unresolved_count bleibt als eigene
    # Bedingung stehen: ein Fall ohne Mehrheitsentscheid und ohne auflösbare
    # KQR-Zuordnung soll den Export ebenfalls als unvollständig ausweisen.
    export_ready = disjoint_summary["open"] == 0 and all(
        pair.pending_review_count == 0 and pair.unresolved_count == 0 for pair in kqr_pairs
    )

    return ProjectPipelineStatus(
        project=project,
        kqr_pairs=kqr_pairs,
        disjoint_total=disjoint_summary["total_disjoint"],
        disjoint_decided=disjoint_summary["decided"],
        disjoint_open=disjoint_summary["open"],
        clustering_done=bool(clusters),
        export_ready=export_ready,
    )


def _migrate_legacy_data() -> None:
    """
    Falls data/projects/ noch nicht existiert, aber data/mappings.json
    vorhanden ist:
    1. Erstellt data/projects/default/
    2. Verschiebt (nicht kopiert) die bekannten Laufzeitdateien/-verzeichnisse
       nach data/projects/default/
    3. Legt data/projects/default/project.json mit name="Migrated Default"
       und kqr_ids=[alle aktuell registrierten KQR-IDs] an.

    Idempotent: existiert data/projects/ bereits, passiert nichts.
    Formalisierte TTL-Dateien und die KQR-Registry bleiben unangetastet.
    """
    projects_dir = _projects_dir()
    if projects_dir.exists():
        return

    legacy_mappings_path = DATA_DIR / "mappings.json"
    if not legacy_mappings_path.exists():
        return

    from app.services import kqr_service

    default_dir = projects_dir / "default"
    default_dir.mkdir(parents=True, exist_ok=True)

    for filename in _LEGACY_FILES:
        source = DATA_DIR / filename
        if source.exists():
            shutil.move(str(source), str(default_dir / filename))

    for dirname in _LEGACY_DIRS:
        source = DATA_DIR / dirname
        if source.exists():
            shutil.move(str(source), str(default_dir / dirname))

    try:
        kqr_ids = [kqr.id for kqr in kqr_service.list_kqr()]
    except Exception:
        kqr_ids = []

    project = Project(
        project_id="default",
        name="Migrated Default",
        kqr_ids=kqr_ids,
    )
    _write_project(project)
    logger.info("Legacy-Daten nach data/projects/default/ migriert.")


_migrate_legacy_data()
