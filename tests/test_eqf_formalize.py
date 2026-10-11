"""
EQF-Reformalisierung auf harm:-Vokabular (scripts/21_eqf_harm_migration.py).

Prueft data/formalized/eqf_2017.ttl gegen die in der Migration zugesagten
Invarianten. Die Datei ist Laufzeitdatenbestand (data/formalized ist in
Worktrees .gitignore't); fehlt sie, wird der Test uebersprungen statt zu
scheitern.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.namespace import SKOS

EQF_TTL = Path(__file__).resolve().parents[1] / "data" / "formalized" / "eqf_2017.ttl"

HARM = Namespace("http://hr-qde.org/harmonised/")
EQF = Namespace("http://data.europa.eu/snb/eqf/")
DQR = Namespace("http://data.bmbf.de/dqr/")

pytestmark = pytest.mark.skipif(
    not EQF_TTL.exists(), reason="data/formalized/eqf_2017.ttl nicht vorhanden"
)


@pytest.fixture(scope="module")
def graph() -> Graph:
    g = Graph()
    g.parse(
        data=EQF_TTL.read_text(encoding="utf-8").replace("\r\n", "\n"),
        format="turtle",
    )
    return g


@pytest.fixture(scope="module")
def concepts(graph: Graph) -> list[URIRef]:
    return list(graph.subjects(RDF.type, SKOS.Concept))


def test_exactly_32_concepts(concepts: list[URIRef]) -> None:
    assert len(concepts) == 32


def test_all_concepts_are_level_concepts(graph: Graph, concepts: list[URIRef]) -> None:
    for c in concepts:
        assert (c, RDF.type, HARM.LevelConcept) in graph, c


def test_derived_from_kqr_eqf_as_uriref(graph: Graph, concepts: list[URIRef]) -> None:
    for c in concepts:
        objs = list(graph.objects(c, HARM.derivedFrom))
        assert objs == [HARM.kqr_eqf], (c, objs)
        # ADR-15-Fehler bei den Alt-DQR-Dateien war ein Literal statt IRI.
        assert all(isinstance(o, URIRef) for o in objs), c


def test_source_identifier_is_local_name(graph: Graph, concepts: list[URIRef]) -> None:
    for c in concepts:
        local = str(c).rsplit("/", 1)[-1]
        idents = [str(o) for o in graph.objects(c, HARM.sourceIdentifier)]
        assert idents == [local], (c, idents)


def test_bilingual_pref_labels(graph: Graph, concepts: list[URIRef]) -> None:
    for c in concepts:
        langs = {getattr(l, "language", None) for l in graph.objects(c, SKOS.prefLabel)}
        assert {"de", "en"} <= langs, (c, langs)


def test_bilingual_definitions(graph: Graph, concepts: list[URIRef]) -> None:
    for c in concepts:
        langs = {getattr(l, "language", None) for l in graph.objects(c, SKOS.definition)}
        assert {"de", "en"} <= langs, (c, langs)


@pytest.mark.parametrize("n", [1, 5, 8])
def test_exact_match_points_to_corrected_dqr_level(graph: Graph, n: int) -> None:
    assert (EQF[f"Level{n}"], SKOS.exactMatch, DQR[f"L{n}"]) in graph


def test_no_dangling_dqr_level_edges(graph: Graph) -> None:
    dangling = [
        str(o)
        for _, _, o in graph.triples((None, SKOS.exactMatch, None))
        if re.search(r"data\.bmbf\.de/dqr/Level[1-8]$", str(o))
    ]
    assert dangling == []


def test_g_struct_eqf_uris_still_present(graph: Graph) -> None:
    import json

    gs_path = Path(__file__).resolve().parents[1] / "eval" / "G_struct.json"
    if not gs_path.exists():
        pytest.skip("eval/G_struct.json nicht vorhanden")
    pairs = json.loads(gs_path.read_text(encoding="utf-8"))["pairs"]
    for uri in sorted({p["object_id"] for p in pairs}):
        assert (URIRef(uri), RDF.type, SKOS.Concept) in graph, uri


def test_level_hierarchy_and_dimension_links_untouched(graph: Graph) -> None:
    # Migration darf die bestehende Struktur nicht angetastet haben.
    for n in range(2, 9):
        assert (EQF[f"Level{n}"], SKOS.broader, EQF[f"Level{n - 1}"]) in graph
    for n in range(1, 9):
        assert (EQF[f"Level{n}"], EQF.hasKnowledge, EQF[f"L{n}_Knowledge"]) in graph
