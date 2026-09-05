from app.models.schemas import (
    CandidatePair,
    ClassificationResult,
    ClassificationRun,
    MappingJustification,
    RelationType,
    ReviewStatus,
)
from app.pipeline.step4_export.sssom_writer import classification_results_to_mappings

_LOOKUP = {
    "urn:a": {"pref_label": "A", "kqr_id": "kqr_a"},
    "urn:b": {"pref_label": "B", "kqr_id": "kqr_b"},
}


def _result(relation: RelationType | None, confidence: float = 1.0) -> ClassificationResult:
    pair = CandidatePair(concept_a="urn:a", concept_b="urn:b", similarity_score=0.9)
    # Ohne Mehrheitsentscheid (relation=None) trägt der einzelne Lauf trotzdem
    # eine konkrete Relation; RELATED steht hier stellvertretend.
    run_relation = relation if relation is not None else RelationType.RELATED
    runs = [
        ClassificationRun(
            relation=run_relation, reasoning="Begründung", model="m", temperature=0.0
        )
    ]
    return ClassificationResult(
        pair=pair, runs=runs, final_relation=relation, mapping_confidence=confidence
    )


def test_equivalent_result_becomes_mapping():
    mappings = classification_results_to_mappings([_result(RelationType.EQUIVALENT)], _LOOKUP)

    assert len(mappings) == 1
    mapping = mappings[0]
    assert mapping.predicate_id == "skos:exactMatch"
    assert mapping.mapping_justification == MappingJustification.LLM_BASED_MATCHING
    assert mapping.mapping_source == "algorithmic"
    assert mapping.justification == "Begründung"


def test_related_and_no_consensus_are_persisted_as_open_reviews():
    """Frueher wurden RELATED-Ergebnisse und Paare ohne Mehrheitsentscheid
    verworfen und existierten nur als fluechtige Objekte im Pruefbericht. Seit
    v0.2 bekommen sie ein Mapping-Objekt mit stabiler mapping_id und
    ReviewStatus.OPEN. Der fehlende Mehrheitsentscheid traegt predicate_id=None,
    ein offenes RELATED traegt skos:relatedMatch."""
    results = [_result(RelationType.RELATED), _result(None)]
    mappings = classification_results_to_mappings(results, _LOOKUP)

    assert len(mappings) == 2
    assert all(m.review_status == ReviewStatus.OPEN for m in mappings)
    assert all(m.mapping_id for m in mappings)
    assert {m.predicate_id for m in mappings} == {"skos:relatedMatch", None}


def test_open_reviews_are_not_written_to_the_export(tmp_path):
    """Persistiert heisst nicht exportiert: ein noch offenes Paar gehoert
    nicht in die SSSOM-Datei, sonst behauptete der Export eine Entscheidung,
    die niemand getroffen hat."""
    from app.pipeline.step4_export.sssom_writer import write_sssom_tsv

    mappings = classification_results_to_mappings(
        [_result(RelationType.EQUIVALENT), _result(None)], _LOOKUP
    )
    output = write_sssom_tsv(mappings, tmp_path / "export.tsv", 0.0)
    content = output.read_text(encoding="utf-8")

    assert content.count("skos:exactMatch") == 1
    assert "skos:relatedMatch" not in content


def test_subsumption_predicates_translated_correctly():
    # subject_id = Konzept A, object_id = Konzept B. Nach SKOS besagt
    # "A skos:narrowMatch B", dass B enger ist als A. A_SUBSUMES_B ("A ist
    # Oberbegriff von B", B enger) muss daher auf skos:narrowMatch abgebildet
    # werden, B_SUBSUMES_A auf skos:broadMatch.
    a_subsumes = classification_results_to_mappings([_result(RelationType.A_SUBSUMES_B)], _LOOKUP)
    b_subsumes = classification_results_to_mappings([_result(RelationType.B_SUBSUMES_A)], _LOOKUP)

    assert a_subsumes[0].predicate_id == "skos:narrowMatch"
    assert b_subsumes[0].predicate_id == "skos:broadMatch"


def test_mapping_justification_values_are_semapv_curies():
    """mapping_justification traegt die SEMAPV-CURIE direkt als Enum-Wert; die
    frueher noetige Uebersetzung von match_type entfaellt damit."""
    from app.models.schemas import MappingJustification
    assert MappingJustification.STRUCTURAL_MATCHING.value == "semapv:StructuralMatching"
    assert MappingJustification.LLM_BASED_MATCHING.value == "semapv:LLMBasedMatching"
    assert MappingJustification.MAPPING_REVIEW.value == "semapv:MappingReview"
    assert not hasattr(MappingJustification, "to_semapv_curie")


def test_legacy_match_type_is_translated_on_load():
    """Persistierte Mappings vor v0.2 tragen match_type. Sie muessen ladbar
    bleiben, damit ein nicht migrierter Datenbestand die API nicht blockiert."""
    from app.models.schemas import Mapping, MappingJustification

    legacy = Mapping(
        subject_id="urn:a",
        subject_label="A",
        object_id="urn:b",
        object_label="B",
        predicate_id="skos:exactMatch",
        mapping_confidence=1.0,
        match_type="struct",
    )
    assert legacy.mapping_justification == MappingJustification.STRUCTURAL_MATCHING
    assert not hasattr(legacy, "match_type")

    legacy_manual = Mapping(
        subject_id="urn:a",
        subject_label="A",
        object_id="urn:b",
        object_label="B",
        predicate_id="skos:exactMatch",
        mapping_confidence=1.0,
        match_type="llm",
        mapping_source="manual",
    )
    assert legacy_manual.mapping_justification == MappingJustification.MAPPING_REVIEW


def test_sssom_record_uses_mapping_justification():
    """SSSOMRecord enthält mapping_justification mit SEMAPV-CURIE, nicht match_type."""
    from app.models.schemas import (
        CandidatePair, ClassificationResult, ClassificationRun,
        Mapping, MappingJustification, RelationType, SSSOMRecord
    )
    mapping = Mapping(
        subject_id="urn:a",
        subject_label="A",
        object_id="urn:b",
        object_label="B",
        predicate_id="skos:exactMatch",
        mapping_confidence=0.89,
        mapping_justification=MappingJustification.LLM_BASED_MATCHING,
    )
    record = SSSOMRecord.from_mapping(mapping)
    assert not hasattr(record, "match_type"), \
        "SSSOMRecord darf kein Feld match_type mehr haben"
    assert record.mapping_justification == "semapv:LLMBasedMatching"
