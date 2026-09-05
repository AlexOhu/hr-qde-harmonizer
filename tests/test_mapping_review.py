"""
Regressionstests für die Konjunkt/Disjunkt-Weiche (FZ3.2) und die
Coverage-Bilanz aus /export/summary.

Der Kern des Ausbaus: RELATED-Ergebnisse und Paare ohne LLM-Mehrheitsentscheid
sind nicht mehr flüchtige Objekte im Prüfbericht, sondern persistierte
Mappings mit stabiler mapping_id, über GET /mappings/ sichtbar und über
PUT /mappings/{mapping_id}/review entscheidbar. Ein offenes Paar ohne
Mehrheitsentscheid trägt predicate_id=None, ein offenes RELATED
skos:relatedMatch.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.models.schemas import (
    CandidatePair,
    ClassificationResult,
    ClassificationRun,
    DisjointStrategy,
    MappingJustification,
    RelationType,
    ReviewStatus,
)
from app.pipeline.step4_export.sssom_writer import classification_results_to_mappings
from app.services import kqr_service, mapping_service

client = TestClient(app)


def _classification_result(relation: RelationType | None, index: int) -> ClassificationResult:
    # relation=None steht für "kein Mehrheitsentscheid"; die Einzelläufe
    # tragen trotzdem eine konkrete Relation.
    run = ClassificationRun(
        relation=relation or RelationType.RELATED,
        reasoning="Testbegründung",
        model="fake/test-model",
        temperature=0.0,
    )
    return ClassificationResult(
        pair=CandidatePair(
            concept_a=f"urn:sat:{index}", concept_b=f"urn:hub:{index}", similarity_score=0.6
        ),
        runs=[run, run, run],
        final_relation=relation,
        mapping_confidence=1.0,
    )


def _persist(relations: list[RelationType | None]) -> list[str]:
    """Legt zu jeder Relation ein Kandidatenpaar an und persistiert es über
    denselben Weg wie die Klassifikationspipeline. Gibt die mapping_ids in
    derselben Reihenfolge zurück."""
    results = [_classification_result(relation, i) for i, relation in enumerate(relations)]
    lookup = {
        uri: {"pref_label": f"Label {uri}", "kqr_id": "sat" if ":sat:" in uri else "hub"}
        for result in results
        for uri in (result.pair.concept_a, result.pair.concept_b)
    }
    mapping_service.add_classification_results(results)
    mappings = classification_results_to_mappings(results, lookup)
    mapping_service.add_mappings(mappings)
    return [m.mapping_id for m in mappings]


@pytest.fixture
def unresolved_mapping_id(isolated_services) -> str:
    """Ein offenes Paar ohne LLM-Mehrheitsentscheid (predicate_id=None)."""
    return _persist([None])[0]


def _get_mapping_from_api(mapping_id: str) -> dict:
    response = client.get("/mappings/")
    assert response.status_code == 200
    match = [m for m in response.json() if m["mapping_id"] == mapping_id]
    assert match, f"Mapping '{mapping_id}' fehlt in GET /mappings/"
    return match[0]


# ── Sichtbarkeit offener Fälle ───────────────────────────────────────────


def test_no_consensus_pair_is_listed_with_open_status(unresolved_mapping_id):
    """Vorher waren Fälle ohne Mehrheitsentscheid über /mappings/ gar nicht
    erreichbar. Sie tragen jetzt predicate_id=None."""
    entry = _get_mapping_from_api(unresolved_mapping_id)

    assert entry["review_status"] == "open"
    assert entry["predicate_id"] is None
    assert entry["mapping_justification"] == "semapv:LLMBasedMatching"


def test_related_and_no_consensus_both_appear_in_the_result_list(isolated_services):
    _persist([RelationType.RELATED, None, RelationType.EQUIVALENT])

    listed = client.get("/mappings/").json()
    by_predicate = {m["predicate_id"]: m for m in listed}

    assert by_predicate["skos:relatedMatch"]["review_status"] == "open"
    assert by_predicate[None]["review_status"] == "open"
    assert by_predicate["skos:exactMatch"]["review_status"] == "conjunct"


def test_review_status_filter_narrows_to_open_entries(isolated_services):
    _persist([RelationType.RELATED, RelationType.EQUIVALENT])

    open_entries = client.get("/mappings/", params={"review_status": "open"}).json()

    assert len(open_entries) == 1
    assert open_entries[0]["predicate_id"] == "skos:relatedMatch"


# ── Konjunkt-Zweig ───────────────────────────────────────────────────────


def test_review_resolves_unresolved_pair_as_conjunct(unresolved_mapping_id):
    response = client.put(
        f"/mappings/{unresolved_mapping_id}/review",
        json={
            "decision": "conjunct",
            "predicate": "skos:broadMatch",
            "confidence": 1.0,
            "author": "Alex",
            "justification": "Subjekt ist der weitere Begriff.",
        },
    )
    assert response.status_code == 200

    entry = _get_mapping_from_api(unresolved_mapping_id)
    assert entry["review_status"] == "conjunct"
    assert entry["predicate_id"] == "skos:broadMatch"
    assert entry["mapping_justification"] == "semapv:MappingReview"
    assert entry["mapping_confidence"] == 1.0
    assert entry["mapping_source"] == "manual"


def test_conjunct_review_accepts_close_match(unresolved_mapping_id):
    """skos:closeMatch erzeugt die Klassifikation nie, ein Reviewer muss es
    aber vergeben können."""
    response = client.put(
        f"/mappings/{unresolved_mapping_id}/review",
        json={"decision": "conjunct", "predicate": "skos:closeMatch", "author": "Alex"},
    )

    assert response.status_code == 200
    assert response.json()["predicate_id"] == "skos:closeMatch"


def test_conjunct_review_defaults_confidence_to_one(unresolved_mapping_id):
    """Eine menschliche Entscheidung ist nicht unsicherer als ein Regelmatch."""
    response = client.put(
        f"/mappings/{unresolved_mapping_id}/review",
        json={"decision": "conjunct", "predicate": "skos:exactMatch", "author": "Alex"},
    )

    assert response.json()["mapping_confidence"] == 1.0


# ── Disjunkt-Zweig ───────────────────────────────────────────────────────


def test_review_resolves_unresolved_pair_as_disjunct(unresolved_mapping_id):
    response = client.put(
        f"/mappings/{unresolved_mapping_id}/review",
        json={
            "decision": "disjunct",
            "strategy": "own_class",
            "author": "Alex",
            "justification": "Kein Pendant im Hub-Rahmen.",
        },
    )
    assert response.status_code == 200

    entry = _get_mapping_from_api(unresolved_mapping_id)
    assert entry["review_status"] == "disjunct"
    assert entry["mapping_justification"] == "semapv:MappingReview"

    # Das Subjektkonzept trägt jetzt eine Integrationsstrategie und wird im
    # Ontologie-Export als harm:HarmonisedConcept materialisiert.
    decisions = client.get("/disjoint/decisions").json()
    assert len(decisions) == 1
    assert decisions[0]["concept_id"] == entry["subject_id"]
    assert decisions[0]["strategy"] == "own_class"


def test_map_to_nearest_creates_related_match_and_keeps_the_note(unresolved_mapping_id):
    response = client.put(
        f"/mappings/{unresolved_mapping_id}/review",
        json={
            "decision": "disjunct",
            "strategy": "map_to_nearest",
            "context_loss_note": "Niveaubezug des Ausgangskonzepts geht verloren.",
            "author": "Alex",
        },
    )
    assert response.status_code == 200

    entry = _get_mapping_from_api(unresolved_mapping_id)
    assert entry["predicate_id"] == "skos:relatedMatch"
    assert entry["mapping_justification"] == "semapv:MappingReview"
    assert entry["context_loss_note"] == "Niveaubezug des Ausgangskonzepts geht verloren."

    decision = client.get("/disjoint/decisions").json()[0]
    assert decision["strategy"] == "map_to_nearest"
    assert decision["context_loss_note"] == entry["context_loss_note"]


def test_map_to_nearest_without_context_loss_note_is_rejected(unresolved_mapping_id):
    response = client.put(
        f"/mappings/{unresolved_mapping_id}/review",
        json={"decision": "disjunct", "strategy": "map_to_nearest", "author": "Alex"},
    )

    assert response.status_code == 400
    assert "context_loss_note" in response.json()["detail"]
    # Der Fall bleibt offen: eine abgelehnte Eingabe darf nichts verändern.
    assert _get_mapping_from_api(unresolved_mapping_id)["review_status"] == "open"


def test_map_to_nearest_with_blank_context_loss_note_is_rejected(unresolved_mapping_id):
    response = client.put(
        f"/mappings/{unresolved_mapping_id}/review",
        json={
            "decision": "disjunct",
            "strategy": "map_to_nearest",
            "context_loss_note": "   ",
            "author": "Alex",
        },
    )

    assert response.status_code == 400


# ── Abgelehnte Eingaben ──────────────────────────────────────────────────


def test_pending_is_rejected_as_strategy(unresolved_mapping_id):
    """"pending" ist kein entscheidbarer Zustand, sondern das Fehlen einer
    Entscheidung -- und darf deshalb nie gespeichert werden."""
    response = client.put(
        f"/mappings/{unresolved_mapping_id}/review",
        json={"decision": "disjunct", "strategy": "pending", "author": "Alex"},
    )

    assert response.status_code == 400
    assert "pending" in response.json()["detail"]


def test_pending_is_rejected_as_predicate(unresolved_mapping_id):
    response = client.put(
        f"/mappings/{unresolved_mapping_id}/review",
        json={"decision": "conjunct", "predicate": "pending", "author": "Alex"},
    )

    assert response.status_code == 400
    assert "pending" in response.json()["detail"]


def test_pending_is_rejected_by_the_disjoint_decide_route(isolated_services, hub_ttl, mock_sentence_transformer):
    """Dieselbe Regel gilt auf dem zweiten Weg in denselben Store."""
    kqr = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    concept_id = kqr_service.get_concepts(kqr.id)[0].uri

    response = client.post(
        f"/disjoint/concepts/{concept_id}/decide",
        json={"strategy": "pending", "justification": "x", "author": "Alex"},
    )

    assert response.status_code == 400


def test_unknown_decision_is_rejected(unresolved_mapping_id):
    response = client.put(
        f"/mappings/{unresolved_mapping_id}/review",
        json={"decision": "vielleicht", "author": "Alex"},
    )

    assert response.status_code == 400


def test_review_of_unknown_mapping_returns_404(isolated_services):
    response = client.put(
        "/mappings/gibt-es-nicht/review",
        json={"decision": "conjunct", "predicate": "skos:exactMatch", "author": "Alex"},
    )

    assert response.status_code == 404


# ── Enum-Vokabular ───────────────────────────────────────────────────────


def test_strategy_values_use_underscores_not_hyphens():
    """Bindestriche würden im generierten Cypher der neosemantics-
    Materialisierung als Subtraktionsoperator gelesen."""
    for strategy in DisjointStrategy:
        assert "-" not in strategy.value


def test_legacy_strategy_names_still_load():
    """Bereits persistierte Entscheidungen bleiben ohne Migrationslauf ladbar."""
    assert DisjointStrategy("standalone_class") == DisjointStrategy.OWN_CLASS
    assert DisjointStrategy("anchor_to_root") == DisjointStrategy.ATTACH_TO_SKELETON
    assert DisjointStrategy("excluded") == DisjointStrategy.OUT_OF_SCOPE
    with pytest.raises(ValueError):
        DisjointStrategy("pending")


# ── Coverage-Bilanz (/export/summary) ────────────────────────────────────


def test_coverage_ratio_counts_open_reviews_in_the_denominator(isolated_services):
    """Zehn Paare, sieben entschieden, drei offen: die Quote muss 0,7 sein.
    Fielen offene Paare aus dem Nenner, meldete das Projekt 1,0 und behauptete
    eine Vollständigkeit, die es nicht gibt."""
    mapping_ids = _persist([None] * 7 + [RelationType.RELATED] * 3)
    for mapping_id in mapping_ids[:7]:
        response = client.put(
            f"/mappings/{mapping_id}/review",
            json={"decision": "conjunct", "predicate": "skos:exactMatch", "author": "Alex"},
        )
        assert response.status_code == 200

    summary = client.get("/export/summary").json()

    assert summary["coverage_total"] == 10
    assert summary["coverage_resolved"] == 7
    assert summary["coverage_ratio"] == pytest.approx(0.7)
    assert summary["open_review_count"] == 3


def test_disjunct_decisions_count_as_resolved(isolated_services):
    """Auch der Disjunkt-Zweig ist eine Entscheidung und gehört in den Zähler."""
    mapping_ids = _persist([None, None])
    client.put(
        f"/mappings/{mapping_ids[0]}/review",
        json={"decision": "disjunct", "strategy": "out_of_scope", "author": "Alex"},
    )

    summary = client.get("/export/summary").json()

    assert summary["coverage_resolved"] == 1
    assert summary["coverage_total"] == 2
    assert summary["coverage_ratio"] == pytest.approx(0.5)


def test_coverage_ratio_is_zero_without_any_pairs(isolated_services):
    summary = client.get("/export/summary").json()

    assert summary["coverage_total"] == 0
    assert summary["coverage_ratio"] == 0.0
    assert summary["open_review_count"] == 0


def test_open_review_count_matches_total_minus_resolved(isolated_services):
    _persist([RelationType.EQUIVALENT] * 4 + [RelationType.RELATED] * 6)

    summary = client.get("/export/summary").json()

    assert summary["open_review_count"] == summary["coverage_total"] - summary["coverage_resolved"]
    assert summary["open_review_count"] == 6


# ── Wirkung auf die Exportartefakte ──────────────────────────────────────


def test_resolved_conjunct_mapping_reaches_the_sssom_preview(unresolved_mapping_id):
    """Vor der Entscheidung gehört ein offenes Paar in keine Exportvorschau,
    danach schon."""
    assert client.get("/mappings/sssom-preview").json()["total_count"] == 0

    client.put(
        f"/mappings/{unresolved_mapping_id}/review",
        json={"decision": "conjunct", "predicate": "skos:exactMatch", "author": "Alex"},
    )

    preview = client.get("/mappings/sssom-preview").json()
    assert preview["total_count"] == 1
    assert preview["sample"][0]["mapping_justification"] == "semapv:MappingReview"
    assert "match_type" not in preview["fields"]


def test_review_decision_survives_a_reload_from_disk(unresolved_mapping_id):
    """Die Entscheidung liegt in mappings.json, nicht nur im Prozessspeicher."""
    client.put(
        f"/mappings/{unresolved_mapping_id}/review",
        json={"decision": "conjunct", "predicate": "skos:narrowMatch", "author": "Alex"},
    )
    mapping_service.reload()

    reloaded = mapping_service.get_mapping(unresolved_mapping_id)
    assert reloaded.review_status == ReviewStatus.CONJUNCT
    assert reloaded.predicate_id == "skos:narrowMatch"
    assert reloaded.mapping_justification == MappingJustification.MAPPING_REVIEW
