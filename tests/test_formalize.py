from app.models.schemas import KQR
from app.pipeline.step1_formalization.formalize import parse_concepts, validate_formalization


def _make_kqr(kqr_id: str) -> KQR:
    return KQR(
        id=kqr_id,
        name=kqr_id,
        namespace_uri=f"http://hr-qde.org/harmonised/{kqr_id}/",
        source_format="turtle",
    )


def test_validate_formalization_accepts_valid_fixture(hub_ttl):
    errors = validate_formalization(hub_ttl, _make_kqr("hub_kqr"))
    assert errors == []


def test_validate_formalization_reports_missing_required_field():
    turtle = """
    @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
    @prefix ex: <http://hr-qde.org/harmonised/broken/> .
    ex:c1 a skos:Concept ;
        skos:prefLabel "Only English"@en .
    """
    errors = validate_formalization(turtle, _make_kqr("broken"))
    assert any("skos:prefLabel@de" in e for e in errors)
    assert any("skos:definition" in e for e in errors)
    assert any("dcterms:source" in e for e in errors)


def test_validate_formalization_rejects_unparseable_turtle():
    errors = validate_formalization("this is not turtle {{{", _make_kqr("broken"))
    assert len(errors) == 1
    assert "geparst" in errors[0]


def test_validate_formalization_rejects_self_referential_hierarchy_and_two_roles():
    turtle = """
    @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
    @prefix harm: <http://hr-qde.org/harmonised/> .
    @prefix ex: <http://example.org/> .
    ex:c1 a skos:Concept, harm:CompetenceConcept, harm:LevelConcept ;
        skos:prefLabel "Broken"@en ;
        skos:broader ex:c1 .
    """

    errors = validate_formalization(turtle, _make_kqr("broken"), strict=False)

    assert any("zugleich" in error for error in errors)
    assert any("auf sich selbst" in error for error in errors)


def test_validate_formalization_rejects_hierarchy_cycle():
    turtle = """
    @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
    @prefix ex: <http://example.org/> .
    ex:c1 a skos:Concept ; skos:prefLabel "One"@en ; skos:broader ex:c2 .
    ex:c2 a skos:Concept ; skos:prefLabel "Two"@en ; skos:broader ex:c1 .
    """

    errors = validate_formalization(turtle, _make_kqr("broken"), strict=False)

    assert "Die SKOS-Hierarchie enthält einen Zyklus." in errors


def test_parse_concepts_extracts_expected_fields(hub_ttl):
    concepts = parse_concepts(hub_ttl, "hub_kqr")
    assert len(concepts) == 6

    programming = next(c for c in concepts if c.uri.endswith("programming"))
    assert programming.pref_label == "Programming"
    assert programming.definition.startswith("Writing computer programs")
    assert programming.kqr_id == "hub_kqr"


def test_parse_concepts_extracts_structural_shortcut_target(satellite_ttl):
    concepts = parse_concepts(satellite_ttl, "satellite_kqr")
    assert len(concepts) == 4
    level_5 = next(c for c in concepts if c.uri.endswith("level_5"))
    assert level_5.pref_label == "e-CF Level 5"
