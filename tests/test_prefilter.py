import numpy as np

from app.models.schemas import Concept, MappingJustification, Mapping, ReviewStatus
from app.pipeline.step1_formalization.formalize import parse_concepts
from app.pipeline.step2_embedding_prefilter.prefilter import (
    child_level_concept_uris,
    derive_child_level_mappings,
    derive_container_mappings,
    detect_container_concepts,
    filter_by_scope,
    find_candidate_pairs,
    find_structural_shortcuts,
    has_level_concept_parent,
    load_structural_shortcut_predicates,
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


_EXACTMATCH_TTL = """
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex:   <http://example.org/> .
@prefix eqf:  <http://data.europa.eu/snb/eqf/> .

ex:L5 a skos:Concept ; skos:prefLabel "L5"@en ; skos:exactMatch eqf:Level5 .
ex:other a skos:Concept ; skos:prefLabel "other"@en ; skos:exactMatch eqf:Level5 .
eqf:Level5 a skos:Concept ; skos:prefLabel "EQF 5"@en .
"""

_EXACTMATCH_LOOKUP = {
    "http://example.org/L5": {"pref_label": "L5", "kqr_id": "ex"},
    "http://example.org/other": {"pref_label": "other", "kqr_id": "ex"},
    "http://data.europa.eu/snb/eqf/Level5": {"pref_label": "EQF 5", "kqr_id": "eqf"},
}
_SKOS_EXACT = {"http://www.w3.org/2004/02/skos/core#exactMatch": "skos:exactMatch"}


def test_find_structural_shortcuts_predicates_override_uses_only_given():
    """``predicates=`` ersetzt die JSON-Abbildung fuer diesen Aufruf --
    skos:exactMatch ist sonst KEIN registriertes Shortcut-Praedikat, wird
    mit Override aber als Struktur-Shortcut behandelt (Niveau-Crosswalk
    gegen EQF, ohne data/structural_shortcut_predicates.json zu aendern)."""
    graph = _graph(_EXACTMATCH_TTL)

    assert find_structural_shortcuts(graph, _EXACTMATCH_LOOKUP) == []

    mappings = find_structural_shortcuts(
        graph, _EXACTMATCH_LOOKUP, predicates=_SKOS_EXACT
    )

    assert sorted(m.subject_id for m in mappings) == [
        "http://example.org/L5",
        "http://example.org/other",
    ]
    assert all(m.predicate_id == "skos:exactMatch" for m in mappings)
    assert all(
        m.mapping_justification == MappingJustification.STRUCTURAL_MATCHING
        for m in mappings
    )


def test_find_structural_shortcuts_exclude_subjects_skips_them():
    graph = _graph(_EXACTMATCH_TTL)

    mappings = find_structural_shortcuts(
        graph,
        _EXACTMATCH_LOOKUP,
        predicates=_SKOS_EXACT,
        exclude_subjects={"http://example.org/other"},
    )

    assert [m.subject_id for m in mappings] == ["http://example.org/L5"]


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


_ROLE_TTL = """
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix harm: <http://hr-qde.org/harmonised/> .
@prefix ex:   <http://example.org/> .

ex:Competence1 a skos:Concept ; skos:prefLabel "Comp 1"@en ;
    harm:conceptRole harm:CompetenceConcept .
ex:Level1 a skos:Concept ; skos:prefLabel "Level 1"@en ;
    harm:conceptRole harm:LevelConcept .
ex:Untagged1 a skos:Concept ; skos:prefLabel "Untagged 1"@en .
"""


def test_concept_role_defaults_to_competence_concept_when_untagged():
    from app.pipeline.step2_embedding_prefilter.prefilter import HARM, concept_role

    graph = _graph(_ROLE_TTL)
    assert concept_role("http://example.org/Competence1", graph) == HARM.CompetenceConcept
    assert concept_role("http://example.org/Level1", graph) == HARM.LevelConcept
    assert concept_role("http://example.org/Untagged1", graph) == HARM.CompetenceConcept


def test_partition_by_role_buckets_embeddings_by_concept_role():
    from app.pipeline.step2_embedding_prefilter.prefilter import HARM, partition_by_role

    graph = _graph(_ROLE_TTL)
    embeddings = {
        "http://example.org/Competence1": np.array([1.0, 0.0]),
        "http://example.org/Level1": np.array([0.0, 1.0]),
        "http://example.org/Untagged1": np.array([0.5, 0.5]),
    }

    buckets = partition_by_role(embeddings, graph)

    assert set(buckets[HARM.CompetenceConcept].keys()) == {
        "http://example.org/Competence1",
        "http://example.org/Untagged1",
    }
    assert set(buckets[HARM.LevelConcept].keys()) == {"http://example.org/Level1"}


def test_filter_by_scope_all_no_longer_auto_excludes_level_concepts():
    """Befund 2026-09-05: scope='all' (Default) darf LevelConcept-Knoten
    NICHT mehr unbedingt in die Skelett-Schicht routen -- ein KQR-Paar ohne
    expliziten strukturellen Shortcut wird vollstaendig ausgewertet.
    Rollentrennung erfolgt stattdessen rollengleich beim Pairing
    (partition_by_role in classification_service), nicht hier."""
    graph = _graph(_ROLE_TTL)
    uris = ["http://example.org/Competence1", "http://example.org/Level1", "http://example.org/Untagged1"]

    pipeline, skeleton = filter_by_scope(uris, graph, scope="all")

    assert set(pipeline) == set(uris)
    assert skeleton == []


def test_load_structural_shortcut_predicates_reads_data_file(tmp_path):
    """Befund 2026-09-05: ein neuer struktureller Shortcut muss ein
    Dateneintrag sein koennen, kein Python-Edit. "_comment"-Schluessel
    (Dokumentationskonvention aus eval/G_struct.json) werden ignoriert."""
    import json

    config = tmp_path / "structural_shortcut_predicates.json"
    config.write_text(
        json.dumps({
            "_comment": "nur Dokumentation, keine Praedikat-URI",
            "http://example.org/customPredicate": "skos:closeMatch",
        }),
        encoding="utf-8",
    )

    result = load_structural_shortcut_predicates(path=config)

    assert result == {"http://example.org/customPredicate": "skos:closeMatch"}


def test_load_structural_shortcut_predicates_falls_back_when_file_missing(tmp_path):
    """Fehlt die Datei (z. B. frischer Checkout ohne data/), darf die
    Klassifikation nicht abstuerzen -- der eingebaute Fallback greift."""
    missing = tmp_path / "does_not_exist.json"

    result = load_structural_shortcut_predicates(path=missing)

    assert "http://data.europa.eu/esco/model#isPartOf" in result


def test_filter_by_scope_level_only_selects_level_concepts_into_pipeline():
    """scope='level_only' muss LevelConcept-Knoten tatsaechlich in die
    pipeline-Liste aufnehmen (nicht in die Skelett-Schicht) -- vor dem
    Befund 2026-09-05 war dieser Zweig unerreichbar, weil LevelConcept-
    Knoten bereits vorher unbedingt geskelettet wurden."""
    graph = _graph(_ROLE_TTL)
    uris = ["http://example.org/Competence1", "http://example.org/Level1", "http://example.org/Untagged1"]

    pipeline, skeleton = filter_by_scope(uris, graph, scope="level_only")

    assert pipeline == ["http://example.org/Level1"]
    assert set(skeleton) == {"http://example.org/Competence1", "http://example.org/Untagged1"}


# ---------------------------------------------------------------------------
# Eltern-Ableitung fuer Deskriptor-Niveauknoten (z. B. DQR-Dimension-2)
# ---------------------------------------------------------------------------

DQR = "http://data.bmbf.de/dqr/"
EQF_LEVEL = "http://data.europa.eu/snb/eqf/Level"
_DQR_DIMS = ["Knowledge", "Skills", "SocialCompetence", "Autonomy"]


def _dqr_2d_like_ttl() -> str:
    """8 Niveau-Anker dqr:L1..L8 (skos:exactMatch eqf:Level{n}, per
    skos:broader verkettet) + 32 Deskriptoren dqr:L{n}_{Dim}
    (skos:broader dqr:L{n}) -- strukturgleich zu data/formalized/dqr_2D.ttl,
    alle Knoten harm:conceptRole harm:LevelConcept."""
    lines = [
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix harm: <http://hr-qde.org/harmonised/> .",
        "@prefix dqr:  <http://data.bmbf.de/dqr/> .",
        "@prefix eqf:  <http://data.europa.eu/snb/eqf/> .",
        "",
    ]
    for n in range(1, 9):
        anchor = [
            f"dqr:L{n} a skos:Concept",
            f'skos:prefLabel "DQR-Niveau {n}"@en',
            "harm:conceptRole harm:LevelConcept",
            f"skos:exactMatch eqf:Level{n}",
        ]
        if n > 1:
            anchor.append(f"skos:broader dqr:L{n - 1}")
        for dim in _DQR_DIMS:
            anchor.append(f"skos:narrower dqr:L{n}_{dim}")
        lines.append(" ;\n    ".join(anchor) + " .")
        for dim in _DQR_DIMS:
            lines.append(
                f"dqr:L{n}_{dim} a skos:Concept ;\n"
                f'    skos:prefLabel "{dim} - Niveau {n}"@en ;\n'
                f"    harm:conceptRole harm:LevelConcept ;\n"
                f"    skos:broader dqr:L{n} ."
            )
    return "\n".join(lines) + "\n"


def _anchor_shortcut(n: int, conf: float = 1.0) -> Mapping:
    """Struktur-Shortcut dqr:L{n} -> eqf:Level{n}, wie ihn
    find_structural_shortcuts() bei geladenem EQF + registriertem
    skos:exactMatch erzeugen wuerde."""
    return Mapping(
        subject_id=f"{DQR}L{n}",
        subject_label=f"DQR-Niveau {n}",
        subject_kqr_id="dqr_2d",
        object_id=f"{EQF_LEVEL}{n}",
        object_label=f"EQF Level {n}",
        object_kqr_id="eqf_2d",
        predicate_id="skos:exactMatch",
        mapping_confidence=conf,
        mapping_justification=MappingJustification.STRUCTURAL_MATCHING,
        review_status=ReviewStatus.CONJUNCT,
    )


def test_child_level_concepts_excluded_from_ann_pool():
    """dqr_2D-artiger Graph: die 8 Niveau-Anker bleiben normale Konzepte,
    die 32 Deskriptoren werden als child_level_concept_uris erkannt und
    damit vom ANN-Pool-Aufbau ausgeschlossen."""
    graph = _graph(_dqr_2d_like_ttl())

    child = child_level_concept_uris(graph)

    assert len(child) == 32
    assert f"{DQR}L5_Knowledge" in child
    assert f"{DQR}L1_Autonomy" in child
    # Niveau-Anker: L1 ohne broader, L5 mit LevelConcept-Kindern -> kein Blatt
    assert f"{DQR}L1" not in child
    assert f"{DQR}L5" not in child
    assert not any(uri.rsplit("/", 1)[-1] in {f"L{n}" for n in range(1, 9)} for uri in child)

    assert has_level_concept_parent(f"{DQR}L5_Knowledge", graph) is True
    assert has_level_concept_parent(f"{DQR}L1", graph) is False


def test_pure_level_chain_has_no_child_level_concepts():
    """dqr_1D-artige reine Niveaukette L1<-L2<-...<-L8 (ohne Facetten):
    die Kettenspitze L8 ist zwar ein kinderloses LevelConcept mit
    LevelConcept-Elternteil, aber ihr Elternteil L7 verzweigt nicht
    (nur ein Level-Kind) -- L8 ist damit kein Deskriptor."""
    lines = [
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix harm: <http://hr-qde.org/harmonised/> .",
        "@prefix dqr:  <http://data.bmbf.de/dqr/> .",
        "@prefix eqf:  <http://data.europa.eu/snb/eqf/> .",
        "",
    ]
    for n in range(1, 9):
        block = [
            f"dqr:L{n} a skos:Concept",
            f'skos:prefLabel "DQR-Niveau {n}"@en',
            "harm:conceptRole harm:LevelConcept",
            f"skos:exactMatch eqf:Level{n}",
        ]
        if n > 1:
            block.append(f"skos:broader dqr:L{n - 1}")
        lines.append(" ;\n    ".join(block) + " .")
    graph = _graph("\n".join(lines) + "\n")

    assert child_level_concept_uris(graph) == set()


def test_derive_child_level_mappings_basic():
    parent = _anchor_shortcut(5)
    child = Concept(
        uri=f"{DQR}L5_Knowledge",
        kqr_id="dqr_2d",
        pref_label="Knowledge - Niveau 5",
        broader=[f"{DQR}L5"],
    )

    derived = derive_child_level_mappings([child], [parent])

    assert len(derived) == 1
    mapping = derived[0]
    assert mapping.subject_id == f"{DQR}L5_Knowledge"
    assert mapping.object_id == f"{EQF_LEVEL}5"
    assert mapping.predicate_id == "skos:narrowMatch"
    assert mapping.mapping_confidence == 1.0
    assert mapping.mapping_justification == MappingJustification.LOGICAL_REASONING
    assert mapping.mapping_source == "algorithmic"
    # abgeleitete Mappings sind determiniert -> nie im Review-Queue
    assert mapping.review_status == ReviewStatus.CONJUNCT


def test_derive_child_level_mappings_missing_parent(caplog):
    child = Concept(
        uri=f"{DQR}L5_Knowledge",
        kqr_id="dqr_2d",
        pref_label="Knowledge - Niveau 5",
        broader=[f"{DQR}L5"],
    )

    with caplog.at_level("WARNING"):
        derived = derive_child_level_mappings([child], [])  # kein Shortcut fuer L5

    assert derived == []
    assert "Eltern-Ableitung uebersprungen" in caplog.text


def test_derive_child_level_mappings_skips_already_derived():
    parent = _anchor_shortcut(5)
    child = Concept(
        uri=f"{DQR}L5_Knowledge",
        kqr_id="dqr_2d",
        pref_label="Knowledge - Niveau 5",
        broader=[f"{DQR}L5"],
    )

    derived = derive_child_level_mappings(
        [child], [parent], already_derived_subjects={f"{DQR}L5_Knowledge"}
    )

    assert derived == []


def test_all_32_dqr_descriptors_get_derived_mappings():
    """Shortcut + Ableitung ueber einen dqr_2D-strukturgleichen Graphen:
    8 Anker-Shortcuts (exactMatch, StructuralMatching) fuehren zu 32
    abgeleiteten Deskriptor-Mappings (narrowMatch, LogicalReasoning),
    kein Deskriptor bleibt offen (Review-Queue = 0)."""
    ttl = _dqr_2d_like_ttl()
    graph = _graph(ttl)

    child_uris = child_level_concept_uris(graph)
    assert len(child_uris) == 32

    concepts = parse_concepts(ttl, "dqr_2d")
    child_concepts = [c for c in concepts if c.uri in child_uris]
    assert len(child_concepts) == 32

    shortcut_mappings = [_anchor_shortcut(n) for n in range(1, 9)]
    assert len(shortcut_mappings) == 8
    assert all(
        m.mapping_justification == MappingJustification.STRUCTURAL_MATCHING
        for m in shortcut_mappings
    )

    derived = derive_child_level_mappings(child_concepts, shortcut_mappings)

    assert len(derived) == 32
    assert all(m.predicate_id == "skos:narrowMatch" for m in derived)
    assert all(
        m.mapping_justification == MappingJustification.LOGICAL_REASONING for m in derived
    )
    assert all(m.review_status == ReviewStatus.CONJUNCT for m in derived)
    assert not any(m.review_status == ReviewStatus.OPEN for m in derived)

    by_subject = {m.subject_id: m for m in derived}
    assert by_subject[f"{DQR}L5_Knowledge"].object_id == f"{EQF_LEVEL}5"
    assert by_subject[f"{DQR}L8_Autonomy"].object_id == f"{EQF_LEVEL}8"
