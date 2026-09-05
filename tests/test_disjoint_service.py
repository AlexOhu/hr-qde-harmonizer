"""
Verwendet isolated_services-Fixture aus conftest.py (tmp_path-basiert).
"""

from __future__ import annotations

import pytest

from app.models.schemas import (
    CandidatePair,
    ClassificationResult,
    ClassificationRun,
    DisjointStrategy,
    Mapping,
    MappingJustification,
    RelationType,
)
from app.pipeline.step4_export.sssom_writer import classification_results_to_mappings
from app.services import disjoint_service, kqr_service, mapping_service, project_service


@pytest.fixture
def hub_concepts(isolated_services, hub_ttl, mock_sentence_transformer):
    """Registriert das Hub-Fixture-KQR (6 Konzepte: programming,
    project_management, database_design, communication, teamwork,
    eqf_level_6) und gibt sie als kqr_id -> Concept-Dict zurück."""
    kqr = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    concepts = kqr_service.get_concepts(kqr.id)
    return {c.uri.rsplit("/", 1)[-1]: c for c in concepts}


def _mark_as_k_mapping(concepts, subject_key, object_key):
    subject = concepts[subject_key]
    obj = concepts[object_key]
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
                mapping_confidence=0.95,
                mapping_justification=MappingJustification.LLM_BASED_MATCHING,
                mapping_source="algorithmic",
            )
        ]
    )


def _mark_as_related(concepts, a_key, b_key):
    a, b = concepts[a_key], concepts[b_key]
    run = ClassificationRun(
        relation=RelationType.RELATED, reasoning="Thematische Nähe", model="fake/test-model", temperature=0.0
    )
    result = ClassificationResult(
        pair=CandidatePair(concept_a=a.uri, concept_b=b.uri, similarity_score=0.6),
        runs=[run, run, run],
        final_relation=RelationType.RELATED,
        mapping_confidence=1.0,
    )
    mapping_service.add_classification_results([result])
    # Seit v0.2 persistiert die Pipeline zu jedem RELATED-Ergebnis auch ein
    # Mapping-Objekt mit ReviewStatus.OPEN (siehe
    # classification_results_to_mappings). get_related_concept_uris() liest
    # aus dieser Menge, nicht mehr aus den ClassificationResult-Objekten.
    mapping_service.add_mappings(
        classification_results_to_mappings(
            [result],
            {
                a.uri: {"pref_label": a.pref_label, "kqr_id": a.kqr_id},
                b.uri: {"pref_label": b.pref_label, "kqr_id": b.kqr_id},
            },
        )
    )


def test_list_disjoint_concepts_excludes_k_mapped_concepts(hub_concepts):
    _mark_as_k_mapping(hub_concepts, "programming", "project_management")

    disjoint = disjoint_service.list_disjoint_concepts()
    disjoint_uris = {c.uri for c in disjoint}

    assert hub_concepts["programming"].uri not in disjoint_uris
    assert hub_concepts["project_management"].uri not in disjoint_uris
    assert hub_concepts["teamwork"].uri in disjoint_uris
    assert len(disjoint) == 4


def test_suggest_strategy_returns_attach_to_skeleton_for_related_concepts(hub_concepts):
    _mark_as_related(hub_concepts, "database_design", "communication")

    assert disjoint_service.suggest_strategy(hub_concepts["database_design"]) == DisjointStrategy.ATTACH_TO_SKELETON
    assert disjoint_service.suggest_strategy(hub_concepts["communication"]) == DisjointStrategy.ATTACH_TO_SKELETON


def test_suggest_strategy_returns_own_class_for_unmapped_concepts(hub_concepts):
    assert (
        disjoint_service.suggest_strategy(hub_concepts["teamwork"]) == DisjointStrategy.OWN_CLASS
    )
    assert (
        disjoint_service.suggest_strategy(hub_concepts["eqf_level_6"]) == DisjointStrategy.OWN_CLASS
    )


