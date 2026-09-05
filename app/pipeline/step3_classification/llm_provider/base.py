"""Abstrakte Basisklasse für LLM-Provider (Schritt 3: Klassifikation).

Jede Implementierung kapselt einen API-Client hinter dieser Schnittstelle.
classify.py kennt ausschließlich LLMProvider — keinen konkreten Client.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Einheitliche Schnittstelle für LLM-Anbieter.

    Implementierungen: AnthropicProvider, OpenAIProvider, GeminiProvider.
    Temperature und Modellname werden beim Konstruktor übergeben und sind
    danach unveränderlich (jede Instanz repräsentiert eine feste Konfiguration).
    """

    @abstractmethod
    def complete(self, prompt: str, max_tokens: int = 200) -> str:
        """Sendet einen Prompt und gibt die rohe Textantwort zurück.

        max_tokens=200 reicht für die kurzen Klassifikationslabels aus
        Schritt 3 (classify.py). Aufrufer mit langen Ausgaben (z. B.
        formalize_from_pdf, das ganze Turtle-Dokumente erzeugt) müssen
        explizit einen höheren Wert übergeben.

        Keine Parsing-Logik hier — das ist Aufgabe von classify.py.
        Wirft im Fehlerfall eine Exception (z. B. AuthenticationError,
        RateLimitError) ohne sie stillschweigend zu unterdrücken.
        """

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Eindeutiger Bezeichner im Format 'anbieter/modellname'.

        Wird in ClassificationRun.model gespeichert (Provenance, FA4).
        Beispiele: 'anthropic/claude-haiku-4-5-20251001', 'openai/gpt-4o-mini'.
        """
