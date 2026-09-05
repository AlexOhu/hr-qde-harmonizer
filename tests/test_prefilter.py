import numpy as np

from app.models.schemas import MappingJustification, Mapping, ReviewStatus
from app.pipeline.step1_formalization.formalize import parse_concepts
from app.pipeline.step2_embedding_prefilter.prefilter import (
    derive_container_mappings,
    detect_container_concepts,
    find_candidate_pairs,
    find_structural_shortcuts,
)
from rdflib import Graph


_CONTAINER_TTL = """
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex:   <http://example.org/> .

ex:scheme a skos:ConceptScheme .

ex:PLAN a skos:Concept ; skos:prefLabel "PLAN"@en ; skos:broader ex:scheme .
ex:A1 a skos:Concept ; skos:prefLabel "A.1"@en ; skos:broader ex:PLAN .
ex:A2 a skos:Concept ; skos:prefLabel "A.2"@en ; skos:broader ex:PLAN .

ex:GROUP a skos:Concept ; skos:prefLabel "GROUP"@en ; skos:narrower ex:LEAF1 .
ex:LEAF1 a skos:Concept ; skos:prefLabel "Leaf 1"@en .

ex:SOLO a skos:Concept ; skos:prefLabel "Solo"@en .
"""


def _graph(ttl: str) -> Graph:
    g = Graph()
    g.parse(data=ttl, format="turtle")
    return g


def test_detect_container_concepts_via_broader_and_narrower():
    containers, children = detect_container_concepts(_graph(_CONTAINER_TTL))

    assert containers == {"http://example.org/PLAN", "http://example.org/GROUP"}
    assert children["http://example.org/PLAN"] == [
        "http://example.org/A1",
        "http://example.org/A2",
    ]
    assert children["http://example.org/GROUP"] == ["http://example.org/LEAF1"]


def test_detect_container_concepts_ignores_scheme_parent():
    # ex:PLAN skos:broader ex:scheme darf ex:scheme nicht zum Container machen.
    containers, _ = detect_container_concepts(_graph(_CONTAINER_TTL))
    assert "http://example.org/scheme" not in containers
    assert "http://example.org/SOLO" not in containers


def _leaf_mapping(subject_id, object_id, object_label, confidence, status=ReviewStatus.CONJUNCT):
    return Mapping(
        subject_id=subject_id,
        subject_label=subject_id.rsplit("/", 1)[-1],
        subject_kqr_id="ecf",
        object_id=object_id,
        object_label=object_label,
        object_kqr_id="esco",
        predicate_id="skos:narrowMatch",
        mapping_confidence=confidence,
        mapping_justification=MappingJustification.LLM_BASED_MATCHING,
        review_status=status,
    )


def test_derive_container_mappings_averages_child_confidences():
    container_children = {"http://example.org/PLAN": ["http://example.org/A1", "http://example.org/A2"]}
    concept_lookup = {
        "http://example.org/PLAN": {"pref_label": "PLAN", "kqr_id": "ecf"},
    }
    pair_mappings = [
        _leaf_mapping("http://example.org/A1", "http://esco/x", "skill x", 1.0),
        _leaf_mapping("http://example.org/A2", "http://esco/x", "skill x", 0.5),
        _leaf_mapping("http://example.org/A2", "http://esco/y", "skill y", 0.5),
        # offenes RELATED-Kindmapping bleibt aussen vor
        _leaf_mapping("http://example.org/A1", "http://esco/z", "skill z", 0.33, ReviewStatus.OPEN),
    ]

    derived = derive_container_mappings(container_children, pair_mappings, concept_lookup)

    by_target = {m.object_id: m for m in derived}
    assert set(by_target) == {"http://esco/x", "http://esco/y"}
    # Container ist weiter als das Hub-Zielkonzept -> Subjekt weiter -> narrowMatch
    # (W3C SKOS / Kap. 2), analog zu RelationType.A_SUBSUMES_B.
    assert by_target["http://esco/x"].predicate_id == "skos:narrowMatch"
    assert by_target["http://esco/x"].mapping_confidence == 0.75  # Mittel aus 1.0 und 0.5
    assert by_target["http://esco/x"].mapping_justification == MappingJustification.LOGICAL_REASONING
    assert by_target["http://esco/x"].subject_id == "http://example.org/PLAN"
    assert by_target["http://esco/y"].mapping_confidence == 0.5


def test_derive_container_mappings_skips_already_derived():
    container_children = {"http://example.org/PLAN": ["http://example.org/A1"]}
    concept_lookup = {"http://example.org/PLAN": {"pref_label": "PLAN", "kqr_id": "ecf"}}
    pair_mappings = [_leaf_mapping("http://example.org/A1", "http://esco/x", "skill x", 1.0)]

    derived = derive_container_mappings(
        container_children, pair_mappings, concept_lookup,
        already_derived_subjects={"http://example.org/PLAN"},
    )
    assert derived == []


