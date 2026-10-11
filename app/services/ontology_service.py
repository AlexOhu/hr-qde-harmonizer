"""
Orchestriert FZ2.3: Embeddings laden → HDBSCAN → DAG → Persistenz.
Analog zu classification_service: keine direkten Pipeline-Importe
in api/routes/, Orchestrierung ausschließlich hier.

Persistenz: data/projects/{project_id}/clusters.json (ClusterResult-Liste
als JSON, ADR-13), analog zu mappings.json. Zusätzlich wird die aus dem
Kondensationsbaum extrahierte Eltern-Kind-Zuordnung
(dag_builder.condensation_tree_to_dag) in
data/projects/{project_id}/clusters_dag.json abgelegt, da das
hdbscan.HDBSCAN-Objekt selbst nicht JSON-serialisierbar ist und daher nicht
wie die Embeddings-Caches in kqr_service ausschließlich im Prozessspeicher
gehalten werden kann, ohne den DAG nach einem uvicorn---reload-Neustart zu
verlieren. In-Memory-Caches sind nach project_id kodiert (ADR-13).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.models.schemas import ClusterResult, HarmonisedCluster
from app.pipeline.step2_embedding_prefilter.clustering import cluster_concepts
from app.pipeline.step2_embedding_prefilter.dag_builder import (
    build_harmonised_clusters,
    condensation_tree_to_dag,
)
from app.services import kqr_service, project_service

_cluster_results: dict[str, list[ClusterResult]] = {}
_dag: dict[str, dict[int, int | None]] = {}


def _clusters_path(project_id: str) -> Path:
    return project_service.get_project_data_dir(project_id) / "clusters.json"


def _dag_path(project_id: str) -> Path:
    return project_service.get_project_data_dir(project_id) / "clusters_dag.json"


def _load_cluster_results(project_id: str) -> list[ClusterResult]:
    path = _clusters_path(project_id)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ClusterResult(**item) for item in data]


def _load_dag(project_id: str) -> dict[int, int | None]:
    path = _dag_path(project_id)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(key): value for key, value in data.items()}


def _get_cluster_results(project_id: str) -> list[ClusterResult]:
    if project_id not in _cluster_results:
        _cluster_results[project_id] = _load_cluster_results(project_id)
    return _cluster_results[project_id]


def _get_dag(project_id: str) -> dict[int, int | None]:
    if project_id not in _dag:
        _dag[project_id] = _load_dag(project_id)
    return _dag[project_id]


def _save(project_id: str) -> None:
    clusters_path = _clusters_path(project_id)
    clusters_path.parent.mkdir(parents=True, exist_ok=True)
    clusters_path.write_text(
        json.dumps(
            [result.model_dump(mode="json") for result in _get_cluster_results(project_id)],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _dag_path(project_id).write_text(
        json.dumps(
            {str(key): value for key, value in _get_dag(project_id).items()}, indent=2, ensure_ascii=False
        ),
        encoding="utf-8",
    )


def run_clustering(
    kqr_ids: list[str],
    min_cluster_size: int = 3,  # empirisch bestimmt, E4 (Kapitel 5, Tab. tab:exp4_hdbscan)
    project_id: str = "default",
) -> list[ClusterResult]:
    """
    Führt HDBSCAN über alle Konzepte der angegebenen KQR aus.
    Embeddings werden aus kqr_service.get_embeddings() geladen
    (analog zu _run_job in classification_service).
    Ergebnis wird in data/projects/{project_id}/clusters.json persistiert.
    """
    project_service.ensure_writable(project_id)

    embeddings: dict[str, np.ndarray] = {}
    concept_lookup: dict[str, dict] = {}
    for kqr_id in kqr_ids:
        embeddings.update(kqr_service.get_embeddings(kqr_id))
        for concept in kqr_service.get_concepts(kqr_id):
            concept_lookup[concept.uri] = {"pref_label": concept.pref_label, "kqr_id": concept.kqr_id}

    results, clusterer = cluster_concepts(embeddings, concept_lookup, min_cluster_size=min_cluster_size)
    dag = condensation_tree_to_dag(clusterer) if embeddings else {}

    _cluster_results[project_id] = results
    _dag[project_id] = dag
    _save(project_id)
    return list(_get_cluster_results(project_id))


def get_cluster_results(project_id: str = "default") -> list[ClusterResult]:
    """Lädt persistierte ClusterResults; leere Liste wenn noch nicht berechnet."""
    return list(_get_cluster_results(project_id))


def get_harmonised_clusters(project_id: str = "default") -> list[HarmonisedCluster]:
    """
    Baut HarmonisedCluster aus den gespeicherten ClusterResults + DAG.
    Noise-Cluster (id == -1) werden herausgefiltert.
    Verwendet die beim Clustering-Lauf deterministisch vergebenen
    auto_label/llm_label-Werte weiter (kein LLM-Aufruf im kritischen
    Anzeigepfad — LLM-Verfeinerung ist ein separater optionaler Schritt).
    """
    return build_harmonised_clusters(_get_cluster_results(project_id), _get_dag(project_id))


def reset(project_id: str = "default") -> None:
    """Leert den In-Memory-Store eines Projekts (primär für Tests)."""
    _cluster_results.pop(project_id, None)
    _dag.pop(project_id, None)
