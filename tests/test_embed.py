from app.models.schemas import Concept
from app.pipeline.step2_embedding_prefilter.embed import embed_concepts


def test_embed_concepts_returns_vector_per_concept(mock_sentence_transformer):
    concepts = [
        Concept(uri="urn:a", kqr_id="k", pref_label="Programming", definition="Writing code."),
        Concept(uri="urn:b", kqr_id="k", pref_label="Teamwork", definition="Working together."),
    ]
    result = embed_concepts(concepts, "fake-model")

    assert set(result.keys()) == {"urn:a", "urn:b"}
    assert result["urn:a"].shape == (16,)


def test_embed_concepts_empty_list_returns_empty_dict(mock_sentence_transformer):
    assert embed_concepts([], "fake-model") == {}


def test_embed_concepts_is_deterministic_for_same_text(mock_sentence_transformer):
    concept = Concept(uri="urn:a", kqr_id="k", pref_label="Programming", definition="Writing code.")
    first = embed_concepts([concept], "fake-model")["urn:a"]
    second = embed_concepts([concept], "fake-model")["urn:a"]
    assert (first == second).all()