def test_suggest_strategy_never_returns_out_of_scope(hub_concepts):
    _mark_as_related(hub_concepts, "database_design", "communication")

    for concept in hub_concepts.values():
        assert disjoint_service.suggest_strategy(concept) != DisjointStrategy.OUT_OF_SCOPE


def test_decide_persists_and_overwrites_without_duplicating(hub_concepts):
    concept = hub_concepts["teamwork"]

    first = disjoint_service.decide(
        concept_id=concept.uri,
        strategy=DisjointStrategy.OWN_CLASS,
        justification="Erste Entscheidung",
        author="Alex",
    )
    assert first.strategy == DisjointStrategy.OWN_CLASS

    second = disjoint_service.decide(
        concept_id=concept.uri,
        strategy=DisjointStrategy.OUT_OF_SCOPE,
        justification="Korrigierte Entscheidung",
        author="Alex",
    )
    assert second.strategy == DisjointStrategy.OUT_OF_SCOPE

    decisions = [d for d in disjoint_service.list_decisions() if d.concept_id == concept.uri]
    assert len(decisions) == 1
    assert decisions[0].justification == "Korrigierte Entscheidung"


def test_get_decision_returns_none_when_undecided(hub_concepts):
    assert disjoint_service.get_decision(hub_concepts["teamwork"].uri) is None


@pytest.fixture
def third_kqr_concepts(isolated_services):
    """Ein drittes, minimales KQR (ein Konzept), damit Tests ein zweites
    KQR-Paar simulieren können, ohne die satellite_kqr-Fixture zu verwenden."""
    third_ttl = """
    @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
    @prefix third: <http://hr-qde.org/harmonised/third_kqr/> .

    third:level_a a skos:Concept ;
        skos:prefLabel "Level A" .
    """
    kqr = kqr_service.register_kqr(
        name="Third KQR", source_format="turtle", filename="third.ttl",
        content=third_ttl.encode("utf-8"), is_hub=False,
    )
    concepts = kqr_service.get_concepts(kqr.id)
    return {c.uri.rsplit("/", 1)[-1]: c for c in concepts}


def test_list_disjoint_concepts_for_pair_ignores_matches_from_other_pairs(
    hub_concepts, third_kqr_concepts, satellite_ttl
):
    """Kernkorrektur: ein Konzept mit einem K-Mapping in Paar Hub<->Third
    darf im Paar Hub<->Satellite (kein eigenes Mapping dort) trotzdem als
    disjunkt gelten -- die projektweite list_disjoint_concepts() würde es
    fälschlich als 'nicht disjunkt' ausschließen."""
    satellite_kqr = kqr_service.register_kqr(
        name="Satellite KQR", source_format="turtle", filename="satellite.ttl",
        content=satellite_ttl.encode("utf-8"), is_hub=False,
    )
    programming = hub_concepts["programming"]
    level_a = third_kqr_concepts["level_a"]
    satellite_kqr_id = satellite_kqr.id  # kein Mapping in diesem Paar -> "programming" bleibt hier disjunkt

    mapping_service.add_mappings(
        [
            Mapping(
                subject_id=programming.uri,
                subject_label=programming.pref_label,
                subject_kqr_id=programming.kqr_id,
                object_id=level_a.uri,
                object_label=level_a.pref_label,
                object_kqr_id=level_a.kqr_id,
                predicate_id=RelationType.EQUIVALENT.to_skos_predicate(),
                mapping_confidence=0.9,
                mapping_justification=MappingJustification.LLM_BASED_MATCHING,
                mapping_source="algorithmic",
            )
        ]
    )

    # Projektweit gilt "programming" bereits als nicht disjunkt.
    assert programming.uri not in {c.uri for c in disjoint_service.list_disjoint_concepts()}

    # Bezogen auf das Paar Hub<->Third HAT "programming" ein K-Mapping -> nicht disjunkt.
    pair_hub_third = disjoint_service.list_disjoint_concepts_for_pair(
        programming.kqr_id, level_a.kqr_id
    )
    assert programming.uri not in {c.uri for c in pair_hub_third}

    # Bezogen auf ein anderes Paar (Hub<->satellite_kqr_id, kein Mapping dort)
    # bleibt "programming" disjunkt, obwohl es projektweit schon gematcht ist.
    pair_hub_other = disjoint_service.list_disjoint_concepts_for_pair(
        programming.kqr_id, satellite_kqr_id
    )
    assert programming.uri in {c.uri for c in pair_hub_other}


