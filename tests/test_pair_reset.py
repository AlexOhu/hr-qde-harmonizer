"""
Tests für das Paar-Reset-Feature: classification_service.reset_pair() und
die darunterliegenden Bausteine in mapping_service (delete_mappings_for_pair,
delete_classification_results_for_pair) und disjoint_service
(count_decisions_for_pair).

Unterschied zum bestehenden Resume-Mechanismus (vgl. test_service_integration.
test_restarted_job_skips_already_classified_pairs): ein Reset macht ein Paar
gezielt wieder klassifikationsbedürftig, ein Resume überspringt umgekehrt
bereits klassifizierte Paare. Beide Verhalten werden hier gegeneinander
abgegrenzt (test_reset_pair_allows_full_reclassification_afterwards).

Folgt den Konventionen aus test_mapping_service.py, test_disjoint_service.py
und test_service_integration.py: isolated_services-Fixture (tmp_path-Store,
kein Netzwerk, kein Neo4j nötig), mock_sentence_transformer/mock_anthropic
zum Umgehen echter Modell-/API-Aufrufe, hub_ttl/satellite_ttl-Fixtures aus
conftest.py.
"""

from __future__ import annotations

import time

import pytest

from app.models.schemas import DisjointStrategy
from app.services import classification_service, disjoint_service, kqr_service, mapping_service


def _run_job_to_completion(
    kqr_a_id: str, kqr_b_id: str, project_id: str = "default", timeout: float = 20.0
) -> dict:
    """Startet einen Klassifikationslauf und blockiert, bis er abgeschlossen
    ist (analog zu den Polling-Schleifen in test_service_integration.py)."""
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
def classified_pair(isolated_services, hub_ttl, satellite_ttl, mock_sentence_transformer, mock_anthropic):
    """Ein vollständig klassifiziertes Hub<->Satellit-Paar (struktureller
    Shortcut + LLM-Mappings), Grundlage für die Reset-Tests. Gibt zusätzlich
    den FakeLLMProvider zurück, damit einzelne Tests dessen Aufrufzahl prüfen
    können, ohne mock_anthropic ein zweites Mal aufzurufen -- das würde einen
    neuen Provider einsetzen und die bisherige Aufrufhistorie verlieren."""
    provider = mock_anthropic("EQUIVALENT | Testbegründung")
    hub_kqr = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    satellite_kqr = kqr_service.register_kqr(
        name="Satellite KQR", source_format="turtle", filename="satellite.ttl",
        content=satellite_ttl.encode("utf-8"), is_hub=False,
    )
    _run_job_to_completion(hub_kqr.id, satellite_kqr.id)
    return hub_kqr, satellite_kqr, provider


def test_delete_mappings_for_pair_removes_only_that_pairs_mappings(classified_pair):
    hub_kqr, satellite_kqr, _provider = classified_pair
    before = mapping_service.list_mappings_for_pair(hub_kqr.id, satellite_kqr.id)
    assert len(before) > 0

    removed = mapping_service.delete_mappings_for_pair(hub_kqr.id, satellite_kqr.id)

    assert {m.mapping_id for m in removed} == {m.mapping_id for m in before}
    assert mapping_service.list_mappings_for_pair(hub_kqr.id, satellite_kqr.id) == []


def test_delete_classification_results_for_pair_empties_get_classified_pairs(classified_pair):
    hub_kqr, satellite_kqr, _provider = classified_pair
    assert len(mapping_service.get_classified_pairs()) > 0

    removed_count = mapping_service.delete_classification_results_for_pair(
        hub_kqr.id, satellite_kqr.id
    )

    assert removed_count > 0
    assert mapping_service.get_classified_pairs() == set()


def test_count_decisions_for_pair_counts_by_kqr_membership(classified_pair):
    hub_kqr, satellite_kqr, _provider = classified_pair
    concept = kqr_service.get_concepts(hub_kqr.id)[0]

    assert disjoint_service.count_decisions_for_pair(hub_kqr.id, satellite_kqr.id) == 0

    disjoint_service.decide(
        concept_id=concept.uri,
        strategy=DisjointStrategy.OWN_CLASS,
        justification="Testentscheidung",
        author="Alex",
    )

    # Das Konzept stammt aus hub_kqr -- zählt in jedem Paar mit, in dem
    # hub_kqr vorkommt, unabhängig vom jeweils anderen KQR (die Entscheidung
    # selbst ist konzept-, nicht paarbezogen).
    assert disjoint_service.count_decisions_for_pair(hub_kqr.id, satellite_kqr.id) == 1
    assert disjoint_service.count_decisions_for_pair(hub_kqr.id, "irgendein_drittes_kqr") == 1
    assert disjoint_service.count_decisions_for_pair("kqr_x", "kqr_y") == 0


def test_reset_pair_requires_justification_and_author(classified_pair):
    hub_kqr, satellite_kqr, _provider = classified_pair

    with pytest.raises(ValueError, match="justification"):
        classification_service.reset_pair(hub_kqr.id, satellite_kqr.id, "", "Alex")

    with pytest.raises(ValueError, match="author"):
        classification_service.reset_pair(hub_kqr.id, satellite_kqr.id, "Begründung", "")


