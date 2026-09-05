"""OpenAI-Implementierung von LLMProvider (ChatGPT).

Lazy-Import von openai — das Paket muss nur installiert sein, wenn dieser
Provider tatsächlich konfiguriert wird (LLM_PROVIDERS=openai).
Installation: pip install openai>=1.0
"""

from __future__ import annotations

from .base import LLMProvider


class OpenAIProvider(LLMProvider):
    """LLMProvider-Implementierung für OpenAI ChatGPT."""

    def __init__(self, api_key: str, model: str, temperature: float = 0.0) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "Das Paket 'openai' ist nicht installiert. "
                "Bitte 'pip install openai>=1.0' ausführen."
            ) from exc

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._temperature = temperature

    @property
    def model_id(self) -> str:
        return f"openai/{self._model}"

    def complete(self, prompt: str, max_tokens: int = 200) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=self._temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return (response.choices[0].message.content or "").strip()
