"""LLM-Provider-Abstraktionsschicht für Schritt 3 (Klassifikation).

Öffentliche API dieses Pakets:
  LLMProvider               – abstrakte Basisklasse
  AnthropicProvider         – Anthropic Claude
  OpenAIProvider            – OpenAI ChatGPT
  GeminiProvider            – Google Gemini
  get_provider              – Factory für einen Anbieter per Name
  get_providers_from_config – baut Provider-Liste aus Settings.llm_providers

Neue Anbieter: LLMProvider ableiten, in factory.py registrieren.
Keine anderen Dateien müssen geändert werden.
"""

from .base import LLMProvider
from .factory import get_provider, get_providers_from_config, is_any_provider_configured

__all__ = [
    "LLMProvider",
    "get_provider",
    "get_providers_from_config",
    "is_any_provider_configured",
]
