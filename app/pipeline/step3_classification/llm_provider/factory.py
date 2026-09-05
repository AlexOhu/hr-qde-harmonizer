"""Factory-Funktionen für LLM-Provider.

get_provider        – erstellt einen einzelnen Provider per Name
get_providers_from_config – liest LLM_PROVIDERS aus Settings und gibt eine
                     geordnete Liste zurück (Reihenfolge = Round-Robin-Reihenfolge
                     für die Dreifachklassifikation in classify.py)
is_any_provider_configured – Key-Prüfung ohne Instanziierung (für check_preconditions)

Neuen Provider registrieren: elif-Zweig in get_provider + Eintrag in
_is_provider_key_set hinzufügen, fertig.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import LLMProvider

if TYPE_CHECKING:
    from app.config import Settings

_VALID_PROVIDERS = {"anthropic", "openai", "gemini", "mistral"}


def _is_provider_key_set(name: str, settings: "Settings") -> bool:
    """Prüft, ob der API-Key für einen einzelnen Anbieter gesetzt ist."""
    name = name.strip().lower()
    if name == "anthropic":
        return bool(settings.anthropic_api_key)
    if name == "openai":
        return bool(settings.openai_api_key)
    if name == "gemini":
        return bool(settings.gemini_api_key)
    if name == "mistral":
        return bool(settings.mistral_api_key)
    return False


def is_any_provider_configured(settings: "Settings") -> bool:
    """True, wenn mindestens ein konfigurierter Anbieter einen gesetzten API-Key hat.

    Wird von check_preconditions() genutzt (Visibility of System State).
    Instanziiert keine Provider — prüft nur die Key-Felder in Settings.
    """
    names = [n.strip() for n in settings.llm_providers.split(",") if n.strip()]
    return any(_is_provider_key_set(name, settings) for name in names)


def get_provider(name: str, settings: "Settings") -> LLMProvider:
    """Erstellt einen LLMProvider für den angegebenen Anbieternamen."""
    name = name.strip().lower()

    if name == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            temperature=settings.classification_temperature,
        )
    elif name == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            temperature=settings.classification_temperature,
        )
    elif name == "gemini":
        from .gemini_provider import GeminiProvider
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            temperature=settings.classification_temperature,
        )
    elif name == "mistral":
        from .mistral_provider import MistralProvider
        return MistralProvider(
            api_key=settings.mistral_api_key,
            model=settings.mistral_model,
            temperature=settings.classification_temperature,
        )
    else:
        raise ValueError(
            f"Unbekannter LLM-Anbieter: '{name}'. "
            f"Gültige Werte: {', '.join(sorted(_VALID_PROVIDERS))}."
        )


def get_providers_from_config(settings: "Settings") -> list[LLMProvider]:
    """Liest LLM_PROVIDERS (kommagetrennte Liste) und gibt Provider-Instanzen zurück.

    Beispiele:
      LLM_PROVIDERS=mistral              → [MistralProvider]
      LLM_PROVIDERS=mistral,openai       → [MistralProvider, OpenAIProvider]
      LLM_PROVIDERS=anthropic,openai,gemini,mistral → Round-Robin in dieser Reihenfolge

    Bei CLASSIFICATION_RUNS_PER_PAIR=3 und drei Anbietern erhält jeder genau
    einen Lauf. Bei einem Anbieter erhält dieser alle drei Läufe (Standardfall).
    """
    names = [n.strip() for n in settings.llm_providers.split(",") if n.strip()]
    if not names:
        raise ValueError(
            "LLM_PROVIDERS ist leer. Mindestens ein Anbieter muss konfiguriert sein."
        )
    return [get_provider(name, settings) for name in names]
