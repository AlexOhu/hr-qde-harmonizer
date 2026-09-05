"""Tests fuer die drei Saeule-D-Lieferartefakte
(``app/pipeline/step4_export/saeule_d_delivery.py``).

Kernkriterium: die erzeugten TTL validieren gegen die kanonischen
Bezugsdokumente ``hrqde-shape-harmonisation.ttl`` und
``hrqde-harmonisation-schema.ttl`` (Adrian Vogler, v0.2.0) mit 0 Violations.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from rdflib import RDF, Graph, Namespace, URIRef

from app.models.schemas import (
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
harm:CompetenceConcept a owl:NamedIndividual .
ecf: a skos:ConceptScheme .
ecf:plan a skos:Concept ; skos:prefLabel "PLAN"@en, "PLANEN"@de ;
    hrqde:sourceIdentifier "A" ; skos:broader ecf: .
ecf:A.1 a skos:Concept ; skos:prefLabel "IS Strategy"@en, "IS-Strategie"@de ;
    skos:definition "def a1"@en ; hrqde:sourceIdentifier "A.1" ;
    hrqde:proficiencyLevel "e-3", "e-4" ;
    harm:conceptRole harm:CompetenceConcept ; skos:broader ecf:plan .
ecf:A.2 a skos:Concept ; skos:prefLabel "Service Levels"@en ;
    hrqde:sourceIdentifier "A.2" ; hrqde:proficiencyLevel "e-1" ;
    harm:conceptRole harm:CompetenceConcept ; skos:broader ecf:plan .
ecf:A.3 a skos:Concept ; skos:prefLabel "Business Plan Development"@en ;
    hrqde:sourceIdentifier "A.3" ;
    harm:conceptRole harm:CompetenceConcept ; skos:broader ecf:plan .
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


# --- _delivery_uri (Spec Abschnitt 7, URI-Muster) -----------------------

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


# --- generate_level_mappings_from_ecf (nur narrativ, ADR-24) -------------

def test_ecf_crosswalk_e3_expands_to_two_targets():
    rows = generate_level_mappings_from_ecf(_g(_ECF_TTL))
    # A.1: e-3 -> EQF5+EQF6, e-4 -> EQF7 ; A.2: e-1 -> EQF3  => 4
    assert len(rows) == 4
    a1_e3 = [r for r in rows if r.proficiency_level == "e-3"]
    assert {r.object_id.rsplit("/", 1)[-1] for r in a1_e3} == {"5", "6"}
    assert all(r.object_id.startswith("http://data.europa.eu/snb/qf-eu-level/") for r in rows)


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

    # Liefer-URI traegt das source/-Segment (Spec Abschnitt 7); die interne
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
    # subject_id traegt die Liefer-URI (source/-Segment, Spec Abschnitt 7)
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
    assert "CEN-EN-16234-1-Crosswalk" in md
    assert "e-3" in md and "EQF 5" in md and "EQF 6" in md
    assert "1191 offene Reviews" in md


# --- Kanonische SHACL-Validierung (Spec Abschnitt 8) ----------------

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
