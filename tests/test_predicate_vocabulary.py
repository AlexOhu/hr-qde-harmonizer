"""
Ein Relationsvokabular: MappingPredicate (SKOS-CURIEs) im Backend, RelationType
nur klassifikationsschritt-intern, kein source_relation mehr.

Deckt ab:
- Der Model-Validator lädt Datenbestände mit dem alten source_relation-Feld:
  ein offenes Paar mit source_relation="UNRESOLVED" bekommt predicate_id=None,
  das Feld selbst verschwindet.
- update_mapping (PUT /mappings/{id}) nimmt alle fünf MappingPredicate-Werte
  entgegen, auch skos:relatedMatch, und lehnt Unfug ab.
- RelationType kennt UNRESOLVED nicht mehr; to_skos_predicate() ist total.
"""

from __future__ import annotations

import pytest

from app.models.schemas import (
    CandidatePair,
    ClassificationResult,
    ClassificationRun,
    Mapping,
    MappingJustification,
    MappingPredicate,
    RelationType,
    ReviewStatus,
)
from app.pipeline.step4_export.sssom_writer import classification_results_to_mappings
from app.services import mapping_service


# ── Model-Validator: alte Datenstände bleiben ladbar ─────────────────────


def test_legacy_source_relation_unresolved_becomes_null_predicate():
    legacy = Mapping.model_validate(
        {
            "subject_id": "urn:a",
            "subject_label": "A",
            "object_id": "urn:b",
            "object_label": "B",
            "predicate_id": "skos:relatedMatch",
            "mapping_confidence": 0.33,
            "mapping_justification": "semapv:LLMBasedMatching",
            "review_status": "open",
            "source_relation": "UNRESOLVED",
        }
    )
    assert legacy.predicate_id is None
    assert not hasattr(legacy, "source_relation")


def test_legacy_source_relation_related_keeps_related_match():
    legacy = Mapping.model_validate(
        {
            "subject_id": "urn:a",
            "subject_label": "A",
            "object_id": "urn:b",
            "object_label": "B",
            "predicate_id": "skos:relatedMatch",
            "mapping_confidence": 1.0,
            "mapping_justification": "semapv:LLMBasedMatching",
            "review_status": "open",
            "source_relation": "RELATED",
        }
    )
    assert legacy.predicate_id == MappingPredicate.RELATED_MATCH


def test_legacy_source_relation_on_conjunct_mapping_is_only_dropped():
    legacy = Mapping.model_validate(
        {
            "subject_id": "urn:a",
            "subject_label": "A",
            "object_id": "urn:b",
            "object_label": "B",
            "predicate_id": "skos:exactMatch",
            "mapping_confidence": 1.0,
            "mapping_justification": "semapv:MappingReview",
            "review_status": "conjunct",
            "source_relation": "UNRESOLVED",
        }
    )
    # review_status != "open": das Prädikat bleibt, nur das Feld fällt weg.
    assert legacy.predicate_id == MappingPredicate.EXACT_MATCH
    assert not hasattr(legacy, "source_relation")


# ── RelationType ist klassifikationsschritt-intern und ohne UNRESOLVED ───


def test_relationtype_has_no_unresolved_member():
    assert {r.value for r in RelationType} == {
        "EQUIVALENT",
        "A_SUBSUMES_B",
        "B_SUBSUMES_A",
        "RELATED",
    }


def test_to_skos_predicate_is_total_over_relationtype():
    for relation in RelationType:
        assert isinstance(relation.to_skos_predicate(), MappingPredicate)


# ── update_mapping akzeptiert alle fünf Prädikate ───────────────────────


def _persist_open_no_consensus() -> str:
    pair = CandidatePair(concept_a="urn:sat:x", concept_b="urn:hub:x", similarity_score=0.6)
    run = ClassificationRun(
        relation=RelationType.RELATED, reasoning="r", model="m", temperature=0.0
    )
    result = ClassificationResult(
        pair=pair, runs=[run, run, run], final_relation=None, mapping_confidence=1.0
    )
    lookup = {
        "urn:sat:x": {"pref_label": "X", "kqr_id": "sat"},
        "urn:hub:x": {"pref_label": "Y", "kqr_id": "hub"},
    }
    mappings = classification_results_to_mappings([result], lookup)
    mapping_service.add_mappings(mappings)
    return mappings[0].mapping_id


@pytest.mark.parametrize("predicate", [p.value for p in MappingPredicate])
def test_update_mapping_accepts_every_predicate(isolated_services, predicate):
    mapping_id = _persist_open_no_consensus()
    updated = mapping_service.update_mapping(
        mapping_id, predicate, justification="geprüft", author="Alex"
    )
    assert updated.predicate_id == predicate
    assert updated.review_status == ReviewStatus.CONJUNCT
    assert updated.mapping_justification == MappingJustification.MAPPING_REVIEW


def test_update_mapping_rejects_unknown_predicate(isolated_services):
    mapping_id = _persist_open_no_consensus()
    with pytest.raises(ValueError):
        mapping_service.update_mapping(
            mapping_id, "skos:somethingElse", justification="x", author="Alex"
        )


def test_open_review_summary_discriminates_on_predicate(isolated_services):
    mapping_service.add_mappings(
        [
            Mapping(
                subject_id=f"urn:s{i}",
                subject_label="s",
                object_id=f"urn:o{i}",
                object_label="o",
                predicate_id=predicate,
                mapping_confidence=1.0,
                mapping_justification=MappingJustification.LLM_BASED_MATCHING,
                review_status=ReviewStatus.OPEN,
            )
            for i, predicate in enumerate([None, None, MappingPredicate.RELATED_MATCH])
        ]
    )
    summary = mapping_service.get_open_review_summary()
    assert summary["no_consensus_pairs"] == 2
    assert summary["related_pairs"] == 1
    assert "unresolved_pairs" not in summary
