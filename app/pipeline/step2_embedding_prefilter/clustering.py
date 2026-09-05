"""
Schritt 2c (optional): HDBSCAN-Clustering im gemeinsamen Embedding-Raum.

Dient der datengetriebenen Zuordnung von Konzepten zu semantischen Schichten
(vgl. VH1.1, Abschnitt 2.2.4.3). Der resultierende Kondensationsbaum kann
prinzipiell in eine rdfs:subClassOf-Hierarchie überführt werden.

Hinweis aus der Konzeption: k-Means & Co. sind hier explizit NICHT geeignet
(kein Kondensationsbaum) — nur als Vergleichsbaseline in der Evaluation.
"""

from __future__ import annotations

from collections import Counter

import hdbscan
import numpy as np

from app.models.schemas import ClusterResult


def cluster_concepts(
    embeddings: dict[str, np.ndarray],
    concept_lookup: dict[str, dict],  # uri -> {"pref_label": ..., "kqr_id": ...}
    min_cluster_size: int = 3,  # empirisch bestimmt, E4 (Kapitel 5, Tab. tab:exp4_hdbscan)
) -> tuple[list[ClusterResult], "hdbscan.HDBSCAN"]:
    """
    Clustert alle Konzepte beider KQR im gemeinsamen Embedding-Raum per HDBSCAN.

    Gibt (ClusterResult-Liste, HDBSCAN-Objekt) zurück; Cluster-ID -1 = Noise/
    Ausreißer. Das HDBSCAN-Objekt wird mitgegeben, damit dag_builder.py den
    Kondensationsbaum (clusterer.condensation_tree_) separat extrahieren kann.

    Noise-Konzepte (cluster_id == -1) werden in der Liste mitgeführt, damit
    disjoint_service.py sie als Kandidaten für die Integrationsstrategie
    verwenden kann (Phase 2).
    """
    uris = list(embeddings.keys())
    if not uris:
        empty_clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, metric="euclidean")
        return [], empty_clusterer

    vectors = np.stack([embeddings[uri] for uri in uris])

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        metric="euclidean",
        gen_min_span_tree=True,
    )
    labels = clusterer.fit_predict(vectors)

    clusters: dict[int, list[str]] = {}
    for uri, label in zip(uris, labels):
        clusters.setdefault(int(label), []).append(uri)

    results: list[ClusterResult] = []
    for cluster_id, member_uris in clusters.items():
        auto_label = _most_common_label(member_uris, concept_lookup)
        centroid_uri = _centroid_uri(member_uris, embeddings) if cluster_id != -1 else None
        results.append(
            ClusterResult(
                cluster_id=cluster_id,
                concept_uris=member_uris,
                auto_label=auto_label,
                centroid_uri=centroid_uri,
            )
        )

    return results, clusterer


def _most_common_label(member_uris: list[str], concept_lookup: dict[str, dict]) -> str:
    labels = [concept_lookup[uri]["pref_label"] for uri in member_uris if uri in concept_lookup]
    if not labels:
        return "?"
    return Counter(labels).most_common(1)[0][0]


def _centroid_uri(member_uris: list[str], embeddings: dict[str, np.ndarray]) -> str:
    vectors = np.stack([embeddings[uri] for uri in member_uris])
    centroid = vectors.mean(axis=0)
    distances = np.linalg.norm(vectors - centroid, axis=1)
    return member_uris[int(np.argmin(distances))]
