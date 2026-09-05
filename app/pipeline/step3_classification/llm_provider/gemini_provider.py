"""Google Gemini-Implementierung von LLMProvider.

Lazy-Import von google-generativeai — das Paket muss nur installiert sein,
wenn dieser Provider konfiguriert wird (LLM_PROVIDERS=gemini).
Installation: pip install google-generativeai>=0.8
"""

from __future__ import annotations

from .base import LLMProvider


class GeminiProvider(LLMProvider):
    """LLMProvider-Implementierung für Google Gemini."""

    def __init__(self, api_key: str, model: str, temperature: float = 0.0) -> None:
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise ImportError(
                "Das Paket 'google-generativeai' ist nicht installiert. "
                "Bitte 'pip install google-generativeai>=0.8' ausführen."
            ) from exc

        genai.configure(api_key=api_key)
        self._genai = genai
        self._client = genai.GenerativeModel(model_name=model)
        self._model = model
        self._temperature = temperature

    @property
    def model_id(self) -> str:
        return f"gemini/{self._model}"

    def complete(self, prompt: str, max_tokens: int = 200) -> str:
        generation_config = self._genai.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=self._temperature,
        )
        response = self._client.generate_content(prompt, generation_config=generation_config)
        return (response.text or "").strip()
