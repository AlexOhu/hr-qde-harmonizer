"""
Verwendet isolated_services-Fixture aus conftest.py (tmp_path-basiert).
"""

from __future__ import annotations

import pytest

from app.models.schemas import Mapping, MappingJustification, RelationType
from app.services import kqr_service, mapping_service


@pytest.fixture
def three_kqr_concepts(isolated_services, hub_ttl, satellite_ttl, mock_sentence_transformer):
    """Hub-KQR (6 Konzepte), Satellite-KQR (4 Konzepte) und ein drittes,
    minimales KQR (1 Konzept) -- Grundlage für Tests, die zwischen mehreren
    KQR-Paaren im selben Projekt unterscheiden müssen."""
    hub = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    satellite = kqr_service.register_kqr(
        name="Satellite KQR", source_format="turtle", filename="satellite.ttl",
        content=satellite_ttl.encode("utf-8"), is_hub=False,
    )
    third_ttl = """
    @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
    @prefix third: <http://hr-qde.org/harmonised/third_kqr/> .

    third:level_a a skos:Concept ;
        skos:prefLabel "Level A" .
    """
    third = kqr_service.register_kqr(
        name="Third KQR", source_format="turtle", filename="third.ttl",
        content=third_ttl.encode("utf-8"), is_hub=False,
    )
    concepts = {
        c.uri.rsplit("/", 1)[-1]: c
        for c in [
            *kqr_service.get_concepts(hub.id),
            *kqr_service.get_concepts(satellite.id),
            *kqr_service.get_concepts(third.id),
        ]
    }
    return hub, satellite, third, concepts


def _add_mapping(subject, obj):
    mapping_service.add_mappings(
        [
            Mapping(
                subject_id=subject.uri,
                subject_label=subject.pref_label,
                subject_kqr_id=subject.kqr_id,
                object_id=obj.uri,
                object_label=obj.pref_label,
                object_kqr_id=obj.kqr_id,
                predicate_id=RelationType.EQUIVALENT.to_skos_predicate(),
                mapping_confidence=0.9,
                mapping_justification=MappingJustification.LLM_BASED_MATCHING,
                mapping_source="algorithmic",
            )
        ]
    )


def test_list_mappings_for_pair_only_returns_mappings_of_that_exact_pair(three_kqr_concepts):
    hub, satellite, third, concepts = three_kqr_concepts
    _add_mapping(concepts["programming"], concepts["project_management"])  # hub<->satellite
    _add_mapping(concepts["teamwork"], concepts["level_a"])  # hub<->third

    pair_mappings = mapping_service.list_mappings_for_pair(hub.id, satellite.id)

    assert len(pair_mappings) == 1
    assert pair_mappings[0].subject_id == concepts["programming"].uri
    assert pair_mappings[0].object_id == concepts["project_management"].uri


def test_list_mappings_for_pair_is_order_independent(three_kqr_concepts):
    hub, satellite, third, concepts = three_kqr_concepts
    _add_mapping(concepts["programming"], concepts["project_management"])

    assert len(mapping_service.list_mappings_for_pair(hub.id, satellite.id)) == 1
    assert len(mapping_service.list_mappings_for_pair(satellite.id, hub.id)) == 1


def test_list_mappings_kqr_a_b_params_take_precedence_over_kqr_id(three_kqr_concepts):
    hub, satellite, third, concepts = three_kqr_concepts
    _add_mapping(concepts["programming"], concepts["project_management"])  # hub<->satellite
    _add_mapping(concepts["teamwork"], concepts["level_a"])  # hub<->third

    # kqr_id="hub_kqr" allein würde beide Mappings zurückgeben (Hub ist
    # jeweils beteiligt); mit kqr_a_id/kqr_b_id gesetzt zählt nur das Paar.
    result = mapping_service.list_mappings(kqr_id=hub.id, kqr_a_id=hub.id, kqr_b_id=satellite.id)

    assert len(result) == 1
    assert result[0].object_kqr_id == satellite.id
