"""Tests fuer die drei Saeule-D-Lieferartefakte
(``app/pipeline/step4_export/saeule_d_delivery.py``).

Kernkriterium: die erzeugten TTL validieren gegen die kanonischen
Bezugsdokumente ``hrqde-shape-harmonisation.ttl`` und
``hrqde-harmonisation-schema.ttl`` (Adrian Vogler, v0.2.0) mit 0 Violations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from rdflib import DCTERMS, RDF, Graph, Literal, Namespace, URIRef

from app.models.schemas import (
    DisjointConceptDecision,
    DisjointStrategy,
    Mapping,
    MappingJustification,
    ReviewStatus,
)
from app.pipeline.step4_export.saeule_d_delivery import (
    _delivery_uri,
    dqr_eqf_level_mappings,
    generate_level_mappings_from_ecf,
    write_delivery,
    write_integration_strategy,
    write_mappings,
    write_ontology,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
HARM = Namespace("http://hr-qde.org/harmonised/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
SSSOM = Namespace("https://w3id.org/sssom/")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")

# e-CF-artig: Bereiche als Container (Kind via skos:broader), Blaetter mit
# Provenienz-Feldern im Platzhalter-NS der Formalisierung.
_ECF_TTL = """
@prefix skos:  <http://www.w3.org/2004/02/skos/core#> .
@prefix owl:   <http://www.w3.org/2002/07/owl#> .
@prefix hrqde: <https://hrqde.example.org/ontology#> .
@prefix harm:  <http://hr-qde.org/harmonised/> .
@prefix ecf:   <http://hr-qde.org/harmonised/ecf/> .
@prefix harm-ecf: <http://hr-qde.org/harmonised/source/ecf/> .
@prefix dqr:   <http://hr-qde.org/harmonised/source/dqr/> .
harm:CompetenceConcept a owl:NamedIndividual .
ecf: a skos:ConceptScheme .
ecf:plan a skos:Concept ; skos:prefLabel "PLAN"@en, "PLANEN"@de ;
    hrqde:sourceIdentifier "A" ; skos:broader ecf: .
ecf:A.1 a skos:Concept ; skos:prefLabel "IS Strategy"@en, "IS-Strategie"@de ;
    skos:definition "def a1"@en ; hrqde:sourceIdentifier "A.1" ;
    a harm:CompetenceConcept ;
    harm:hasLevel harm-ecf:A.1.Niveau3, harm-ecf:A.1.Niveau4 ;
    skos:broader ecf:plan .
ecf:A.2 a skos:Concept ; skos:prefLabel "Service Levels"@en ;
    hrqde:sourceIdentifier "A.2" ; a harm:CompetenceConcept ;
    harm:hasLevel harm-ecf:A.2.Niveau1 ; skos:broader ecf:plan .
ecf:A.3 a skos:Concept ; skos:prefLabel "Business Plan Development"@en ;
    hrqde:sourceIdentifier "A.3" ;
    a harm:CompetenceConcept ; skos:broader ecf:plan .

harm-ecf:A.1.Niveau3 a skos:Concept, harm:LevelConcept ;
    hrqde:sourceIdentifier "A.1 Niveau 3" ; skos:prefLabel "A.1 proficiency 3"@en ;
    harm:eqfCrosswalkTarget dqr:L5 .
harm-ecf:A.1.Niveau4 a skos:Concept, harm:LevelConcept ;
    hrqde:sourceIdentifier "A.1 Niveau 4" ; skos:prefLabel "A.1 proficiency 4"@en ;
    harm:eqfCrosswalkTarget dqr:L7 .
harm-ecf:A.2.Niveau1 a skos:Concept, harm:LevelConcept ;
    hrqde:sourceIdentifier "A.2 Niveau 1" ; skos:prefLabel "A.2 proficiency 1"@en ;
    harm:eqfCrosswalkTarget dqr:L3 .
