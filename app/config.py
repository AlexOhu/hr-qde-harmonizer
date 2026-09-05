"""Zentrale Konfiguration, geladen aus Umgebungsvariablen (.env)."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # -------------------------------------------------------------------------
    # LLM-Provider (Schritt 3: Klassifikation, vgl. ADR-7 und VH1.6)
    #
    # LLM_PROVIDERS: kommagetrennte Liste von Anbieternamen in der Reihenfolge,
    # in der die Klassifikationsläufe per Round-Robin verteilt werden.
    #   "anthropic"                → alle drei Läufe über Anthropic Claude
    #   "mistral"                  → alle drei Läufe über Mistral
    #   "anthropic,openai,gemini"  → je ein Lauf pro Anbieter
    # Gültige Werte: anthropic, openai, gemini, mistral
    # -------------------------------------------------------------------------
    llm_providers: str = os.getenv("LLM_PROVIDERS", "anthropic")

    # Anthropic Claude — aktiv wenn "anthropic" in LLM_PROVIDERS
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    # OpenAI ChatGPT — aktiv wenn "openai" in LLM_PROVIDERS
    # Paket-Voraussetzung: pip install openai>=1.0
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Google Gemini — aktiv wenn "gemini" in LLM_PROVIDERS
    # Paket-Voraussetzung: pip install google-generativeai>=0.8
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # Mistral AI — aktiv wenn "mistral" in LLM_PROVIDERS
    # Paket-Voraussetzung: pip install mistralai>=1.0
    # Empfehlung für EU-Kontext: mistral-small-latest (EU-Rechenzentren, DSGVO)
    mistral_api_key: str = os.getenv("MISTRAL_API_KEY", "")
    mistral_model: str = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

    # Gilt für alle Provider (temperature=0 für maximale Reproduzierbarkeit,
    # vgl. VH1.6 — Nicht-Determinismus ist akzeptierte Randbedingung).
    classification_temperature: float = float(os.getenv("CLASSIFICATION_TEMPERATURE", "0"))
    classification_runs_per_pair: int = int(os.getenv("CLASSIFICATION_RUNS_PER_PAIR", "3"))

    # Neo4j
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "changeme123")

    # Embedding / Vorfilter (Schritt 2) — Modellwahl begründet in Kapitel 4,
    # Abschnitt "Modellwahl und Berechnung der Embeddings" (VH1.4, ADR-6).
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "intfloat/multilingual-e5-large-instruct"
    )
    ann_top_k: int = int(os.getenv("ANN_TOP_K", "20"))

    # React-Frontend (frontend/): erlaubte Browser-Origins fuer CORS.
    # Kommagetrennt in .env, Default deckt den Vite-Dev-Server ab.
    cors_allow_origins: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    ]

    # Export-Schwelle (vgl. VH1.7)
    # empirisch bestimmt, E3 (Kapitel 5, Tab. tab:exp3_confidence): theta_op = 0.67
    mapping_confidence_threshold: float = float(os.getenv("MAPPING_CONFIDENCE_THRESHOLD", "0.67"))


settings = Settings()
