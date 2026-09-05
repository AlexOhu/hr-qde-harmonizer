"""
Verwendet tests/fixtures/hub_kqr.ttl als Konzeptquelle (analog
test_formalize.py), keine Netzwerk-Calls.
"""

from __future__ import annotations

import pytest
from rdflib import OWL, RDF, RDFS, SKOS, Graph, Literal, URIRef

from app.models.schemas import (
    DisjointConceptDecision,
    DisjointStrategy,
    HarmonisedCluster,
    Mapping,
    MappingJustification,
    RelationType,
    ReviewStatus,
)
from app.pipeline.step1_formalization.formalize import parse_concepts
from app.pipeline.step4_export.ontology_export import HARM, export_audit_report, export_ontology


@pytest.fixture
def concepts(hub_ttl):
    return parse_concepts(hub_ttl, "hub_kqr")


def _concept(concepts, local_name):
    return next(c for c in concepts if c.uri.endswith(local_name))


@pytest.fixture
def sample_mappings(concepts):
    programming = _concept(concepts, "programming")
    project_management = _concept(concepts, "project_management")
    return [
        Mapping(
            subject_id=programming.uri,
            subject_label=programming.pref_label,
            subject_kqr_id="hub_kqr",
            object_id=project_management.uri,
            object_label=project_management.pref_label,
            object_kqr_id="hub_kqr",
            predicate_id=RelationType.EQUIVALENT.to_skos_predicate(),
            mapping_confidence=0.9,
            mapping_justification=MappingJustification.LLM_BASED_MATCHING,
            mapping_source="algorithmic",
        )
    ]


@pytest.fixture
def sample_clusters(concepts):
    programming = _concept(concepts, "programming")
    project_management = _concept(concepts, "project_management")
    communication = _concept(concepts, "communication")
    teamwork = _concept(concepts, "teamwork")
    return [
        HarmonisedCluster(
            cluster_uri="http://hr-qde.org/harmonised/cluster/0",
            label="Technical Skills",
            parent_cluster_uri=None,
            member_uris=[programming.uri, project_management.uri],
        ),
        HarmonisedCluster(
            cluster_uri="http://hr-qde.org/harmonised/cluster/1",
            label="Soft Skills",
            parent_cluster_uri="http://hr-qde.org/harmonised/cluster/0",
            member_uris=[communication.uri, teamwork.uri],
        ),
    ]


@pytest.fixture
def sample_disjoint_decisions(concepts):
    communication = _concept(concepts, "communication")
    return [
        DisjointConceptDecision(
            concept_id=communication.uri,
            concept_label=communication.pref_label,
            kqr_id="hub_kqr",
            strategy=DisjointStrategy.OWN_CLASS,
            justification="Kein ESCO-Pendant gefunden.",
            author="Alex",
        )
    ]


def test_export_ontology_produces_valid_turtle(tmp_path, sample_mappings, sample_clusters, sample_disjoint_decisions):
    output_path = tmp_path / "ontology.ttl"
    export_ontology(sample_mappings, sample_clusters, sample_disjoint_decisions, "turtle", output_path)

    graph = Graph()
    graph.parse(str(output_path), format="turtle")  # wirft bei ungültigem Turtle
    assert len(graph) > 0


def test_export_ontology_all_cluster_uris_are_owl_classes(tmp_path, sample_mappings, sample_clusters, sample_disjoint_decisions):
    output_path = tmp_path / "ontology.ttl"
    export_ontology(sample_mappings, sample_clusters, sample_disjoint_decisions, "turtle", output_path)

    graph = Graph()
    graph.parse(str(output_path), format="turtle")

    for cluster in sample_clusters:
        assert (URIRef(cluster.cluster_uri), RDF.type, OWL.Class) in graph


def test_export_ontology_subclassof_matches_input_dag(tmp_path, sample_mappings, sample_clusters, sample_disjoint_decisions):
    output_path = tmp_path / "ontology.ttl"
    export_ontology(sample_mappings, sample_clusters, sample_disjoint_decisions, "turtle", output_path)

    graph = Graph()
    graph.parse(str(output_path), format="turtle")

    root_cluster, child_cluster = sample_clusters
    assert (URIRef(child_cluster.cluster_uri), RDFS.subClassOf, URIRef(root_cluster.cluster_uri)) in graph
    assert (URIRef(root_cluster.cluster_uri), RDFS.subClassOf, None) not in graph


