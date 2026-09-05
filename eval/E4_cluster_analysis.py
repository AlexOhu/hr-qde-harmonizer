"""
E4 – Cluster-Inhaltsanalyse (Zusatzauswertung zu VH₂.₃)

Analysiert die vier Cluster, die HDBSCAN bei m*=3 (E4, Tab. tab:exp4_hdbscan)
auf dem gemeinsamen Embedding-Raum aller KQR erzeugt. Für jeden Cluster wird
die KQR-Verteilung, das Zentroid-Konzept und die Top-20 nächstgelegenen
Konzepte bestimmt; ein LLM charakterisiert die gemeinsame Thematik in einem
Satz.

Verwendung:
    python eval/E4_cluster_analysis.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.E4_hdbscan import load_all_embeddings  # noqa: E402

OUTPUT_PATH = ROOT / "eval" / "results" / "E4_cluster_content.json"
MIN_CLUSTER_SIZE = 3
TOP_N = 20

CHARACTERIZATION_PROMPT = """Du charakterisierst einen semantischen Cluster aus einem
Ontologie-Harmonisierungsprojekt im IKT-Bereich.
Fasse die gemeinsame Thematik der folgenden Konzepte in einem
prägnanten deutschen Satz zusammen (max. 20 Wörter).
Konzepte: {labels}"""


def _top_n_by_distance(
    member_uris: list[str],
    embeddings: dict[str, np.ndarray],
    concept_lookup: dict[str, dict],
    centroid_uri: str,
    n: int,
) -> list[str]:
    """Top-n pref_labels, sortiert nach L2-Abstand zum Zentroid (nächste zuerst)."""
    centroid = embeddings[centroid_uri]
    vectors = np.stack([embeddings[uri] for uri in member_uris])
    distances = np.linalg.norm(vectors - centroid, axis=1)
    order = np.argsort(distances)
    ordered_uris = [member_uris[i] for i in order]
    labels = [
        concept_lookup[uri]["pref_label"]
        for uri in ordered_uris
        if uri in concept_lookup
    ]
    return labels[:n]


def characterize_cluster(provider, top_labels: list[str]) -> str:
    prompt = CHARACTERIZATION_PROMPT.format(labels=", ".join(top_labels))
    return provider.complete(prompt, max_tokens=200)


def main() -> None:
    from app.config import settings
    from app.pipeline.step2_embedding_prefilter.clustering import cluster_concepts
    from app.pipeline.step3_classification.llm_provider import get_providers_from_config

    print("Lade kombinierte Embeddings ...")
    embeddings, concept_lookup = load_all_embeddings()
    n_total = len(embeddings)
    print(f"Gesamt: {n_total} Konzepte im gemeinsamen Embedding-Raum\n")

    print(f"Clustere mit min_cluster_size={MIN_CLUSTER_SIZE} ...")
    results, _clusterer = cluster_concepts(
        embeddings, concept_lookup, min_cluster_size=MIN_CLUSTER_SIZE
    )

    noise = [r for r in results if r.cluster_id == -1]
    n_noise = sum(len(r.concept_uris) for r in noise)
    real_clusters = sorted(
        (r for r in results if r.cluster_id >= 0), key=lambda r: r.cluster_id
    )
    print(f"{len(real_clusters)} Cluster gefunden, {n_noise} Konzepte als Noise\n")

    provider = get_providers_from_config(settings)[0]
    print(f"LLM-Provider: {provider.model_id}\n")

    cluster_entries = []
    for r in real_clusters:
        kqr_distribution: dict[str, int] = {}
        for uri in r.concept_uris:
            kqr_id = concept_lookup.get(uri, {}).get("kqr_id", "?")
            kqr_distribution[kqr_id] = kqr_distribution.get(kqr_id, 0) + 1

        centroid_uri = r.centroid_uri
        centroid_label = concept_lookup.get(centroid_uri, {}).get("pref_label", "?")

        top20_labels = _top_n_by_distance(
            r.concept_uris, embeddings, concept_lookup, centroid_uri, TOP_N
        )

        print(f"  Cluster {r.cluster_id} (n={len(r.concept_uris)}): LLM-Charakterisierung ...")
        llm_label = characterize_cluster(provider, top20_labels)

        cluster_entries.append(
            {
                "cluster_id": r.cluster_id,
                "size": len(r.concept_uris),
                "kqr_distribution": kqr_distribution,
                "centroid_uri": centroid_uri,
                "centroid_label": centroid_label,
                "top20_labels": top20_labels,
                "llm_label": llm_label,
            }
        )

    output = {
        "m": MIN_CLUSTER_SIZE,
        "n_concepts_total": n_total,
        "n_noise": n_noise,
        "clusters": cluster_entries,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nErgebnis gespeichert: {OUTPUT_PATH}")

    print("\n--- E4: Cluster-Inhaltsanalyse (m=3) ---")
    for c in cluster_entries:
        dist_str = ", ".join(f"{k}={v}" for k, v in sorted(c["kqr_distribution"].items()))
        print(
            f"Cluster {c['cluster_id']:>2}  n={c['size']:>4}  [{dist_str}]  "
            f"Zentroid: '{c['centroid_label']}'\n"
            f"    LLM: {c['llm_label']}"
        )


if __name__ == "__main__":
    main()
