"""
Tests für app.services.project_service. Alle Tests verwenden die
tmp_path-Fixture (keine permanenten Daten unter dem echten data/-Verzeichnis).
"""

from __future__ import annotations

import json

import pytest

from app.models.schemas import ProjectStatus
from app.services import kqr_service, project_service


@pytest.fixture
def isolated_project_service(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(project_service, "DATA_DIR", data_dir)

    # get_pipeline_status() ruft transitiv kqr_service auf (disjunkte
    # Konzepte werden über alle registrierten KQR ermittelt) -- ohne
    # Isolation würde die echte, globale Registry unter data/ durchschlagen.
    monkeypatch.setattr(kqr_service, "DATA_DIR", data_dir)
    monkeypatch.setattr(kqr_service, "RAW_DIR", data_dir / "raw")
    monkeypatch.setattr(kqr_service, "FORMALIZED_DIR", data_dir / "formalized")
    monkeypatch.setattr(kqr_service, "REGISTRY_PATH", data_dir / "kqr_registry.json")
    kqr_service.reload_registry()
    yield


def test_create_project_creates_directory_and_project_json(isolated_project_service):
    project = project_service.create_project(name="ESCO-ECF", kqr_ids=["esco", "ecf"])

    project_dir = project_service.get_project_data_dir(project.project_id)
    assert project_dir.is_dir()
    assert (project_dir / "project.json").exists()
    assert project.name == "ESCO-ECF"
    assert project.kqr_ids == ["esco", "ecf"]
    assert project.status == ProjectStatus.ACTIVE


def test_list_projects_returns_empty_list_when_no_projects_dir(isolated_project_service):
    assert project_service.list_projects() == []


def test_get_project_raises_key_error_for_unknown_id(isolated_project_service):
    with pytest.raises(KeyError):
        project_service.get_project("does-not-exist")


def test_update_project_changes_name_and_description_and_bumps_updated_at(isolated_project_service):
    project = project_service.create_project(name="Original", kqr_ids=["esco"])
    original_updated_at = project.updated_at

    updated = project_service.update_project(
        project.project_id, name="Neuer Name", description="Neue Beschreibung"
    )

    assert updated.name == "Neuer Name"
    assert updated.description == "Neue Beschreibung"
    assert updated.updated_at >= original_updated_at
    assert project_service.get_project(project.project_id).name == "Neuer Name"


def test_create_snapshot_copies_data_files_and_leaves_original_untouched(isolated_project_service):
    project = project_service.create_project(name="Original", kqr_ids=["esco", "ecf"])
    project_dir = project_service.get_project_data_dir(project.project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "mappings.json").write_text(json.dumps([{"dummy": True}]), encoding="utf-8")

    snapshot = project_service.create_snapshot(project.project_id, version_label="v1")

    assert snapshot.status == ProjectStatus.SNAPSHOT
    assert snapshot.parent_project_id == project.project_id
    assert snapshot.version_label == "v1"

    snapshot_dir = project_service.get_project_data_dir(snapshot.project_id)
    assert (snapshot_dir / "mappings.json").read_text(encoding="utf-8") == (
        project_dir / "mappings.json"
    ).read_text(encoding="utf-8")

    original = project_service.get_project(project.project_id)
    assert original.status == ProjectStatus.ACTIVE


def test_fork_project_creates_empty_active_project_with_parent_reference(isolated_project_service):
    source = project_service.create_project(name="Quelle", kqr_ids=["esco", "ecf"])
    source_dir = project_service.get_project_data_dir(source.project_id)
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "mappings.json").write_text("[]", encoding="utf-8")

    forked = project_service.fork_project(source.project_id, "Fork", ["esco", "dqr"])

    assert forked.status == ProjectStatus.ACTIVE
    assert forked.parent_project_id == source.project_id
    assert forked.kqr_ids == ["esco", "dqr"]
    forked_dir = project_service.get_project_data_dir(forked.project_id)
    assert not (forked_dir / "mappings.json").exists()


def test_delete_project_removes_directory(isolated_project_service):
    project = project_service.create_project(name="Zu löschen", kqr_ids=["esco"])
    project_service.delete_project(project.project_id)

    with pytest.raises(KeyError):
        project_service.get_project(project.project_id)


def test_delete_project_raises_key_error_for_unknown_id(isolated_project_service):
    with pytest.raises(KeyError):
        project_service.delete_project("does-not-exist")


def test_ensure_writable_raises_for_snapshot_project(isolated_project_service):
    project = project_service.create_project(name="Original", kqr_ids=["esco"])
    snapshot = project_service.create_snapshot(project.project_id, version_label="v1")

    project_service.ensure_writable(project.project_id)  # kein Fehler
    with pytest.raises(ValueError):
        project_service.ensure_writable(snapshot.project_id)


def test_ensure_writable_tolerates_unknown_project_id(isolated_project_service):
    # Rückwärtskompatibler Default-Fall ohne project.json (Invariante 3).
    project_service.ensure_writable("default")


def test_get_pipeline_status_returns_empty_kqr_pairs_for_new_project(isolated_project_service):
    project = project_service.create_project(name="Neu", kqr_ids=["esco", "ecf"])

    status = project_service.get_pipeline_status(project.project_id)

    assert status.project.project_id == project.project_id
    assert status.kqr_pairs == []
    assert status.disjoint_total == 0
    assert status.clustering_done is False
    assert status.export_ready is True


