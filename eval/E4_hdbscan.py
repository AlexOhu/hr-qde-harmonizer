"""
E4 – HDBSCAN-Parametersweep (VH₂.₃)

Variiert min_cluster_size m ∈ {3, 5, 8, 10, 15} und berechnet
Silhouette-Koeffizient, Davies-Bouldin-Index, Cluster-Anzahl
und Noise-Rate auf dem kombinierten Embedding-Raum aller KQR.

Verwendung:
    python eval/E4_hdbscan.py [--m-values 3 5 8 10 15]
                               [--output eval/results/E4_hdbscan.json]
    python eval/E4_hdbscan.py --report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import KDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUTPUT_DIR = ROOT / "eval" / "results"
NOISE_RATE_LIMIT = 0.20   # Ausschlusskriterium

# Produktiver Matching-Raum: ausschliesslich harm:CompetenceConcept-KQR
# (ESCO-Hub + e-CF-Satellit). Niveaurahmen (DQR, EQF) sind harm:LevelConcept
# und laufen im Produktivpfad nicht durch ANN/Clustering; sie werden hier
# bewusst ausgeschlossen (Entscheidung 2026-08-31, vgl. eval/PROTOKOLL.md).
# Ueber --kqr-ids ueberschreibbar (etwa fuer eine Sensitivitaetsanalyse mit DQR).
E4_DEFAULT_KQR_IDS = ("esco_v1_2_ict_ausschnitt", "ecf")


def hopkins_statistic(
    matrix: np.ndarray,
    n_samples: int | None = None,
    random_state: int = 42,
) -> float:
    """Hopkins-Statistik für Daten auf der Einheitshypersphäre (VH₂.₄)."""
    rng = np.random.default_rng(random_state)
    n, d = matrix.shape
    s = n_samples if n_samples is not None else max(50, n // 10)
    s = min(s, n - 1)

    # Schritt 1: Zufällige Stichprobe aus den echten Datenpunkten
    idx = rng.choice(n, size=s, replace=False)
    p = matrix[idx]

    # Schritt 2: Zufällige Punkte auf der Einheitshypersphäre
    raw = rng.standard_normal((s, d))
    u = raw / np.linalg.norm(raw, axis=1, keepdims=True)

    # Schritt 3 + 4: NN-Abstände via KDTree
    tree = KDTree(matrix)
    # k=2 für p-Punkte: Index 0 ist der Punkt selbst, Index 1 ist echter NN
    w_dists, _ = tree.query(p, k=2)
    w = w_dists[:, 1]
    # k=1 für u-Punkte: kein Ausschluss nötig (KDTree.query gibt bei k=1 ein 1D-Array zurück)
    x, _ = tree.query(u, k=1)

    return float(x.sum() / (x.sum() + w.sum()))


def load_all_embeddings(
    kqr_ids: tuple[str, ...] = E4_DEFAULT_KQR_IDS,
) -> tuple[dict[str, np.ndarray], dict[str, dict]]:
    """Kombiniert Embeddings der in ``kqr_ids`` genannten KQR (Status BEREIT).

    Die explizite Allowlist macht den Sweep unabhaengig vom (zeitweise mit
    Walkthrough-/Experiment-KQR verschmutzten) Registrierungsstand.
    """
    from app.services import kqr_service
    from app.models.schemas import KQRStatus

    allow = set(kqr_ids)
    all_embeddings: dict[str, np.ndarray] = {}
    concept_lookup: dict[str, dict] = {}
    for kqr in kqr_service.list_kqr():
        if kqr.id not in allow:
            print(f"  Überspringe '{kqr.id}' (nicht in --kqr-ids)")
            continue
        if kqr.status != KQRStatus.BEREIT:
            print(f"  Überspringe '{kqr.id}' (Status: {kqr.status})")
            continue
        emb = kqr_service.get_embeddings(kqr.id)
        all_embeddings.update(emb)
        for c in kqr_service.get_concepts(kqr.id):
            concept_lookup[c.uri] = {
                "pref_label": c.pref_label, "kqr_id": c.kqr_id
            }
        print(f"  '{kqr.id}': {len(emb)} Vektoren geladen")
    return all_embeddings, concept_lookup


def run_one(
    embeddings: dict[str, np.ndarray],
    concept_lookup: dict[str, dict],
    m: int,
) -> dict:
    from sklearn.metrics import silhouette_score, davies_bouldin_score
    from app.pipeline.step2_embedding_prefilter.clustering import cluster_concepts

    results, _ = cluster_concepts(embeddings, concept_lookup, min_cluster_size=m)

    uris   = list(embeddings.keys())
    matrix = np.stack([embeddings[u] for u in uris])
    labels = []
    uri_to_label: dict[str, int] = {}
    for r in results:
        for uri in r.concept_uris:
            uri_to_label[uri] = r.cluster_id
    labels = np.array([uri_to_label.get(u, -1) for u in uris])

    non_noise_mask = labels != -1
    n_total = len(labels)
    n_noise  = int((labels == -1).sum())
    noise_rate = n_noise / n_total if n_total else 0.0
    n_clusters = len({l for l in labels if l != -1})

    # Silhouette und DB nur auf nicht-Noise-Punkten berechenbar
    if n_clusters >= 2 and non_noise_mask.sum() >= 2:
        sil = float(silhouette_score(
            matrix[non_noise_mask], labels[non_noise_mask], metric="euclidean"
        ))
        db  = float(davies_bouldin_score(
            matrix[non_noise_mask], labels[non_noise_mask]
        ))
    else:
        sil, db = float("nan"), float("nan")

    return {
        "m": m, "silhouette": round(sil, 4), "davies_bouldin": round(db, 4),
        "n_clusters": n_clusters, "noise_rate": round(noise_rate, 4),
        "n_noise": n_noise, "n_total": n_total,
    }


def run_experiment(
    m_values: list[int], kqr_ids: tuple[str, ...] = E4_DEFAULT_KQR_IDS
) -> dict:
    print("Lade kombinierte Embeddings ...")
    embeddings, concept_lookup = load_all_embeddings(kqr_ids)
    print(f"Gesamt: {len(embeddings)} Konzepte im gemeinsamen Embedding-Raum\n")

    # Hopkins-Vorvalidierung (VH₂.₄)
    print("Berechne Hopkins-Statistik ...")
    matrix_all = np.stack(list(embeddings.values()))
    h = hopkins_statistic(matrix_all)
    print(f"Hopkins H = {h:.4f}  ", end="")
    if h < 0.55:
        print("→ kein Clustering-Signal (H ≈ 0.5: zufällige Verteilung)")
    elif h < 0.75:
        print("→ schwaches Clustering-Signal")
    else:
        print("→ Clustering-Tendenz vorhanden (H > 0.75)")
    print()

    results = []
    for m in sorted(m_values):
        print(f"m={m} ...", end=" ", flush=True)
        row = run_one(embeddings, concept_lookup, m)
        results.append(row)
        print(
            f"S={row['silhouette']:.4f}  DB={row['davies_bouldin']:.4f}"
            f"  Cluster={row['n_clusters']}  η={row['noise_rate']:.2%}"
        )
    return {"hopkins_h": round(h, 4), "results": results}

def report(data: dict) -> None:
    h = data.get("hopkins_h")
    results = data["results"]
    if h is not None:
        print(f"\nHopkins H = {h:.4f}", end="  ")
        if h < 0.55:
            print("(kein Clustering-Signal)")
        elif h < 0.75:
            print("(schwaches Signal)")
        else:
            print("(Clustering-Tendenz vorhanden)")
    print("\n--- E4: HDBSCAN-Parametersweep ---")
    print(f"{'m':>4} {'Silhouette':>12} {'Davies-Bouldin':>16}"
          f" {'Cluster':>8} {'η':>8}  Kriterium")
    print("-" * 62)
    for r in results:
        ok = "✓" if r["noise_rate"] < NOISE_RATE_LIMIT else "✗ η≥0.20"
        print(
            f"{r['m']:>4} {r['silhouette']:>12.4f}"
            f" {r['davies_bouldin']:>16.4f}"
            f" {r['n_clusters']:>8} {r['noise_rate']:>8.2%}  {ok}"
        )

    # Entscheidungslogik
    candidates = [r for r in results if r["noise_rate"] < NOISE_RATE_LIMIT]
    if not candidates:
        print("\nKein m erfüllt η < 0.20. Grenzwert überdenken.")
        return

    import math
    best = max(
        candidates,
        key=lambda x: (x["silhouette"] if not math.isnan(x["silhouette"]) else -1)
    )
    print(f"\nOptimum: m*={best['m']}"
          f"  S={best['silhouette']:.4f}  DB={best['davies_bouldin']:.4f}"
          f"  η={best['noise_rate']:.2%}")


def main() -> None:
    parser = argparse.ArgumentParser(description="E4: HDBSCAN-Sweep")
    parser.add_argument("--m-values", nargs="+", type=int,
                        default=[3, 5, 8, 10, 15])
    parser.add_argument("--kqr-ids", nargs="+", type=str,
                        default=list(E4_DEFAULT_KQR_IDS),
                        help="KQR-IDs im Clustering-Raum (Default: ESCO + e-CF)")
    parser.add_argument("--output", type=Path,
                        default=OUTPUT_DIR / "E4_hdbscan.json")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    if args.report:
        data = json.loads(args.output.read_text(encoding="utf-8"))
        report(data)
        return

    data = run_experiment(args.m_values, tuple(args.kqr_ids))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nErgebnis gespeichert: {args.output}")
    report(data)


if __name__ == "__main__":
    main()
