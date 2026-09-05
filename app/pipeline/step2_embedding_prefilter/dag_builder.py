"""
Überführt den HDBSCAN-Kondensationsbaum in einen gerichteten azyklischen
Graphen (DAG) mit rdfs:subClassOf-Semantik (FZ2.3, Abschnitt 4.4.2).

Abhängigkeit: hdbscan.HDBSCAN-Objekt aus clustering.cluster_concepts().
Kein LLM-Aufruf in condensation_tree_to_dag() und name_clusters_auto()
— beide Funktionen sind ohne Mock testbar (vgl. CLAUDE.md-Prinzip
"Pipeline-Schritte sind unabhängig testbar").

Hinweis zur Implementierung: hdbscan legt den Kondensationsbaum unter dem
Attribut `condensed_tree_` ab (nicht `condensation_tree_`). Dessen
`to_pandas()`-Darstellung enthält Knoten-IDs 0..n-1 für die einzelnen
Datenpunkte (Reihenfolge wie beim `fit_predict()`-Aufruf) und IDs >= n für
interne (nicht notwendigerweise final ausgewählte) Cluster-Knoten. Um die
final durch `labels_` ausgewählten Cluster im Baum wiederzufinden, wird je
Cluster die Menge seiner Blatt-Punkte mit den Blattmengen der internen
Baumknoten abgeglichen (deterministisch, kein Sampling).
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

from app.models.schemas import ClusterResult, HarmonisedCluster

if TYPE_CHECKING:
    import hdbscan

    from app.pipeline.step3_classification.llm_provider.base import LLMProvider

logger = logging.getLogger(__name__)

HRQDE_CLUSTER_BASE = "http://hr-qde.org/harmonised/cluster/"


def condensation_tree_to_dag(
    clusterer: "hdbscan.HDBSCAN",
) -> dict[int, int | None]:
    """
    Extrahiert die Eltern-Kind-Beziehungen zwischen den final ausgewählten
    Clustern (clusterer.labels_) aus dem Kondensationsbaum.

    Rückgabe: {cluster_id: parent_cluster_id | None (= Wurzel)}. Noise
    (-1) taucht nicht als Schlüssel auf. Ein Cluster gilt als Kind eines
    anderen, wenn sein Baumknoten im Kondensationsbaum ein Nachfahre des
    Baumknotens des anderen Clusters ist (nächstgelegener ausgewählter
    Vorfahre).
    """
    labels = list(clusterer.labels_)
    n_points = len(labels)
    tree_df = clusterer.condensed_tree_.to_pandas()

    children_of: dict[int, list[int]] = {}
    parent_of: dict[int, int] = {}
    for row in tree_df.itertuples():
        parent, child = int(row.parent), int(row.child)
        children_of.setdefault(parent, []).append(child)
        parent_of[child] = parent

    leaves_cache: dict[int, set[int]] = {}

    def leaves_of(node: int) -> set[int]:
        if node < n_points:
            return {node}
        if node not in leaves_cache:
            result: set[int] = set()
            for child in children_of.get(node, []):
                result |= leaves_of(child)
            leaves_cache[node] = result
        return leaves_cache[node]

    cluster_ids = sorted({label for label in labels if label != -1})
    node_for_cluster: dict[int, int] = {}
    for cluster_id in cluster_ids:
        expected = {index for index, label in enumerate(labels) if label == cluster_id}
        for node in children_of:
            if leaves_of(node) == expected:
                node_for_cluster[cluster_id] = node
                break

    selected_nodes = set(node_for_cluster.values())
    dag: dict[int, int | None] = {}
    for cluster_id, node in node_for_cluster.items():
        ancestor = parent_of.get(node)
        while ancestor is not None and ancestor not in selected_nodes:
            ancestor = parent_of.get(ancestor)
        if ancestor is None:
            dag[cluster_id] = None
        else:
            dag[cluster_id] = next(
                cid for cid, candidate_node in node_for_cluster.items() if candidate_node == ancestor
            )
    return dag


def name_clusters_auto(
    clusters: list[ClusterResult],
    concept_lookup: dict[str, dict],
) -> dict[int, str]:
    """
    Benennt jeden Cluster deterministisch durch das häufigste prefLabel
    seiner Mitgliedskonzepte. Kein LLM-Aufruf. Grundlage für Schicht 1
    der zweistufigen Benennung (Abschnitt 4.4.2).
    """
    labels: dict[int, str] = {}
    for cluster in clusters:
        member_labels = [
            concept_lookup[uri]["pref_label"] for uri in cluster.concept_uris if uri in concept_lookup
        ]
        labels[cluster.cluster_id] = (
            Counter(member_labels).most_common(1)[0][0] if member_labels else cluster.auto_label
        )
    return labels


def name_clusters_llm(
    clusters: list[ClusterResult],
    concept_lookup: dict[str, dict],
    provider: "LLMProvider",
) -> dict[int, str]:
    """
    Verfeinert die auto-Labels per LLM (Schicht 2). Kurzer Prompt:
    Liste der prefLabels im Cluster → prägnanter Oberbegriff.
    Modellwahl vorläufig (VH1.6), über den `provider`-Parameter freigelegt.
    Fehler (Timeout, Parse-Fehler) führen zu explizit geloggtem Fallback auf
    auto_label, niemals zu einer Exception oder stiller None-Rückgabe.
    """
    auto_labels = name_clusters_auto(clusters, concept_lookup)
    llm_labels: dict[int, str] = {}
    for cluster in clusters:
        if cluster.cluster_id == -1:
            llm_labels[cluster.cluster_id] = auto_labels[cluster.cluster_id]
            continue

        pref_labels = [
            concept_lookup[uri]["pref_label"] for uri in cluster.concept_uris if uri in concept_lookup
        ]
        prompt = (
            "Gegeben ist eine Liste von Fachbegriffen aus einem Kompetenz-/"
            "Qualifikationsrahmenwerk, die laut Clustering-Algorithmus semantisch "
            "zusammengehören. Nenne einen prägnanten deutschen Oberbegriff "
            "(max. 5 Wörter), der diese Gruppe treffend zusammenfasst. Antworte "
            f"NUR mit dem Oberbegriff.\n\nBegriffe: {', '.join(pref_labels)}"
        )
        try:
            response = provider.complete(prompt, max_tokens=30).strip()
            llm_labels[cluster.cluster_id] = response or auto_labels[cluster.cluster_id]
        except Exception:
            logger.warning(
                "LLM-Label-Verfeinerung für Cluster %s fehlgeschlagen, Fallback auf auto_label.",
                cluster.cluster_id,
                exc_info=True,
            )
            llm_labels[cluster.cluster_id] = auto_labels[cluster.cluster_id]
    return llm_labels


def build_harmonised_clusters(
    clusters: list[ClusterResult],
    dag: dict[int, int | None],
) -> list[HarmonisedCluster]:
    """
    Kombiniert ClusterResult + DAG zu HarmonisedCluster-Objekten.
    URI-Schema: {HRQDE_CLUSTER_BASE}{cluster_id}
    Noise-Cluster (id == -1) werden nicht als HarmonisedCluster ausgegeben —
    ihre Konzepte sind Kandidaten für disjoint_service.py (Phase 2).
    """
    harmonised: list[HarmonisedCluster] = []
    for cluster in clusters:
        if cluster.cluster_id == -1:
            continue
        parent_id = dag.get(cluster.cluster_id)
        harmonised.append(
            HarmonisedCluster(
                cluster_uri=f"{HRQDE_CLUSTER_BASE}{cluster.cluster_id}",
                label=cluster.llm_label or cluster.auto_label,
                parent_cluster_uri=(
                    f"{HRQDE_CLUSTER_BASE}{parent_id}" if parent_id is not None else None
                ),
                member_uris=list(cluster.concept_uris),
            )
        )
    return harmonised
