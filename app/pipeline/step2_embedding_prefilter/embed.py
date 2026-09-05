"""
Schritt 2a: Vektor-Embeddings für alle Concept-Objekte berechnen.

Grundlage für die ANN-Suche (prefilter.py) und die HDBSCAN-Layer-Zuordnung
(clustering.py). Modellwahl ist laut Konzeption noch offen (VH1.4:
Mehrsprachigkeit, Instruction-Tuning, Reproduzierbarkeit) — der Default in
.env.example ist ein Platzhalter, kein empirisch validiertes Ergebnis.
"""

from __future__ import annotations

import numpy as np

from app.models.schemas import Concept

# Modul-Singleton je model_name, damit sentence-transformers nicht bei jedem
# Aufruf neu von der Platte/aus dem Netz geladen wird.
_model_cache: dict[str, object] = {}


def _get_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    if model_name not in _model_cache:
        _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]


def embed_concepts(concepts: list[Concept], model_name: str) -> dict[str, np.ndarray]:
    """
    Berechnet einen Embedding-Vektor je Concept (Basis: pref_label + definition).

    Rückgabe: Mapping von Concept.uri auf Vektor. Vektoren werden L2-normalisiert
    zurückgegeben, sodass Kosinus-Ähnlichkeit in Schritt 2b (prefilter.py) per
    Inner Product berechnet werden kann.
    """
    if not concepts:
        return {}

    model = _get_model(model_name)
    texts = [f"{c.pref_label}. {c.definition or ''}".strip() for c in concepts]
    vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return {concept.uri: vector for concept, vector in zip(concepts, vectors)}