def test_get_summary_for_pair_reflects_decision_made_in_other_pair_context(
    hub_concepts, third_kqr_concepts
):
    """Eine Entscheidung ist global pro concept_id (siehe Kommentar in
    get_summary_for_pair) -- ein Konzept, das in einem anderen Paar bereits
    entschieden wurde, muss auch in diesem Paar als 'entschieden' zählen."""
    teamwork = hub_concepts["teamwork"]

    disjoint_service.decide(
        concept_id=teamwork.uri,
        strategy=DisjointStrategy.OWN_CLASS,
        justification="Entschieden im Kontext eines anderen Paares",
        author="Alex",
    )

    summary = disjoint_service.get_summary_for_pair(teamwork.kqr_id, third_kqr_concepts["level_a"].kqr_id)

    assert teamwork.uri in {
        c.uri
        for c in disjoint_service.list_disjoint_concepts_for_pair(
            teamwork.kqr_id, third_kqr_concepts["level_a"].kqr_id
        )
    }
    assert summary["decided"] >= 1
    assert summary["by_strategy"]["own_class"] == 1


def test_get_summary_counts_total_decided_open_and_by_strategy(hub_concepts):
    _mark_as_k_mapping(hub_concepts, "programming", "project_management")
    # 4 disjunkte Konzepte: database_design, communication, teamwork, eqf_level_6

    disjoint_service.decide(
        concept_id=hub_concepts["teamwork"].uri,
        strategy=DisjointStrategy.OWN_CLASS,
        justification="Eigenständig",
        author="Alex",
    )
    disjoint_service.decide(
        concept_id=hub_concepts["eqf_level_6"].uri,
        strategy=DisjointStrategy.ATTACH_TO_SKELETON,
        justification="Anhängen",
        author="Alex",
        anchor_class="http://hr-qde.org/harmonised/root/qualification_level",
    )

    summary = disjoint_service.get_summary()

    assert summary["total_disjoint"] == 4
    assert summary["decided"] == 2
    assert summary["open"] == 2
    assert summary["by_strategy"]["own_class"] == 1
    assert summary["by_strategy"]["attach_to_skeleton"] == 1
    assert summary["by_strategy"]["out_of_scope"] == 0


def test_decide_records_context_kqr_ids_sorted(hub_concepts):
    """decide() haelt die KQR-Kombination fest, gegen die entschieden wird --
    sortiert, unabhaengig von der Reihenfolge in project.kqr_ids."""
    hub_id = hub_concepts["teamwork"].kqr_id
    kqr_ids = ["zzz_kqr", hub_id, "aaa_kqr"]
    project = project_service.create_project(name="Kontext-Test", kqr_ids=kqr_ids)

    decision = disjoint_service.decide(
        concept_id=hub_concepts["teamwork"].uri,
        strategy=DisjointStrategy.OWN_CLASS,
        justification="Mit Projektkontext",
        author="Alex",
        project_id=project.project_id,
    )

    assert decision.context_kqr_ids == sorted(kqr_ids)


def test_decide_without_project_record_leaves_context_empty(hub_concepts):
    """Ohne persistierten Project-Datensatz (Testkonvention 'default') bleibt
    context_kqr_ids leer -- ein solcher Datensatz wird spaeter nicht zur
    Wiederverwendung vorgeschlagen."""
    decision = disjoint_service.decide(
        concept_id=hub_concepts["teamwork"].uri,
        strategy=DisjointStrategy.OWN_CLASS,
        justification="Ohne Projektkontext",
        author="Alex",
    )

    assert decision.context_kqr_ids == []


