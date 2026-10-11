"""Export complete E4 cluster membership for the production ESCO/e-CF space.

Run from the repository root::

    python eval/E4_membership.py --output eval/results/E4_membership_prod1302.json

The script uses local Turtle input and the configured embedding model. It does
not call an LLM or replace any existing E4 result file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.pipeline.step2_embedding_prefilter.clustering import cluster_concepts
from app.pipeline.step2_embedding_prefilter.dag_builder import HRQDE_CLUSTER_BASE
from eval.E4_hdbscan import load_all_embeddings


KQR_IDS = ("esco_skeleton_oberhuber", "ecf")
TARGETS = {
    "A.1": "http://hr-qde.org/harmonised/ecf/A.1",
    "ICT capacity planning strategies": (
        "http://data.europa.eu/esco/skill/"
        "60d48be0-4260-4b2e-85b9-aedff7a9b7d9"
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-cluster-size", type=int, default=3)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    if args.min_cluster_size < 2:
        parser.error("--min-cluster-size must be at least 2")

    embeddings, lookup = load_all_embeddings(KQR_IDS)
    counts = {
        kqr_id: sum(item["kqr_id"] == kqr_id for item in lookup.values())
        for kqr_id in KQR_IDS
    }
    if counts != {"esco_skeleton_oberhuber": 1302, "ecf": 45}:
        raise RuntimeError(f"Unexpected input counts: {counts}")
    if len(embeddings) != len(lookup) or len(embeddings) != 1347:
        raise RuntimeError(
            f"Embedding/label count mismatch: {len(embeddings)} / {len(lookup)}"
        )

    results, _ = cluster_concepts(
        embeddings, lookup, min_cluster_size=args.min_cluster_size
    )
    memberships = {}
    clusters = []
    for result in sorted(results, key=lambda item: item.cluster_id):
        for uri in result.concept_uris:
            if uri in memberships:
                raise RuntimeError(f"Duplicate cluster membership: {uri}")
            memberships[uri] = result.cluster_id
        clusters.append({
            "cluster_id": result.cluster_id,
            "cluster_uri": (
                f"{HRQDE_CLUSTER_BASE}{result.cluster_id}"
                if result.cluster_id >= 0 else None
            ),
            "size": len(result.concept_uris),
            "n_esco": sum(lookup[uri]["kqr_id"] == KQR_IDS[0]
                          for uri in result.concept_uris),
            "n_ecf": sum(lookup[uri]["kqr_id"] == KQR_IDS[1]
                         for uri in result.concept_uris),
            "centroid_uri": result.centroid_uri,
            "auto_label": result.auto_label,
            "llm_label": result.llm_label,
        })
    if set(memberships) != set(embeddings):
        raise RuntimeError("Cluster output does not cover the embedding space")

    input_files = {
        kqr_id: ROOT / "data" / "formalized" / f"{kqr_id}.ttl"
        for kqr_id in KQR_IDS
    }
    data = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "app.pipeline.step2_embedding_prefilter.clustering.cluster_concepts",
        "min_cluster_size": args.min_cluster_size,
        "embedding_model": settings.embedding_model,
        "hdbscan_version": version("hdbscan"),
        "inputs": {
            kqr_id: {"path": str(path.relative_to(ROOT)).replace("\\", "/"),
                     "sha256": sha256(path), "n_concepts": counts[kqr_id]}
            for kqr_id, path in input_files.items()
        },
        "n_total": len(embeddings),
        "clusters": clusters,
        "targets": {
            name: {"uri": uri, "cluster_id": memberships[uri]}
            for name, uri in TARGETS.items()
        },
        "memberships": [
            {"uri": uri, "kqr_id": lookup[uri]["kqr_id"],
             "label": lookup[uri]["pref_label"], "cluster_id": memberships[uri]}
            for uri in sorted(memberships)
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(f"Saved {len(memberships)} concept memberships to {args.output}")
    print(json.dumps({"clusters": clusters, "targets": data["targets"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