def test_find_candidate_pairs_ranks_by_similarity():
    embeddings_a = {"a1": np.array([1.0, 0.0]), "a2": np.array([0.0, 1.0])}
    embeddings_b = {
        "b1": np.array([0.9, 0.1]),
        "b2": np.array([0.0, 0.9]),
        "b3": np.array([-1.0, 0.0]),
    }

    pairs = find_candidate_pairs(embeddings_a, embeddings_b, top_k=1)

    assert len(pairs) == 2
    a1_pair = next(p for p in pairs if p.concept_a == "a1")
    assert a1_pair.concept_b == "b1"


def test_find_candidate_pairs_empty_input_returns_empty_list():
    assert find_candidate_pairs({}, {"b1": np.array([1.0])}, top_k=5) == []
    assert find_candidate_pairs({"a1": np.array([1.0])}, {}, top_k=5) == []


def test_find_structural_shortcuts_detects_known_cross_reference(hub_ttl, satellite_ttl):
    hub_graph = Graph()
    hub_graph.parse(data=hub_ttl, format="turtle")
    satellite_graph = Graph()
    satellite_graph.parse(data=satellite_ttl, format="turtle")
    merged = hub_graph + satellite_graph

    hub_concepts = parse_concepts(hub_ttl, "hub_kqr")
    satellite_concepts = parse_concepts(satellite_ttl, "satellite_kqr")
    concept_lookup = {
        c.uri: {"pref_label": c.pref_label, "kqr_id": c.kqr_id}
        for c in [*hub_concepts, *satellite_concepts]
    }

    mappings = find_structural_shortcuts(merged, concept_lookup)

    assert len(mappings) == 1
    mapping = mappings[0]
    assert mapping.subject_id.endswith("level_5")
    assert mapping.object_id.endswith("eqf_level_6")
    assert mapping.predicate_id == "skos:broadMatch"
    assert mapping.mapping_confidence == 1.0
    assert mapping.mapping_justification == MappingJustification.STRUCTURAL_MATCHING
    assert mapping.mapping_source == "algorithmic"


def test_find_structural_shortcuts_no_matches_returns_empty_list(hub_ttl):
    hub_graph = Graph()
    hub_graph.parse(data=hub_ttl, format="turtle")
    hub_concepts = parse_concepts(hub_ttl, "hub_kqr")
    concept_lookup = {c.uri: {"pref_label": c.pref_label, "kqr_id": c.kqr_id} for c in hub_concepts}

    assert find_structural_shortcuts(hub_graph, concept_lookup) == []


def test_is_occupation_uri_detects_esco_occupation():
    from app.pipeline.step2_embedding_prefilter.prefilter import is_occupation_uri
    assert is_occupation_uri(
        "http://data.europa.eu/esco/occupation/0464b062-cea6-4164-b10d-956c61956ae7"
    ) is True


def test_is_occupation_uri_returns_false_for_skill():
    from app.pipeline.step2_embedding_prefilter.prefilter import is_occupation_uri
    assert is_occupation_uri(
        "http://data.europa.eu/esco/skill/0d4471ae-3820-4c23-8566-f44a7bd159b2"
    ) is False


def test_is_occupation_uri_returns_false_for_non_esco_uri():
    from app.pipeline.step2_embedding_prefilter.prefilter import is_occupation_uri
    assert is_occupation_uri("http://hr-qde.org/harmonised/ecf/B.1") is False


def test_exclude_occupation_embeddings_removes_occupations_retains_skills():
    import numpy as np
    from app.pipeline.step2_embedding_prefilter.prefilter import exclude_occupation_embeddings

    occupation_uri = "http://data.europa.eu/esco/occupation/aaaaaaaa-0000-0000-0000-000000000001"
    skill_uri_a   = "http://data.europa.eu/esco/skill/bbbbbbbb-0000-0000-0000-000000000001"
    skill_uri_b   = "http://data.europa.eu/esco/skill/cccccccc-0000-0000-0000-000000000002"
    ecf_uri       = "http://hr-qde.org/harmonised/ecf/B.1"

    embeddings = {
        occupation_uri: np.array([1.0, 0.0]),
        skill_uri_a:    np.array([0.0, 1.0]),
        skill_uri_b:    np.array([0.5, 0.5]),
        ecf_uri:        np.array([0.3, 0.7]),
    }

    result = exclude_occupation_embeddings(embeddings)

    assert occupation_uri not in result, "Occupation-URI muss entfernt worden sein"
    assert skill_uri_a in result
    assert skill_uri_b in result
    assert ecf_uri in result
    assert len(result) == 3

    # Eingabe-Dict darf nicht verändert worden sein (kein in-place-Filter)
    assert occupation_uri in embeddings