def test_get_pipeline_status_disjoint_counts_are_scoped_per_pair(
    isolated_project_service, hub_ttl, satellite_ttl, mock_sentence_transformer
):
    """KQRPairStatus.disjoint_total/_decided/_open müssen sich auf genau
    dieses Paar beziehen (list_disjoint_concepts_for_pair()), nicht auf die
    projektweite disjunkte Menge -- sonst würde ein in einem anderen Paar
    gematchtes Konzept fälschlich als 'nicht disjunkt' gezählt."""
    from app.models.schemas import Mapping, MappingJustification, RelationType
    from app.services import classification_service, mapping_service

    hub = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    satellite = kqr_service.register_kqr(
        name="Satellite KQR", source_format="turtle", filename="satellite.ttl",
        content=satellite_ttl.encode("utf-8"), is_hub=False,
    )

    project = project_service.create_project(name="Test", kqr_ids=[hub.id, satellite.id])

    # Simulierter abgeschlossener Job für dieses Paar (kein echter LLM-Lauf
    # nötig -- get_pipeline_status liest nur job-Metadaten und Mappings).
    classification_service._get_project_jobs(project.project_id)["job-1"] = {
        "job_id": "job-1", "kqr_a_id": hub.id, "kqr_b_id": satellite.id,
        "status": "completed", "done_pairs": 1, "total_pairs": 1, "error": None,
    }

    hub_concepts = {c.uri.rsplit("/", 1)[-1]: c for c in kqr_service.get_concepts(hub.id)}
    satellite_concepts = {c.uri.rsplit("/", 1)[-1]: c for c in kqr_service.get_concepts(satellite.id)}
    programming = hub_concepts["programming"]
    project_management = satellite_concepts["project_management"]

    mapping_service.add_mappings(
        [
            Mapping(
                subject_id=programming.uri,
                subject_label=programming.pref_label,
                subject_kqr_id=programming.kqr_id,
                object_id=project_management.uri,
                object_label=project_management.pref_label,
                object_kqr_id=project_management.kqr_id,
                predicate_id=RelationType.EQUIVALENT.to_skos_predicate(),
                mapping_confidence=0.9,
                mapping_justification=MappingJustification.LLM_BASED_MATCHING,
                mapping_source="algorithmic",
            )
        ],
        project_id=project.project_id,
    )

    status = project_service.get_pipeline_status(project.project_id)

    assert len(status.kqr_pairs) == 1
    pair = status.kqr_pairs[0]
    assert pair.mappings_count == 1
    # Hub: 6 Konzepte, Satellite: 4 Konzepte, 2 davon gematcht -> 8 disjunkt.
    assert pair.disjoint_total == 8
    assert pair.disjoint_open == 8
    assert pair.disjoint_decided == 0


def test_get_pipeline_status_surfaces_job_error_for_failed_pair(
    isolated_project_service, hub_ttl, satellite_ttl, mock_sentence_transformer
):
    """Ein gescheiterter Job traegt seine Fehlermeldung bis in KQRPairStatus,
    damit die Projektuebersicht mehr zeigen kann als nur 'Fehlgeschlagen'."""
    from app.services import classification_service

    hub = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    satellite = kqr_service.register_kqr(
        name="Satellite KQR", source_format="turtle", filename="satellite.ttl",
        content=satellite_ttl.encode("utf-8"), is_hub=False,
    )
    project = project_service.create_project(
        name="Failed Pair Test", kqr_ids=[hub.id, satellite.id]
    )

    classification_service._get_project_jobs(project.project_id)["job-failed"] = {
        "job_id": "job-failed", "kqr_a_id": hub.id, "kqr_b_id": satellite.id,
        "status": "failed", "done_pairs": 3, "total_pairs": 10,
        "error": "Mistral-API: 429 Too Many Requests",
    }

    status = project_service.get_pipeline_status(project.project_id)

    assert len(status.kqr_pairs) == 1
    pair = status.kqr_pairs[0]
    assert pair.job_status == "failed"
    assert pair.error == "Mistral-API: 429 Too Many Requests"


def test_get_pipeline_status_leaves_error_empty_for_interrupted_pair(
    isolated_project_service, hub_ttl, satellite_ttl, mock_sentence_transformer
):
    """Ein unterbrochener (nicht gescheiterter) Job hat keine Ausnahme
    erlebt -- error bleibt None, statt eine irrefuehrende Meldung zu zeigen."""
    from app.services import classification_service

    hub = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    satellite = kqr_service.register_kqr(
        name="Satellite KQR", source_format="turtle", filename="satellite.ttl",
        content=satellite_ttl.encode("utf-8"), is_hub=False,
    )
    project = project_service.create_project(
        name="Interrupted Pair Test", kqr_ids=[hub.id, satellite.id]
    )

    classification_service._get_project_jobs(project.project_id)["job-interrupted"] = {
        "job_id": "job-interrupted", "kqr_a_id": hub.id, "kqr_b_id": satellite.id,
        "status": "interrupted", "done_pairs": 3, "total_pairs": 10, "error": None,
    }

    status = project_service.get_pipeline_status(project.project_id)

    assert status.kqr_pairs[0].error is None


def test_migrate_legacy_data_moves_files_and_is_idempotent(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "mappings.json").write_text("[]", encoding="utf-8")
    (data_dir / "classification_jobs.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(project_service, "DATA_DIR", data_dir)

    project_service._migrate_legacy_data()

    default_dir = data_dir / "projects" / "default"
    assert (default_dir / "mappings.json").exists()
    assert not (data_dir / "mappings.json").exists()
    assert (default_dir / "project.json").exists()

    # Idempotenz: zweiter Aufruf darf nichts mehr verändern.
    project_service._migrate_legacy_data()
    assert (default_dir / "mappings.json").exists()
