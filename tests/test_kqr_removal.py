"""
Tests fuer das KQR-Entfernen-Feature: zwei bewusst getrennte Operationen
(vgl. ADR-01 in app/services/project_service.py).

a) project_service.remove_kqr_from_project() -- projekt-scoped, guenstig,
   reversibel: der KQR bleibt in der globalen Registry, nur die Referenz
   und die betroffenen Paare dieses Projekts werden aufgeraeumt (ueber die
   bestehende classification_service.reset_pair()-Logik).
b) kqr_service.delete_kqr() -- global destruktiv, gesperrt solange
   irgendein Projekt den KQR noch referenziert.

Folgt den Konventionen aus tests/test_pair_reset.py und
tests/test_project_service.py: isolated_services-Fixture (tmp_path-Store,
kein Netzwerk, kein Neo4j noetig), mock_sentence_transformer/mock_anthropic
zum Umgehen echter Modell-/API-Aufrufe, hub_ttl/satellite_ttl-Fixtures aus
conftest.py.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.services import classification_service, kqr_service, project_service

client = TestClient(app)


def _run_job_to_completion(
    kqr_a_id: str, kqr_b_id: str, project_id: str = "default", timeout: float = 20.0
) -> dict:
    """Startet einen Klassifikationslauf und blockiert, bis er abgeschlossen
    ist (analog zu test_pair_reset._run_job_to_completion)."""
    job_id = classification_service.start_classification_job(
        kqr_a_id, kqr_b_id, project_id=project_id
    )
    deadline = time.time() + timeout
    progress = classification_service.get_job_progress(job_id, project_id=project_id)
    while progress["status"] == "running" and time.time() < deadline:
        time.sleep(0.05)
        progress = classification_service.get_job_progress(job_id, project_id=project_id)
    assert progress["status"] == "completed", progress
    return progress


@pytest.fixture
def project_with_classified_pair(isolated_services, hub_ttl, satellite_ttl, mock_sentence_transformer, mock_anthropic):
    """Ein Projekt mit Hub und Satellit, deren Paar bereits vollstaendig
    klassifiziert wurde -- Grundlage fuer die Entfernungs-Tests."""
    mock_anthropic("EQUIVALENT | Testbegründung")
    hub_kqr = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    satellite_kqr = kqr_service.register_kqr(
        name="Satellite KQR", source_format="turtle", filename="satellite.ttl",
        content=satellite_ttl.encode("utf-8"), is_hub=False,
    )
    project = project_service.create_project(
        name="Entfernungs-Testprojekt",
        kqr_ids=[hub_kqr.id, satellite_kqr.id],
        hub_kqr_id=hub_kqr.id,
    )
    _run_job_to_completion(hub_kqr.id, satellite_kqr.id, project_id=project.project_id)
    return project, hub_kqr, satellite_kqr


# ── a) projekt-scoped Entfernung ─────────────────────────────────────────


def test_remove_kqr_from_project_resets_all_affected_pairs_and_updates_kqr_ids(
    project_with_classified_pair,
):
    from app.services import mapping_service

    project, hub_kqr, satellite_kqr = project_with_classified_pair
    mappings_before = mapping_service.list_mappings_for_pair(
        hub_kqr.id, satellite_kqr.id, project_id=project.project_id
    )
    assert len(mappings_before) > 0

    result = project_service.remove_kqr_from_project(
        project.project_id, satellite_kqr.id, author="Alex"
    )

    assert result == {"removed_pairs": 1, "was_hub": False}
    assert (
        mapping_service.list_mappings_for_pair(
            hub_kqr.id, satellite_kqr.id, project_id=project.project_id
        )
        == []
    )

    updated = project_service.get_project(project.project_id)
    assert updated.kqr_ids == [hub_kqr.id]

    events = classification_service.list_reset_events(project.project_id)
    assert len(events) == 1
    assert events[0]["justification"] == f"KQR '{satellite_kqr.id}' aus Projekt entfernt."
    assert events[0]["author"] == "Alex"


def test_remove_kqr_from_project_accepts_custom_justification(project_with_classified_pair):
    project, hub_kqr, satellite_kqr = project_with_classified_pair

    project_service.remove_kqr_from_project(
        project.project_id, satellite_kqr.id, author="Alex", justification="Falsches Framework."
    )

    events = classification_service.list_reset_events(project.project_id)
    assert events[0]["justification"] == "Falsches Framework."


def test_remove_kqr_from_project_blocks_hub_removal(project_with_classified_pair):
    project, hub_kqr, _satellite_kqr = project_with_classified_pair

    with pytest.raises(ValueError, match="Hub"):
        project_service.remove_kqr_from_project(project.project_id, hub_kqr.id, author="Alex")

    # Ein blockierter Versuch veraendert weder kqr_ids noch die Mappings.
    unchanged = project_service.get_project(project.project_id)
    assert hub_kqr.id in unchanged.kqr_ids


def test_remove_kqr_from_project_blocked_on_snapshot_project(project_with_classified_pair):
    project, _hub_kqr, satellite_kqr = project_with_classified_pair
    snapshot = project_service.create_snapshot(project.project_id, version_label="v1")

    with pytest.raises(ValueError, match="Snapshot"):
        project_service.remove_kqr_from_project(
            snapshot.project_id, satellite_kqr.id, author="Alex"
        )

    assert satellite_kqr.id in project_service.get_project(snapshot.project_id).kqr_ids


def test_remove_kqr_from_project_leaves_global_registry_untouched(project_with_classified_pair):
    """Ein entfernter KQR bleibt global registriert, formalisiert und
    eingebettet -- er laesst sich spaeter erneut zu einem Projekt
    hinzufuegen (ADR-01)."""
    project, _hub_kqr, satellite_kqr = project_with_classified_pair

    project_service.remove_kqr_from_project(project.project_id, satellite_kqr.id, author="Alex")

    still_registered = kqr_service.get_kqr(satellite_kqr.id)
    assert still_registered.status.value == "bereit"
    assert satellite_kqr.id in {k.id for k in kqr_service.list_kqr()}
    assert (kqr_service.FORMALIZED_DIR / f"{satellite_kqr.id}.ttl").exists()


def test_remove_kqr_from_project_api_returns_400_for_hub(project_with_classified_pair):
    project, hub_kqr, _satellite_kqr = project_with_classified_pair

    response = client.request(
        "DELETE", f"/projects/{project.project_id}/kqr/{hub_kqr.id}", json={"author": "Alex"}
    )

    assert response.status_code == 400
    assert "Hub" in response.json()["detail"]


# ── b) globale Loeschung ─────────────────────────────────────────────────


def test_delete_kqr_without_reference_removes_registry_and_files(
    isolated_services, hub_ttl, mock_sentence_transformer
):
    hub_kqr = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    assert (kqr_service.FORMALIZED_DIR / f"{hub_kqr.id}.ttl").exists()
    assert list(kqr_service.RAW_DIR.glob(f"{hub_kqr.id}.*"))

    kqr_service.delete_kqr(hub_kqr.id)

    with pytest.raises(KeyError):
        kqr_service.get_kqr(hub_kqr.id)
    assert hub_kqr.id not in {k.id for k in kqr_service.list_kqr()}
    assert not (kqr_service.FORMALIZED_DIR / f"{hub_kqr.id}.ttl").exists()
    assert list(kqr_service.RAW_DIR.glob(f"{hub_kqr.id}.*")) == []


def test_delete_kqr_blocked_when_referenced_by_project_names_it(
    isolated_services, hub_ttl, mock_sentence_transformer
):
    hub_kqr = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    project_service.create_project(name="Referenzierendes Projekt", kqr_ids=[hub_kqr.id])

    with pytest.raises(ValueError, match="Referenzierendes Projekt"):
        kqr_service.delete_kqr(hub_kqr.id)

    # Die globale Registry bleibt nach dem blockierten Versuch unveraendert.
    assert kqr_service.get_kqr(hub_kqr.id) is not None


def test_delete_kqr_api_returns_409_when_referenced(isolated_services, hub_ttl, mock_sentence_transformer):
    hub_kqr = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    project_service.create_project(name="Referenzierendes Projekt", kqr_ids=[hub_kqr.id])

    response = client.delete(f"/kqr/{hub_kqr.id}")

    assert response.status_code == 409
    assert "Referenzierendes Projekt" in response.json()["detail"]


def test_delete_kqr_api_returns_404_for_unknown_id(isolated_services):
    response = client.delete("/kqr/does-not-exist")
    assert response.status_code == 404
