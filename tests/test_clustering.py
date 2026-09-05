"""
Synthetische Embeddings (4 klar trennbare Cluster à 10 Konzepte,
2D-Vektoren, kein echtes Embedding-Modell nötig).
"""

from __future__ import annotations

import numpy as np
import pytest

from app.pipeline.step2_embedding_prefilter.clustering import cluster_concepts
from app.pipeline.step2_embedding_prefilter.dag_builder import (
    build_harmonised_clusters,
    condensation_tree_to_dag,
    name_clusters_auto,
)

_GROUP_CENTERS = {
    "GroupA": (0.0, 0.0),
    "GroupB": (10.0, 10.0),
    "GroupC": (0.0, 10.0),
    "GroupD": (10.0, 0.0),
}


@pytest.fixture
def synthetic_embeddings() -> tuple[dict[str, np.ndarray], dict[str, dict]]:
    rng = np.random.default_rng(42)
    embeddings: dict[str, np.ndarray] = {}
    concept_lookup: dict[str, dict] = {}
    for group_label, center in _GROUP_CENTERS.items():
        for index in range(10):
            uri = f"http://example.org/{group_label}_{index}"
            vector = np.array(center) + rng.normal(scale=0.05, size=2)
            embeddings[uri] = vector
            concept_lookup[uri] = {"pref_label": group_label, "kqr_id": "kqr1"}
    return embeddings, concept_lookup


def test_cluster_concepts_finds_four_clusters_without_noise(synthetic_embeddings):
    embeddings, concept_lookup = synthetic_embeddings

    results, clusterer = cluster_concepts(embeddings, concept_lookup, min_cluster_size=5)

    assert clusterer is not None
    non_noise = [r for r in results if r.cluster_id != -1]
    assert len(non_noise) == 4
    assert sum(len(r.concept_uris) for r in non_noise) == 40


def test_cluster_result_cluster_ids_are_unique(synthetic_embeddings):
    embeddings, concept_lookup = synthetic_embeddings

    results, _ = cluster_concepts(embeddings, concept_lookup, min_cluster_size=5)

    cluster_ids = [r.cluster_id for r in results]
    assert len(cluster_ids) == len(set(cluster_ids))


def test_cluster_result_auto_label_matches_group(synthetic_embeddings):
    embeddings, concept_lookup = synthetic_embeddings

    results, _ = cluster_concepts(embeddings, concept_lookup, min_cluster_size=5)

    for result in results:
        if result.cluster_id == -1:
            continue
        member_labels = {concept_lookup[uri]["pref_label"] for uri in result.concept_uris}
        assert result.auto_label in member_labels
        assert result.centroid_uri in result.concept_uris


def test_condensation_tree_to_dag_returns_parent_mapping(synthetic_embeddings):
    embeddings, concept_lookup = synthetic_embeddings

    results, clusterer = cluster_concepts(embeddings, concept_lookup, min_cluster_size=5)
    non_noise_ids = {r.cluster_id for r in results if r.cluster_id != -1}

    dag = condensation_tree_to_dag(clusterer)

    assert set(dag.keys()) == non_noise_ids
    for cluster_id, parent_id in dag.items():
        assert parent_id is None or parent_id in non_noise_ids
        assert parent_id != cluster_id


def test_name_clusters_auto_returns_nonempty_label_per_cluster(synthetic_embeddings):
    embeddings, concept_lookup = synthetic_embeddings

    results, _ = cluster_concepts(embeddings, concept_lookup, min_cluster_size=5)

    labels = name_clusters_auto(results, concept_lookup)

    assert set(labels.keys()) == {r.cluster_id for r in results}
    for label in labels.values():
        assert isinstance(label, str)
        assert label.strip() != ""


def test_build_harmonised_clusters_filters_noise(synthetic_embeddings):
    embeddings, concept_lookup = synthetic_embeddings

    results, clusterer = cluster_concepts(embeddings, concept_lookup, min_cluster_size=5)
    dag = condensation_tree_to_dag(clusterer)

    harmonised = build_harmonised_clusters(results, dag)

    assert len(harmonised) == len([r for r in results if r.cluster_id != -1])
    for cluster in harmonised:
        assert "-1" not in cluster.cluster_uri.rsplit("/", 1)[-1]


def test_noise_concepts_do_not_appear_in_harmonised_member_uris():
    # Ein klarer Cluster (10 Punkte) plus zwei weit entfernte Einzelpunkte,
    # die als Noise (-1) klassifiziert werden sollten.
    rng = np.random.default_rng(1)
    embeddings: dict[str, np.ndarray] = {}
    concept_lookup: dict[str, dict] = {}
    for index in range(10):
        uri = f"http://example.org/cluster_{index}"
        embeddings[uri] = np.array([0.0, 0.0]) + rng.normal(scale=0.05, size=2)
        concept_lookup[uri] = {"pref_label": "Cluster", "kqr_id": "kqr1"}

    for index, far_point in enumerate([(50.0, 50.0), (-50.0, -50.0)]):
        uri = f"http://example.org/outlier_{index}"
        embeddings[uri] = np.array(far_point)
        concept_lookup[uri] = {"pref_label": "Outlier", "kqr_id": "kqr1"}

    results, clusterer = cluster_concepts(embeddings, concept_lookup, min_cluster_size=5)
    noise_uris = {uri for r in results if r.cluster_id == -1 for uri in r.concept_uris}
    assert noise_uris, "Testaufbau erwartet mindestens einen Noise-Punkt"

    dag = condensation_tree_to_dag(clusterer)
    harmonised = build_harmonised_clusters(results, dag)

    all_member_uris = {uri for cluster in harmonised for uri in cluster.member_uris}
    assert all_member_uris.isdisjoint(noise_uris)


def test_cluster_concepts_empty_input_returns_empty_list():
    results, clusterer = cluster_concepts({}, {}, min_cluster_size=5)
    assert results == []
    assert clusterer is not None


def test_hopkins_uniform_data():
    """Gleichmäßig verteilte Punkte auf Hypersphäre → H ≈ 0.5."""
    from eval.E4_hdbscan import hopkins_statistic
    # Bewusst anderer Seed als der hopkins_statistic()-Aufruf (random_state=0):
    # identische Seeds für Datengenerierung und internen RNG führen bei
    # numpy PCG64 zu einer bitweisen Stream-Überlappung (choice() rückt den
    # Zustand um genau n_samples Draws vor, was exakt auf die ersten Zeilen
    # der Ausgangsdaten trifft) und damit zu degenerierten Distanzen (H=0).
    rng = np.random.default_rng(7)
    raw = rng.standard_normal((200, 10))
    uniform = raw / np.linalg.norm(raw, axis=1, keepdims=True)
    h = hopkins_statistic(uniform, n_samples=30, random_state=0)
    assert 0.35 < h < 0.65, f"Erwarteter Bereich 0.35–0.65, bekommen: {h:.4f}"


def test_hopkins_clustered_data():
    """Klar geclusterte Punkte → H > 0.7."""
    from eval.E4_hdbscan import hopkins_statistic
    rng = np.random.default_rng(1)
    centers = np.array([[1,0,0,0,0], [0,1,0,0,0], [0,0,1,0,0]], dtype=float)
    points = []
    for c in centers:
        noise = rng.standard_normal((60, 5)) * 0.05
        cluster = c + noise
        cluster /= np.linalg.norm(cluster, axis=1, keepdims=True)
        points.append(cluster)
    clustered = np.vstack(points)
    h = hopkins_statistic(clustered, n_samples=30, random_state=1)
    assert h > 0.7, f"Erwarteter Wert > 0.7, bekommen: {h:.4f}"
