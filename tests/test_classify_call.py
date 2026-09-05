"""
Tests für call_classification_model (app/pipeline/step3_classification/classify.py).

Nach dem Refactoring nimmt call_classification_model einen LLMProvider statt
eines direkten API-Clients. Tests verwenden FakeLLMProvider aus conftest.py —
kein Monkeypatching von externen Bibliotheken nötig.
"""

import pytest

from app.models.schemas import RelationType
from app.pipeline.step3_classification.classify import (
    ClassificationParseError,
    call_classification_model,
)
from tests.conftest import FakeLLMProvider


def test_call_parses_valid_response():
    provider = FakeLLMProvider("EQUIVALENT | Beide bezeichnen dieselbe Kompetenz.")
    run = call_classification_model("irrelevant prompt", provider=provider)

    assert run.relation == RelationType.EQUIVALENT
    assert run.reasoning == "Beide bezeichnen dieselbe Kompetenz."
    assert run.model == "fake/test-model"


def test_call_records_provider_model_id():
    """model_id des Providers landet in ClassificationRun.model (Provenance FA4)."""
    provider = FakeLLMProvider("RELATED | grob verwandt.", model_name="openai/gpt-4o-mini")
    run = call_classification_model("prompt", provider=provider)

    assert run.model == "openai/gpt-4o-mini"


def test_call_rejects_missing_separator():
    provider = FakeLLMProvider("EQUIVALENT ohne Trennzeichen")
    with pytest.raises(ClassificationParseError):
        call_classification_model("prompt", provider=provider)


def test_call_rejects_unknown_relation():
    provider = FakeLLMProvider("MAYBE_EQUIVALENT | unklar")
    with pytest.raises(ClassificationParseError):
        call_classification_model("prompt", provider=provider)


def test_call_rejects_unresolved_as_direct_output():
    # "UNRESOLVED" ist kein RelationType-Wert mehr: ein fehlender
    # Mehrheitsentscheid ist final_relation=None aus majority_vote(), niemals
    # eine direkte Modellausgabe. Der Parser lehnt das Token ab.
    provider = FakeLLMProvider("UNRESOLVED | das Modell darf das nicht ausgeben")
    with pytest.raises(ClassificationParseError):
        call_classification_model("prompt", provider=provider)


def test_call_forwards_prompt_to_provider():
    """Der Prompt wird unverändert an provider.complete() weitergereicht."""
    provider = FakeLLMProvider("RELATED | ok")
    call_classification_model("mein konkreter Prompt", provider=provider)

    assert provider.calls == ["mein konkreter Prompt"]