"""

_ESCO_SKILL_A = "http://data.europa.eu/esco/skill/000f1d3d-220f-4789-9c0a-cc742521fb02"
_ESCO_SKILL_B = "http://data.europa.eu/esco/skill/00c04e40-35ea-4ed1-824c-82f936c8f876"


def _g(ttl: str) -> Graph:
    graph = Graph()
    graph.parse(data=ttl, format="turtle")
    return graph


def _k_mappings() -> list[Mapping]:
    return [
        Mapping(
            subject_id="http://hr-qde.org/harmonised/ecf/A.1", subject_label="IS Strategy",
            subject_kqr_id="ecf",
            object_id=_ESCO_SKILL_A, object_label="skill a",
            object_kqr_id="esco_skeleton_oberhuber",
            predicate_id="skos:narrowMatch", mapping_confidence=0.91,
            mapping_justification=MappingJustification.LLM_BASED_MATCHING,
            review_status=ReviewStatus.CONJUNCT,
        ),
        Mapping(
            subject_id="http://hr-qde.org/harmonised/ecf/A.2", subject_label="Service Levels",
            subject_kqr_id="ecf",
            object_id=_ESCO_SKILL_B, object_label="skill b",
            object_kqr_id="esco_skeleton_oberhuber",
            predicate_id="skos:relatedMatch", mapping_confidence=1.0,
            mapping_justification=MappingJustification.LLM_BASED_MATCHING,
            review_status=ReviewStatus.OPEN,
        ),
    ]


# --- _delivery_uri (URI-Muster) -----------------------

def test_delivery_uri_adds_source_segment_for_satellite_concepts():
    assert _delivery_uri("http://hr-qde.org/harmonised/ecf/A.1") == URIRef(
        "http://hr-qde.org/harmonised/source/ecf/A.1"
    )
    # bereits im Liefer-Schema -> idempotent
    assert _delivery_uri("http://hr-qde.org/harmonised/source/ecf/A.1") == URIRef(
        "http://hr-qde.org/harmonised/source/ecf/A.1"
    )


def test_delivery_uri_leaves_non_source_harm_uris_unchanged():
    # KQR-Entitaeten, Mapping-/Levelmapping-/MappingSet-Individuen tragen
    # keine {rahmen}/{kennung}-Struktur eines Satelliten-Rahmens
    for uri in (
        "http://hr-qde.org/harmonised/kqr_ecf",
        "http://hr-qde.org/harmonised/mapping/abc-123",
        "http://hr-qde.org/harmonised/levelmapping/DQR1__EQF1",
        "http://hr-qde.org/harmonised/mappingset/oberhuber-v0.2",
    ):
        assert _delivery_uri(uri) == URIRef(uri)


def test_delivery_uri_leaves_non_harm_uris_unchanged():
    # ESCO-Skills/Berufe und Skelett-Niveauknoten werden nie umgeschrieben
    assert _delivery_uri(_ESCO_SKILL_A) == URIRef(_ESCO_SKILL_A)
    assert _delivery_uri("http://hr-qde.org/ontology/DQR1") == URIRef(
        "http://hr-qde.org/ontology/DQR1"
    )


# --- generate_level_mappings_from_ecf (kanonische LevelMappings) ---------

def test_ecf_crosswalk_e3_expands_to_two_targets():
    rows = generate_level_mappings_from_ecf(_g(_ECF_TTL))
    assert len(rows) == 3
    assert {r.object_id.rsplit("/", 1)[-1] for r in rows} == {"L3", "L5", "L7"}
    assert all(r.predicate_id == "skos:closeMatch" for r in rows)
    assert all(r.object_id.startswith("http://hr-qde.org/harmonised/source/dqr/") for r in rows)


def test_dqr_eqf_level_mappings_are_skeleton_to_authority():
    lms = dqr_eqf_level_mappings()
    assert len(lms) == 8
    assert lms[0].subject_id == "http://hr-qde.org/ontology/DQR1"
    assert lms[7].object_id == "http://data.europa.eu/snb/qf-eu-level/8"
    assert all(lm.predicate_id == "skos:exactMatch" for lm in lms)
    assert all(lm.mapping_confidence == Decimal("1.0") for lm in lms)


# --- Artefakt 1: Ontologie ---------------------------------------------

def test_ontology_has_no_minted_level_nodes(tmp_path):
    stats = write_ontology(tmp_path, _g(_ECF_TTL), _k_mappings(), [], version="0.2")
    out = Graph()
    out.parse(stats["path"], format="turtle")
    text = Path(stats["path"]).read_text(encoding="utf-8")

    assert "harm:EQFLevel" not in text and "harm:DQRLevel" not in text
    assert "mappingTarget" not in text
    # keine ESCO-Knoten im Ontologie-Artefakt
    assert "data.europa.eu/esco" not in text
    # keine Mappings
    assert (None, RDF.type, SSSOM.Mapping) not in out
    assert (None, RDF.type, HARM.HubMapping) not in out


def test_ontology_concept_provenance(tmp_path):
    stats = write_ontology(tmp_path, _g(_ECF_TTL), _k_mappings(), [], version="0.2")
    out = Graph()
    out.parse(stats["path"], format="turtle")

    # Liefer-URI traegt das source/-Segment; die interne
    # Pipeline-URI (ohne source/) taucht im Artefakt nicht mehr auf.
    a1 = URIRef("http://hr-qde.org/harmonised/source/ecf/A.1")
    assert (a1, HARM.derivedFrom, HARM.kqr_ecf) in out
    assert (URIRef("http://hr-qde.org/harmonised/ecf/A.1"), HARM.derivedFrom, None) not in out
    assert (a1, HARM.sourceIdentifier, None) not in out or any(
        str(o) == "A.1" for o in out.objects(a1, HARM.sourceIdentifier)
    )
    assert list(out.objects(a1, HARM.sourceIdentifier)) == [
        next(iter(out.objects(a1, HARM.sourceIdentifier)))
    ]
    # KQR-Entitaeten sind keine Quellkonzepte und bleiben unveraendert
    assert (HARM.kqr_ecf, RDF.type, HARM.KQR) in out


def test_ontology_disjoint_concepts_carry_strategy_and_comment(tmp_path):
    stats = write_ontology(tmp_path, _g(_ECF_TTL), _k_mappings(), [], version="0.2")
    out = Graph()
    out.parse(stats["path"], format="turtle")

    # A.1 ist ueber ein CONJUNCT-Mapping verankert -> kein HarmonisedConcept
    a1 = URIRef("http://hr-qde.org/harmonised/source/ecf/A.1")
    assert (a1, RDF.type, HARM.HarmonisedConcept) not in out
    # A.2 (nur OPEN) und A.3 (kein Mapping) -> HarmonisedConcept
    for local in ("A.2", "A.3"):
        node = URIRef(f"http://hr-qde.org/harmonised/source/ecf/{local}")
        assert (node, RDF.type, HARM.HarmonisedConcept) in out
        assert list(out.objects(node, HARM.integrationStrategy)) == [
            next(iter(out.objects(node, HARM.integrationStrategy)))
        ]
        assert any(out.objects(node, URIRef("http://www.w3.org/2000/01/rdf-schema#comment")))
    assert stats["harmonised_concepts"] == 2


def test_ontology_disjoint_decision_exports_creator_and_created(tmp_path):
    created_at = datetime(2026, 10, 10, 12, 30, tzinfo=timezone.utc)
    decision = DisjointConceptDecision(
        concept_id="http://hr-qde.org/harmonised/ecf/A.2",
        concept_label="Service Levels",
        kqr_id="ecf",
        strategy=DisjointStrategy.OWN_CLASS,
        justification="No corresponding ESCO concept was identified.",
        author="Alex",
        created_at=created_at,
    )

    stats = write_ontology(
        tmp_path, _g(_ECF_TTL), _k_mappings(), [decision], version="0.2"
    )
    out = Graph()
    out.parse(stats["path"], format="turtle")

    concept = URIRef("http://hr-qde.org/harmonised/source/ecf/A.2")
    assert (concept, DCTERMS.creator, Literal("Alex")) in out
    assert (concept, DCTERMS.created, Literal(created_at)) in out

    pyshacl = pytest.importorskip("pyshacl")
    conforms, _, report = pyshacl.validate(
        out,
        shacl_graph=str(REPO_ROOT / "hrqde-shape-harmonisation.ttl"),
        ont_graph=str(REPO_ROOT / "hrqde-harmonisation-schema.ttl"),
        inference="rdfs",
        advanced=True,
    )
    assert conforms, report


def test_disjoint_provenance_is_optional_but_shacl_checks_its_datatypes(tmp_path):
    pyshacl = pytest.importorskip("pyshacl")
    stats = write_ontology(tmp_path, _g(_ECF_TTL), _k_mappings(), [], version="0.2")
    data = Graph().parse(stats["path"], format="turtle")
    shape = REPO_ROOT / "hrqde-shape-harmonisation.ttl"
    schema = REPO_ROOT / "hrqde-harmonisation-schema.ttl"

    conforms_without_decisions, _, _ = pyshacl.validate(
        data, shacl_graph=str(shape), ont_graph=str(schema),
        data_graph_format="turtle", shacl_graph_format="turtle",
        ont_graph_format="turtle", inference="rdfs", advanced=True,
    )
    assert conforms_without_decisions

    concept = URIRef("http://hr-qde.org/harmonised/source/ecf/A.2")
    data.add((concept, DCTERMS.creator, Literal("Alex")))
    data.add((concept, DCTERMS.created, Literal("not-a-date", datatype=XSD.string)))
    conforms_with_invalid_timestamp, _, _ = pyshacl.validate(
        data, shacl_graph=str(shape), ont_graph=str(schema),
        data_graph_format="turtle", shacl_graph_format="turtle",
        ont_graph_format="turtle", inference="rdfs", advanced=True,
    )
    assert not conforms_with_invalid_timestamp


# --- Artefakt 2: Mappings --------------------------------------------

def test_mappings_hub_records_use_iri_predicate_and_decimal(tmp_path):
    stats = write_mappings(tmp_path, _k_mappings(), version="0.2")
    out = Graph()
    out.parse(stats["path"], format="turtle")

    hub = list(out.subjects(RDF.type, HARM.HubMapping))
    assert len(hub) == 1 and stats["hub_mappings"] == 1
    rec = hub[0]
    pred = next(out.objects(rec, SSSOM.predicate_id))
    assert isinstance(pred, URIRef)
    assert str(pred) == "http://www.w3.org/2004/02/skos/core#narrowMatch"
    conf = next(out.objects(rec, SSSOM.mapping_confidence))
    assert conf.datatype == URIRef("http://www.w3.org/2001/XMLSchema#decimal")
    just = next(out.objects(rec, SSSOM.mapping_justification))
    assert str(just).startswith("https://w3id.org/semapv/")
    # subject_id traegt die Liefer-URI (source/-Segment)
    assert next(out.objects(rec, SSSOM.subject_id)) == URIRef(
        "http://hr-qde.org/harmonised/source/ecf/A.1"
    )
    # OPEN-Mapping (A.2) darf nicht auftauchen, weder unter der internen
    # noch unter der Liefer-URI
    assert not list(out.subjects(SSSOM.subject_id, URIRef("http://hr-qde.org/harmonised/ecf/A.2")))
    assert not list(
        out.subjects(SSSOM.subject_id, URIRef("http://hr-qde.org/harmonised/source/ecf/A.2"))
    )


def test_mappings_have_mappingset_and_eight_levelmappings(tmp_path):
    stats = write_mappings(tmp_path, _k_mappings(), version="0.2")
    out = Graph()
    out.parse(stats["path"], format="turtle")

    mset = list(out.subjects(RDF.type, SSSOM.MappingSet))
    assert len(mset) == 1
    assert list(out.objects(mset[0], SSSOM.mapping_set_version))
    members = set(out.objects(mset[0], SSSOM.mappings))
    lvl = list(out.subjects(RDF.type, HARM.LevelMapping))
    assert len(lvl) == 8 and stats["level_mappings"] == 8
    assert set(lvl).issubset(members)
    for rec in lvl:
        subj = str(next(out.objects(rec, SSSOM.subject_id)))
        obj = str(next(out.objects(rec, SSSOM.object_id)))
        assert subj.startswith("http://hr-qde.org/ontology/DQR")
        assert obj.startswith("http://data.europa.eu/snb/qf-eu-level/")


# --- Artefakt 3: Strategie-Doku --------------------------------------

def test_integration_strategy_markdown_contains_protocol_and_crosswalk(tmp_path):
    onto = write_ontology(tmp_path, _g(_ECF_TTL), _k_mappings(), [], version="0.2")
    maps = write_mappings(tmp_path, _k_mappings(), version="0.2")
    strat = write_integration_strategy(
        tmp_path, _g(_ECF_TTL), [], onto, maps,
        coverage={"coverage_ratio": 0.75, "open_review_count": 1},
        limitations=["1191 offene Reviews"], version="0.2",
    )
    md = Path(strat["path"]).read_text(encoding="utf-8")
    assert "Begleitprotokoll" in md
    assert "harm:HubMapping" in md and "harm:LevelMapping" in md
    assert "Niveaukette" in md
    assert "DQR L5" in md and "DQR L7" in md
    assert "1191 offene Reviews" in md
    # ohne Entscheidungen: Rueckfallstrategie offen ausgewiesen, nicht als
    # Vorschlag von suggest_strategy ausgegeben
    assert "2 von 2 disjunkten Konzepten haben keine gespeicherte" in md
    assert "Rueckfallstrategie `own_class`" in md


def _attach_decision(concept: str = "A.2", **kw) -> DisjointConceptDecision:
    return DisjointConceptDecision(
        concept_id=f"http://hr-qde.org/harmonised/ecf/{concept}",
        concept_label="Service Levels",
        kqr_id="ecf",
        strategy=DisjointStrategy.ATTACH_TO_SKELETON,
        anchor_class=kw.get("anchor_class", _ESCO_SKILL_B),
        justification=kw.get("justification", "Naehe zu skill b, keine Aequivalenz."),
        author="Alex",
        created_at=datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc),
    )


def test_ontology_comment_carries_anchor_class(tmp_path):
    stats = write_ontology(tmp_path, _g(_ECF_TTL), _k_mappings(), [_attach_decision()])
    out = Graph().parse(stats["path"], format="turtle")
    node = URIRef("http://hr-qde.org/harmonised/source/ecf/A.2")
    comment = str(next(out.objects(node, URIRef("http://www.w3.org/2000/01/rdf-schema#comment"))))
    assert comment.startswith("Naehe zu skill b")
    assert f"Ankerklasse: {_ESCO_SKILL_B}" in comment
    assert (node, HARM.integrationStrategy, Literal("attach_to_skeleton")) in out
    assert stats["harmonised_decided"] == 1
    # Ankerklasse nur als Text: keine direkte Kante auf ESCO in der Ontologie
    assert (node, None, URIRef(_ESCO_SKILL_B)) not in out


def test_decision_with_internal_uri_applies_to_delivery_namespace_leaf(tmp_path):
    """Regression: ecf_level fuehrt die Blaetter unter harm:source/ecf/...,
    Entscheidungen tragen die interne URI harm:ecf/... (wie in der UI
    gespeichert). Beide muessen als dasselbe Konzept erkannt werden."""
    ttl = _ECF_TTL.replace("ecf:A.2 a skos:Concept", "harm-ecf:A.2 a skos:Concept")
    stats = write_ontology(tmp_path, _g(ttl), _k_mappings(), [_attach_decision()])
    out = Graph().parse(stats["path"], format="turtle")
    node = URIRef("http://hr-qde.org/harmonised/source/ecf/A.2")
    assert (node, HARM.integrationStrategy, Literal("attach_to_skeleton")) in out
    assert (node, DCTERMS.creator, Literal("Alex")) in out
    assert stats["harmonised_decided"] == 1

    maps = write_mappings(tmp_path, _k_mappings())
    strat = write_integration_strategy(tmp_path, _g(ttl), [_attach_decision()], stats, maps)
    assert strat["disjoint_documented"] == 1


def test_integration_strategy_lists_only_decisions_of_harmonised_concepts(tmp_path):
    hub_decision = DisjointConceptDecision(
        concept_id=_ESCO_SKILL_A, concept_label="skill a", kqr_id="esco_skeleton_oberhuber",
        strategy=DisjointStrategy.OWN_CLASS, justification="Hub", author="Alex",
    )
    decisions = [_attach_decision(), hub_decision]
    onto = write_ontology(tmp_path, _g(_ECF_TTL), _k_mappings(), decisions)
    maps = write_mappings(tmp_path, _k_mappings())
    strat = write_integration_strategy(tmp_path, _g(_ECF_TTL), decisions, onto, maps)
    md = Path(strat["path"]).read_text(encoding="utf-8")
    assert strat["disjoint_documented"] == 1
    assert "| Ankerklasse |" in md and f"`{_ESCO_SKILL_B}`" in md
    assert _ESCO_SKILL_A not in md.split("## 2.")[1].split("## 3.")[0]
    # A.3 bleibt ohne Entscheidung
    assert "1 von 2 disjunkten Konzepten haben keine gespeicherte" in md


# --- Kanonische SHACL-Validierung ----------------

@pytest.mark.parametrize("artifact", ["ontology", "mappings"])
def test_delivery_passes_canonical_shacl(tmp_path, artifact):
    pyshacl = pytest.importorskip("pyshacl")
    shape = REPO_ROOT / "hrqde-shape-harmonisation.ttl"
    schema = REPO_ROOT / "hrqde-harmonisation-schema.ttl"
    assert shape.exists() and schema.exists(), "kanonische Bezugsdokumente fehlen im Repo-Root"

    bundle = write_delivery(tmp_path, _g(_ECF_TTL), _k_mappings(), [], version="0.2")
    data_path = bundle[artifact]["path"]

    conforms, _results_graph, results_text = pyshacl.validate(
        data_path,
        shacl_graph=str(shape),
        ont_graph=str(schema),
        data_graph_format="turtle",
        shacl_graph_format="turtle",
        ont_graph_format="turtle",
        inference="rdfs",
        advanced=True,
    )
    assert conforms, f"SHACL-Verstoesse in {artifact}:\n{results_text}"
