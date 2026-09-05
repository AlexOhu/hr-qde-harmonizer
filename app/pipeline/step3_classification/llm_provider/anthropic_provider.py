"""Anthropic-Implementierung von LLMProvider.

Wrapper um das anthropic-SDK. Konfiguration (API-Key, Modell, Temperature)
erfolgt ausschließlich über den Konstruktor — keine globalen Settings hier.
"""

from __future__ import annotations

import anthropic

from .base import LLMProvider


class AnthropicProvider(LLMProvider):
    """LLMProvider-Implementierung für Anthropic Claude."""

    def __init__(self, api_key: str, model: str, temperature: float = 0.0) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._temperature = temperature

    @property
    def model_id(self) -> str:
        return f"anthropic/{self._model}"

    def complete(self, prompt: str, max_tokens: int = 200) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=self._temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ).strip()