def test_reset_pair_removes_mappings_and_results_but_keeps_job_history(classified_pair):
    hub_kqr, satellite_kqr, _provider = classified_pair
    mappings_before = mapping_service.list_mappings_for_pair(hub_kqr.id, satellite_kqr.id)
    jobs_before = classification_service.list_jobs()

    result = classification_service.reset_pair(
        hub_kqr.id, satellite_kqr.id, "Klassifikation war fachlich nicht plausibel.", "Alex"
    )

    assert result["removed_mappings"] == len(mappings_before)
    assert result["removed_classification_results"] > 0
    assert result["affected_disjoint_decisions"] == 0

    assert mapping_service.list_mappings_for_pair(hub_kqr.id, satellite_kqr.id) == []
    assert mapping_service.get_classified_pairs() == set()
    # Die Job-Historie bleibt erhalten -- ein Reset löscht keine Läufe,
    # er macht nur deren Mappings/Ergebnisse rückgängig (vgl. Docstring von
    # classification_service.reset_pair).
    assert classification_service.list_jobs() == jobs_before


def test_reset_pair_does_not_touch_disjoint_decisions_but_reports_them(classified_pair):
    hub_kqr, satellite_kqr, _provider = classified_pair
    concept = kqr_service.get_concepts(hub_kqr.id)[0]
    decision = disjoint_service.decide(
        concept_id=concept.uri,
        strategy=DisjointStrategy.OWN_CLASS,
        justification="Vor dem Reset entschieden",
        author="Alex",
    )

    result = classification_service.reset_pair(
        hub_kqr.id, satellite_kqr.id, "Neu klassifizieren", "Alex"
    )

    assert result["affected_disjoint_decisions"] == 1
    # Die Entscheidung selbst bleibt unverändert bestehen (konzeptbezogen,
    # nicht paarbezogen -- vgl. disjoint_service.get_summary_for_pair).
    assert disjoint_service.get_decision(concept.uri) == decision


def test_reset_pair_persists_and_lists_reset_events(classified_pair):
    hub_kqr, satellite_kqr, _provider = classified_pair

    result = classification_service.reset_pair(
        hub_kqr.id, satellite_kqr.id, "Klassifikation zurücksetzen", "Alex"
    )

    events = classification_service.list_reset_events()
    assert len(events) == 1
    assert events[0]["kqr_a_id"] == hub_kqr.id
    assert events[0]["kqr_b_id"] == satellite_kqr.id
    assert events[0]["justification"] == "Klassifikation zurücksetzen"
    assert events[0]["author"] == "Alex"
    assert events[0]["removed_mappings"] == result["removed_mappings"]
    assert events[0]["removed_classification_results"] == result["removed_classification_results"]


def test_reset_pair_allows_full_reclassification_afterwards(classified_pair):
    """Kernverhalten des Resets, im Unterschied zu einem Resume: nach dem
    Reset muss ein erneuter Lauf jedes Konzeptpaar wieder klassifizieren
    (also erneut ans LLM gehen), nicht nur die zuvor offenen Paare -- vgl.
    test_service_integration.test_restarted_job_skips_already_classified_pairs,
    wo genau das Gegenteil (Überspringen) geprüft wird."""
    hub_kqr, satellite_kqr, provider = classified_pair
    calls_before_reset = len(provider.calls)
    assert calls_before_reset > 0

    classification_service.reset_pair(hub_kqr.id, satellite_kqr.id, "Neu klassifizieren", "Alex")
    _run_job_to_completion(hub_kqr.id, satellite_kqr.id)

    # Ein reiner Resume (get_classified_pairs()) hätte nach dem Reset keine
    # bereits erledigten Paare mehr gekannt -- der zweite Lauf muss daher
    # genauso viele LLM-Aufrufe auslösen wie der erste.
    assert len(provider.calls) - calls_before_reset == calls_before_reset


def test_reset_pair_blocked_on_snapshot_project(
    isolated_services, hub_ttl, satellite_ttl, mock_sentence_transformer, mock_anthropic
):
    from app.services import project_service

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
        name="Snapshot-Testprojekt", kqr_ids=[hub_kqr.id, satellite_kqr.id]
    )
    _run_job_to_completion(hub_kqr.id, satellite_kqr.id, project_id=project.project_id)
    snapshot = project_service.create_snapshot(project.project_id, version_label="v1")

    with pytest.raises(ValueError, match="Snapshot"):
        classification_service.reset_pair(
            hub_kqr.id, satellite_kqr.id, "Begründung", "Alex", project_id=snapshot.project_id
        )

    # Das Ursprungsprojekt bleibt vom fehlgeschlagenen Reset-Versuch auf dem
    # Snapshot unberührt.
    assert (
        mapping_service.list_mappings_for_pair(
            hub_kqr.id, satellite_kqr.id, project_id=project.project_id
        )
        != []
    )
