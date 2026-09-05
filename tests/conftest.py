from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.pipeline.step3_classification.llm_provider.base import LLMProvider

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def hub_ttl() -> str:
    return (FIXTURES_DIR / "hub_kqr.ttl").read_text(encoding="utf-8")


@pytest.fixture
def satellite_ttl() -> str:
    return (FIXTURES_DIR / "satellite_kqr.ttl").read_text(encoding="utf-8")


class FakeSentenceTransformer:
    """Deterministischer Ersatz für sentence_transformers.SentenceTransformer,
    damit Tests ohne Netzwerkzugriff/Modell-Download laufen. Erzeugt einen
    reproduzierbaren, aber inhaltlich bedeutungslosen Vektor je Eingabetext."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def encode(self, texts: list[str], convert_to_numpy: bool = True, normalize_embeddings: bool = True):
        vectors = []
        for text in texts:
            rng = np.random.default_rng(abs(hash(text)) % (2**32))
            vector = rng.normal(size=16)
            if normalize_embeddings:
                vector = vector / np.linalg.norm(vector)
            vectors.append(vector)
        return np.stack(vectors)


@pytest.fixture
def mock_sentence_transformer(monkeypatch):
    """Ersetzt sentence_transformers.SentenceTransformer global und leert den
    Modul-Singleton-Cache in embed.py, damit die Fake-Klasse tatsächlich
    verwendet wird."""
    import sentence_transformers

    from app.pipeline.step2_embedding_prefilter import embed

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", FakeSentenceTransformer)
    embed._model_cache.clear()
    yield
    embed._model_cache.clear()


class FakeLLMProvider(LLMProvider):
    """Deterministischer LLMProvider für Tests — kein echter API-Aufruf.

    Liefert eine feste Antwort oder das Ergebnis einer Callable. Kein
    Monkeypatching nötig: Instanz direkt als 'provider'-Argument übergeben.

    Beispiel:
        provider = FakeLLMProvider("EQUIVALENT | Testbegründung")
        run = call_classification_model("prompt", provider=provider)
    """

    def __init__(
        self,
        response_text: str | callable = "EQUIVALENT | Testbegründung",
        model_name: str = "fake/test-model",
    ) -> None:
        self._response_text = response_text
        self._model_name = model_name
        self.calls: list[str] = []

    @property
    def model_id(self) -> str:
        return self._model_name

    def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        if callable(self._response_text):
            return self._response_text(prompt)
        return self._response_text


@pytest.fixture
def fake_provider():
    """Gibt eine Factory zurück, die FakeLLMProvider-Instanzen erzeugt.

    Verwendung im Test:
        def test_something(fake_provider):
            provider = fake_provider("EQUIVALENT | Grund")
            run = call_classification_model("prompt", provider=provider)
    """
    def _factory(
        response_text: str | callable = "EQUIVALENT | Testbegründung",
        model_name: str = "fake/test-model",
    ) -> FakeLLMProvider:
        return FakeLLMProvider(response_text, model_name)

    return _factory


@pytest.fixture
def mock_anthropic(monkeypatch):
    """Patcht get_providers_from_config im classification_service durch FakeLLMProvider.

    Der Fixture-Name bleibt für Rückwärtskompatibilität erhalten. Nach dem
    Provider-Refactoring patcht er nicht mehr anthropic.Anthropic direkt,
    sondern die Provider-Factory — damit sind Integrationstests vom konkreten
    Anbieter entkoppelt.

    Rückgabe ist eine Factory, die den Antworttext konfiguriert:
        mock_anthropic("EQUIVALENT | Grund")
        mock_anthropic(lambda prompt: next(response_iter))
    """
    import app.services.classification_service as svc_module

    def _factory(response_text: str | callable = "EQUIVALENT | Testbegründung"):
        provider = FakeLLMProvider(response_text)

        def _fake_get_providers(_settings):
            return [provider]

        monkeypatch.setattr(svc_module, "get_providers_from_config", _fake_get_providers)
        return provider

    return _factory


@pytest.fixture
def isolated_services(tmp_path, monkeypatch):
    """Isoliert die In-Memory-/Datei-Services (kqr_service, project_service
    und die darauf aufbauenden projektspezifischen Services) für einen Test:
    Registry/Rohdaten/Formalisiert-Ordner sowie das data/projects/-Verzeichnis
    zeigen auf ein tmp_path-Verzeichnis statt auf das echte data/, und alle
    Module-Caches werden geleert.

    mapping_service, classification_service, disjoint_service und
    ontology_service leiten ihre Dateipfade ausschließlich über
    project_service.get_project_data_dir(project_id) ab -- ein einziges
    Monkeypatch von project_service.DATA_DIR genügt daher, um alle vier
    Services gleichzeitig zu isolieren (ADR-01/ADR-02)."""
    from app.services import classification_service, disjoint_service, kqr_service, mapping_service, ontology_service, project_service

    data_dir = tmp_path / "data"
    monkeypatch.setattr(kqr_service, "DATA_DIR", data_dir)
    monkeypatch.setattr(kqr_service, "RAW_DIR", data_dir / "raw")
    monkeypatch.setattr(kqr_service, "FORMALIZED_DIR", data_dir / "formalized")
    monkeypatch.setattr(kqr_service, "REGISTRY_PATH", data_dir / "kqr_registry.json")
    kqr_service.reload_registry()

    monkeypatch.setattr(project_service, "DATA_DIR", data_dir)

    mapping_service._mappings.clear()
    mapping_service._classification_results.clear()
    classification_service._jobs.clear()
    classification_service._pause_events.clear()
    ontology_service._cluster_results.clear()
    ontology_service._dag.clear()
    disjoint_service._decisions.clear()

    yield

    mapping_service._mappings.clear()
    mapping_service._classification_results.clear()
    classification_service._jobs.clear()
    classification_service._pause_events.clear()
    ontology_service._cluster_results.clear()
    ontology_service._dag.clear()
    disjoint_service._decisions.clear()