def test_suggest_reusable_decision_offers_when_current_is_subset(hub_concepts):
    """Wurde gegen {hub,b,c} entschieden, ist die Entscheidung fuer die
    Teilmenge {hub,b} weiter gueltig und wird angeboten."""
    hub_id = hub_concepts["teamwork"].kqr_id
    source = project_service.create_project(
        name="Quelle", kqr_ids=[hub_id, "b_kqr", "c_kqr"]
    )
    concept_uri = hub_concepts["teamwork"].uri
    disjoint_service.decide(
        concept_id=concept_uri,
        strategy=DisjointStrategy.OWN_CLASS,
        justification="Im Quellprojekt entschieden",
        author="Alex",
        project_id=source.project_id,
    )

    reusable = disjoint_service.suggest_reusable_decision(concept_uri, [hub_id, "b_kqr"])

    assert reusable is not None
    assert reusable.concept_id == concept_uri
    assert reusable.strategy == DisjointStrategy.OWN_CLASS


def test_suggest_reusable_decision_not_offered_for_superset_or_disjoint(hub_concepts):
    """Bei Obermenge oder ueberschneidungsfreier Menge koennte ein
    zusaetzliches KQR ein bisher ungeprueftes Mapping liefern -- kein
    Vorschlag."""
    hub_id = hub_concepts["teamwork"].kqr_id
    source = project_service.create_project(name="Quelle", kqr_ids=[hub_id, "b_kqr"])
    concept_uri = hub_concepts["teamwork"].uri
    disjoint_service.decide(
        concept_id=concept_uri,
        strategy=DisjointStrategy.OWN_CLASS,
        justification="Gegen {hub,b} entschieden",
        author="Alex",
        project_id=source.project_id,
    )

    assert disjoint_service.suggest_reusable_decision(concept_uri, [hub_id, "b_kqr", "c_kqr"]) is None
    assert disjoint_service.suggest_reusable_decision(concept_uri, ["x_kqr"]) is None


def test_suggest_reusable_decision_ignores_empty_context(hub_concepts):
    """Nicht migrierte Altdatensaetze (leeres context_kqr_ids) werden nie
    vorgeschlagen -- ihre Vergleichsmenge ist unbekannt."""
    concept_uri = hub_concepts["teamwork"].uri
    # decide() ohne Project-Datensatz -> context_kqr_ids == []
    disjoint_service.decide(
        concept_id=concept_uri,
        strategy=DisjointStrategy.OWN_CLASS,
        justification="Altdatensatz ohne Kontext",
        author="Alex",
    )

    assert disjoint_service.suggest_reusable_decision(concept_uri, ["a_kqr"]) is None
    assert disjoint_service.suggest_reusable_decision(concept_uri, []) is None


def test_suggest_reusable_decision_returns_latest_of_multiple_matches(hub_concepts):
    """Mehrere passende Kandidaten -> der zuletzt erstellte gewinnt."""
    concept_uri = hub_concepts["teamwork"].uri
    hub_id = hub_concepts["teamwork"].kqr_id
    older = project_service.create_project(name="Alt", kqr_ids=[hub_id, "b_kqr"])
    newer = project_service.create_project(name="Neu", kqr_ids=[hub_id, "b_kqr"])

    disjoint_service.decide(
        concept_id=concept_uri, strategy=DisjointStrategy.OWN_CLASS,
        justification="alt", author="Alex", project_id=older.project_id,
    )
    later = disjoint_service.decide(
        concept_id=concept_uri, strategy=DisjointStrategy.OUT_OF_SCOPE,
        justification="neu", author="Alex", project_id=newer.project_id,
    )

    reusable = disjoint_service.suggest_reusable_decision(concept_uri, [hub_id])

    assert reusable is not None
    assert reusable.decision_id == later.decision_id
    assert reusable.strategy == DisjointStrategy.OUT_OF_SCOPE
