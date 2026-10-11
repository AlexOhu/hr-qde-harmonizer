"""
Vier Granularitaets-Varianten EQF/DQR (scripts/22_build_eqf_dqr_granularity_variants.py):

  eqf_1D.ttl  8   dqr_1D.ttl  8
  eqf_2D.ttl  32  dqr_2D.ttl  40

data/formalized ist Laufzeitdatenbestand (.gitignore't in Worktrees); fehlt
eine Datei, wird der jeweilige Test uebersprungen.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.namespace import OWL, SKOS

FORMALIZED = Path(__file__).resolve().parents[1] / "data" / "formalized"

HARM = Namespace("http://hr-qde.org/harmonised/")
EQF = Namespace("http://data.europa.eu/snb/eqf/")
# Namespace-Revision 2026-09-06: DQR-Konzept-URIs auf die harmonisierte
# Source-Basis umgestellt; owl:sameAs bruecken je Konzept auf die
# data.bmbf.de-Autoritaets-URI.
DQR = Namespace("http://hr-qde.org/harmonised/source/dqr/")
DQR_AUTHORITY = Namespace("http://data.bmbf.de/dqr/")

VARIANTS = {
    "eqf_1D.ttl": {"count": 8, "kqr": HARM.kqr_eqf},
    "eqf_2D.ttl": {"count": 32, "kqr": HARM.kqr_eqf},
    "dqr_1D.ttl": {"count": 8, "kqr": HARM.kqr_dqr},
    "dqr_2D.ttl": {"count": 40, "kqr": HARM.kqr_dqr},
}


def _graph(name: str) -> Graph:
    path = FORMALIZED / name
    if not path.exists():
        pytest.skip(f"{name} nicht vorhanden")
    g = Graph()
    g.parse(data=path.read_text(encoding="utf-8"), format="turtle")
    return g


@pytest.mark.parametrize("name", list(VARIANTS))
def test_concept_count(name: str) -> None:
    g = _graph(name)
    assert len(list(g.subjects(RDF.type, SKOS.Concept))) == VARIANTS[name]["count"]


@pytest.mark.parametrize("name", list(VARIANTS))
def test_every_concept_is_level_concept_with_iri_provenance(name: str) -> None:
    g = _graph(name)
    kqr = VARIANTS[name]["kqr"]
    for c in g.subjects(RDF.type, SKOS.Concept):
        assert (c, RDF.type, HARM.LevelConcept) in g, c
        df = list(g.objects(c, HARM.derivedFrom))
        assert df == [kqr], (c, df)
        assert all(isinstance(o, URIRef) for o in df), c
        assert list(g.objects(c, HARM.sourceIdentifier)), c


@pytest.mark.parametrize("name", list(VARIANTS))
def test_source_identifier_is_local_name(name: str) -> None:
    g = _graph(name)
    for c in g.subjects(RDF.type, SKOS.Concept):
        local = str(c).rsplit("/", 1)[-1]
        assert [str(o) for o in g.objects(c, HARM.sourceIdentifier)] == [local], c


@pytest.mark.parametrize("name", list(VARIANTS))
def test_bilingual_pref_labels(name: str) -> None:
    g = _graph(name)
    for c in g.subjects(RDF.type, SKOS.Concept):
        langs = {getattr(l, "language", None) for l in g.objects(c, SKOS.prefLabel)}
        assert {"de", "en"} <= langs, (c, langs)


def test_dqr_concepts_bridge_to_authority_uri() -> None:
    # Namespace-Revision 2026-09-06: jeder DQR-Konzeptknoten traegt genau
    # ein owl:sameAs auf die gleichnamige data.bmbf.de-Autoritaets-URI.
    for name in ("dqr_1D.ttl", "dqr_2D.ttl"):
        g = _graph(name)
        for c in g.subjects(RDF.type, SKOS.Concept):
            assert str(c).startswith(str(DQR)), c
            local = str(c).rsplit("/", 1)[-1]
            assert list(g.objects(c, OWL.sameAs)) == [DQR_AUTHORITY[local]], c


def test_eqf_variants_carry_no_dimension_mappings() -> None:
    # EQF bleibt reiner Referenzrahmen: einzige ausgehende Kante ist die
    # 1:1-Niveaukalibrierung skos:exactMatch harm-dqr:L{n}.
    for name in ("eqf_1D.ttl", "eqf_2D.ttl"):
        g = _graph(name)
        for _, p, o in g.triples((None, None, None)):
            if p in (SKOS.exactMatch, SKOS.closeMatch, SKOS.broadMatch,
                     SKOS.narrowMatch, SKOS.relatedMatch):
                assert p == SKOS.exactMatch and str(o).startswith(str(DQR)), (name, p, o)
                assert str(o).rsplit("/", 1)[-1] in {f"L{n}" for n in range(1, 9)}, o


@pytest.mark.parametrize("n", [1, 5, 8])
def test_dqr_1D_level_crosswalk(n: int) -> None:
    g = _graph("dqr_1D.ttl")
    assert (DQR[f"L{n}"], SKOS.exactMatch, EQF[f"Level{n}"]) in g


@pytest.mark.parametrize("n", [1, 4, 8])
def test_dqr_2D_dimension_crosswalk_matches_g_struct(n: int) -> None:
    g = _graph("dqr_2D.ttl")
    assert (DQR[f"L{n}"], SKOS.exactMatch, EQF[f"Level{n}"]) in g
    assert (DQR[f"L{n}_Knowledge"], SKOS.exactMatch, EQF[f"L{n}_Knowledge"]) in g
    assert (DQR[f"L{n}_Skills"], SKOS.exactMatch, EQF[f"L{n}_Skills"]) in g
    assert (DQR[f"L{n}_SocialCompetence"], SKOS.narrowMatch,
            EQF[f"L{n}_ResponsibilityAutonomy"]) in g
    assert (DQR[f"L{n}_Autonomy"], SKOS.narrowMatch,
            EQF[f"L{n}_ResponsibilityAutonomy"]) in g


def test_2D_reproduces_g_struct_natively() -> None:
    import json

    gs_path = Path(__file__).resolve().parents[1] / "eval" / "G_struct.json"
    if not gs_path.exists():
        pytest.skip("eval/G_struct.json nicht vorhanden")
    g = Graph()
    for name in ("eqf_2D.ttl", "dqr_2D.ttl"):
        path = FORMALIZED / name
        if not path.exists():
            pytest.skip(f"{name} nicht vorhanden")
        g.parse(data=path.read_text(encoding="utf-8"), format="turtle")
    pred = {"skos:exactMatch": SKOS.exactMatch, "skos:narrowMatch": SKOS.narrowMatch}
    for pair in json.loads(gs_path.read_text(encoding="utf-8"))["pairs"]:
        s, o = URIRef(pair["subject_id"]), URIRef(pair["object_id"])
        assert (s, RDF.type, SKOS.Concept) in g, s
        assert (o, RDF.type, SKOS.Concept) in g, o
        assert (s, pred[pair["predicate"]], o) in g, (s, pair["predicate"], o)


@pytest.mark.parametrize("name", ["eqf_2D.ttl", "dqr_2D.ttl"])
def test_fine_variant_facets_link_to_their_level(name: str) -> None:
    g = _graph(name)
    for facet in g.subjects(RDF.type, SKOS.Concept):
        local = str(facet).rsplit("/", 1)[-1]
        if "_" not in local:
            continue  # Niveauknoten
        parents = list(g.objects(facet, SKOS.broader))
        assert len(parents) == 1, (facet, parents)
        parent_local = str(parents[0]).rsplit("/", 1)[-1]
        facet_level = local.split("_", 1)[0]  # "L1" bei DQR, "L1" bei EQF-Facette
        # EQF-Niveauknoten heissen "Level1", DQR-Niveauknoten "L1".
        assert parent_local in (facet_level, facet_level.replace("L", "Level")), (
            facet,
            parent_local,
        )
