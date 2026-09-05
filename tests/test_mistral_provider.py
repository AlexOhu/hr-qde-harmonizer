"""Tests für den Retry-/Backoff-Schutz in MistralProvider.complete() gegen
transiente Upstream-Fehler (429/5xx) -- vgl. Docstring in mistral_provider.py.
Kein echter Netzwerkzugriff: mistralai.client.Chat.complete wird gemockt,
time.sleep gepatcht, damit der Test nicht tatsächlich wartet."""

from __future__ import annotations

import httpx
import pytest

from app.pipeline.step3_classification.llm_provider.mistral_provider import MistralProvider
from mistralai.client.errors import MistralError


class _FakeMessage:
    content = "EQUIVALENT | Testbegründung"


class _FakeChoice:
    message = _FakeMessage()


class _FakeChatResponse:
    choices = [_FakeChoice()]


def _mistral_error(status_code: int) -> MistralError:
    raw_response = httpx.Response(
        status_code=status_code,
        request=httpx.Request("POST", "https://api.mistral.ai/v1/chat/completions"),
    )
    return MistralError("API error occurred", raw_response=raw_response)


@pytest.fixture
def provider(monkeypatch):
    p = MistralProvider(api_key="test-key", model="mistral-small-latest")
    monkeypatch.setattr(
        "app.pipeline.step3_classification.llm_provider.mistral_provider.time.sleep", lambda _: None
    )
    return p


def test_retries_transient_503_then_succeeds(provider, monkeypatch):
    calls = {"count": 0}

    def fake_complete(**kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise _mistral_error(503)
        return _FakeChatResponse()

    monkeypatch.setattr(provider._client.chat, "complete", fake_complete)

    result = provider.complete("irrelevanter Prompt")

    assert result == "EQUIVALENT | Testbegründung"
    assert calls["count"] == 3


def test_does_not_retry_non_transient_error(provider, monkeypatch):
    calls = {"count": 0}

    def fake_complete(**kwargs):
        calls["count"] += 1
        raise _mistral_error(401)

    monkeypatch.setattr(provider._client.chat, "complete", fake_complete)

    with pytest.raises(MistralError):
        provider.complete("irrelevanter Prompt")

    assert calls["count"] == 1


def test_gives_up_after_max_attempts(provider, monkeypatch):
    calls = {"count": 0}

    def fake_complete(**kwargs):
        calls["count"] += 1
        raise _mistral_error(503)

    monkeypatch.setattr(provider._client.chat, "complete", fake_complete)

    with pytest.raises(MistralError):
        provider.complete("irrelevanter Prompt")

    assert calls["count"] == 3