def test_export_ontology_mapped_concepts_have_preflabel_and_type(tmp_path, sample_mappings, sample_clusters, sample_disjoint_decisions):
    output_path = tmp_path / "ontology.ttl"
    export_ontology(sample_mappings, sample_clusters, sample_disjoint_decisions, "turtle", output_path)

    graph = Graph()
    graph.parse(str(output_path), format="turtle")

    mapping = sample_mappings[0]
    subject_ref = URIRef(mapping.subject_id)
    assert (subject_ref, RDF.type, SKOS.Concept) in graph
    assert (subject_ref, SKOS.prefLabel, Literal(mapping.subject_label, lang="en")) in graph


def test_export_ontology_disjoint_decision_has_integration_strategy(tmp_path, sample_mappings, sample_clusters, sample_disjoint_decisions):
    output_path = tmp_path / "ontology.ttl"
    export_ontology(sample_mappings, sample_clusters, sample_disjoint_decisions, "turtle", output_path)

    graph = Graph()
    graph.parse(str(output_path), format="turtle")

    decision = sample_disjoint_decisions[0]
    concept_ref = URIRef(decision.concept_id)
    assert (concept_ref, RDF.type, HARM.HarmonisedConcept) in graph
    assert (concept_ref, HARM.integrationStrategy, Literal(decision.strategy.value)) in graph


def test_export_ontology_mapped_concepts_are_not_typed_as_harmonised_concept(
    tmp_path, sample_mappings, sample_clusters, sample_disjoint_decisions
):
    """Konzepte der konjunkten Menge K dürfen nicht den Typ
    hrqde:HarmonisedConcept tragen. Dieser Typ ist ausschließlich
    disjunkten Konzepten vorbehalten (Tabelle 3.13)."""
    output_path = tmp_path / "ontology.ttl"
    export_ontology(
        sample_mappings, sample_clusters, sample_disjoint_decisions, "turtle", output_path
    )

    graph = Graph()
    graph.parse(str(output_path), format="turtle")

    for mapping in sample_mappings:
        for concept_uri in (mapping.subject_id, mapping.object_id):
            assert (URIRef(concept_uri), RDF.type, HARM.HarmonisedConcept) not in graph, (
                f"{concept_uri} ist ein konjunktes Konzept (Menge K) und darf "
                f"nicht als hrqde:HarmonisedConcept typisiert sein."
            )


def test_export_audit_report_has_three_required_sections(tmp_path, sample_mappings):
    output_path = tmp_path / "audit.md"
    unresolved = [
        Mapping(
            subject_id="http://example.org/a",
            subject_label="A",
            object_id="http://example.org/b",
            object_label="B",
            predicate_id=None,
            mapping_confidence=0.2,
            mapping_justification=MappingJustification.LLM_BASED_MATCHING,
            mapping_source="algorithmic",
            review_status=ReviewStatus.OPEN,
            justification="Kein Mehrheitsentscheid",
        )
    ]

    export_audit_report(sample_mappings, unresolved, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "Automatische Mappings" in content
    assert "Manuell bestätigte" in content
    assert "ohne LLM-Mehrheitsentscheid" in content
    assert "Kein Mehrheitsentscheid" in content


def test_export_audit_report_lists_manual_mappings(tmp_path, sample_mappings):
    manual_mapping = sample_mappings[0].model_copy(
        update={"mapping_source": "manual", "author": "Alex", "justification": "Manuell bestätigt"}
    )
    output_path = tmp_path / "audit.md"

    export_audit_report([manual_mapping], [], output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "Alex" in content
    assert "Manuell bestätigt" in content


@pytest.mark.parametrize("fmt", ["xml", "json-ld"])
def test_export_ontology_other_formats_do_not_raise(tmp_path, sample_mappings, sample_clusters, sample_disjoint_decisions, fmt):
    output_path = tmp_path / f"ontology.{fmt}"
    result_path = export_ontology(sample_mappings, sample_clusters, sample_disjoint_decisions, fmt, output_path)
    assert result_path.exists()
