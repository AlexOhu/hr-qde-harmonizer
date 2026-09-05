"""
E3 – Confidence-Schwellen: Precision/Recall-Trade-off (VH₁.₇)

Berechnet Precision, Recall und F1 für θ ∈ {0.33, 0.67, 1.00}
auf G_manual und bestimmt θ* (F1-Optimum) sowie θ_op
(Precision-biased Empfehlung).

Hinweis: Dreifach-Mehrheitsentscheid erzeugt nur drei diskrete
Confidence-Werte. Die PR-Kurve hat daher exakt drei Stützpunkte.

Verwendung:
    python eval/E3_confidence.py [--gold eval/gold/G_manual.json]
                                  [--n-fs OPTIMAL_N_FS]
                                  [--output eval/results/E3_confidence.json]
    python eval/E3_confidence.py --report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GOLD_JSON  = ROOT / "eval" / "gold" / "G_manual.json"
OUTPUT_DIR = ROOT / "eval" / "results"
E2_RESULT  = OUTPUT_DIR / "E2_few_shot.json"

THRESHOLDS = [0.33, 0.67, 1.00]
# Relationen, die zur Menge K gehören (wird gefiltert)
_K_RELATIONS = {"EQUIVALENT", "A_SUBSUMES_B", "B_SUBSUMES_A"}


def precision_recall_f1(
    predictions: list[tuple[str, float]],  # (relation, confidence)
    gold_labels: list[str],
    threshold: float,
) -> tuple[float, float, float, int]:
    """Precision, Recall, F1 und Anzahl akzeptierter Mappings bei θ."""
    tp = fp = fn = 0
    accepted = 0
    for (pred_rel, conf), gold in zip(predictions, gold_labels):
        is_accepted   = conf >= threshold and pred_rel in _K_RELATIONS
        is_gold_in_k  = gold in _K_RELATIONS
        accepted      += is_accepted
        tp += is_accepted and is_gold_in_k
        fp += is_accepted and not is_gold_in_k
        fn += not is_accepted and is_gold_in_k

    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec  = tp / (tp + fn) if (tp + fn) else 0.0
    f1_  = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1_, accepted


def load_best_n_fs() -> int:
    """Liest n_FS* aus E2-Ergebnis (Fallback: 3)."""
    if E2_RESULT.exists():
        data = json.loads(E2_RESULT.read_text(encoding="utf-8"))
        best = max(data["results"], key=lambda x: x["macro_f1"])
        return best["n_fs"]
    return 3


def run_experiment(gold_path: Path, n_fs: int) -> list[dict]:
    from eval.E2_few_shot import _load_concept_lookup, _few_shot_text_for_n_fs
    from app.pipeline.step3_classification.classify import classify_pair
    from app.pipeline.step3_classification.llm_provider import get_providers_from_config
    from app.models.schemas import CandidatePair
    from app.config import settings

    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    print(f"G_manual: {len(gold)} Paare  |  n_FS={n_fs}")

    concept_lookup = _load_concept_lookup()
    providers = get_providers_from_config(settings)
    few_shot_text = _few_shot_text_for_n_fs(n_fs)

    predictions: list[tuple[str, float]] = []
    gold_labels: list[str] = []
    for item in gold:
        pair = CandidatePair(
            concept_a=item["subject_id"],
            concept_b=item["object_id"],
            similarity_score=1.0,
        )
        result = classify_pair(
            pair,
            concept_lookup[item["subject_id"]],
            concept_lookup[item["object_id"]],
            few_shot_text,
            providers,
            settings.classification_runs_per_pair,
        )
        # Kein Mehrheitsentscheid: als eigenes, nie zur Goldmenge passendes
        # Label führen (früher RelationType.UNRESOLVED.value).
        predicted = result.final_relation.value if result.final_relation else "UNRESOLVED"
        predictions.append((predicted, result.mapping_confidence))
        gold_labels.append(item["gold_relation"])
        print(".", end="", flush=True)
    print()

    results = []
    for theta in THRESHOLDS:
        prec, rec, f1_, accepted = precision_recall_f1(
            predictions, gold_labels, theta
        )
        results.append({
            "theta": theta,
            "precision": round(prec, 4),
            "recall":    round(rec,  4),
            "f1":        round(f1_,  4),
            "accepted":  accepted,
        })
        print(f"  theta={theta:.2f}: P={prec:.4f}  R={rec:.4f}  F1={f1_:.4f}"
              f"  Mappings={accepted}")
    return results

def report(results: list[dict]) -> None:
    print("\n--- E3: Confidence-Schwellen ---")
    print(f"{'theta':>6} {'Precision':>10} {'Recall':>8} {'F1':>8} {'Mappings':>10}")
    print("-" * 46)
    for r in results:
        print(
            f"{r['theta']:>6.2f} {r['precision']:>10.4f}"
            f" {r['recall']:>8.4f} {r['f1']:>8.4f} {r['accepted']:>10}"
        )
    best_f1   = max(results, key=lambda x: x["f1"])
    # Precision-biased: höchster Precision-Wert, der noch F1 >= 0.9 * best hat
    threshold = 0.9 * best_f1["f1"]
    precision_biased = max(
        (r for r in results if r["f1"] >= threshold),
        key=lambda x: x["precision"],
        default=best_f1,
    )
    print(f"\nF1-Optimum: theta*={best_f1['theta']:.2f}  F1={best_f1['f1']:.4f}")
    print(f"Precision-biased: theta_op={precision_biased['theta']:.2f}"
          f"  P={precision_biased['precision']:.4f}"
          f"  F1={precision_biased['f1']:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="E3: Confidence-Schwellen")
    parser.add_argument("--gold", type=Path, default=GOLD_JSON)
    parser.add_argument("--n-fs", type=int, default=None,
                        help="Few-Shot-Anzahl (Standard: n_FS* aus E2-Ergebnis)")
    parser.add_argument("--output", type=Path,
                        default=OUTPUT_DIR / "E3_confidence.json")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    if args.report:
        data = json.loads(args.output.read_text(encoding="utf-8"))
        report(data["results"])
        return

    if not args.gold.exists():
        raise SystemExit(
            f"G_manual nicht gefunden: {args.gold}\n"
            "Zuerst: python eval/build_gold_manual.py --finalize"
        )

    n_fs = args.n_fs if args.n_fs is not None else load_best_n_fs()
    print(f"Verwende n_FS={n_fs} (aus E2-Ergebnis oder Fallback)")

    results = run_experiment(args.gold, n_fs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"n_fs_used": n_fs, "results": results},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nErgebnis gespeichert: {args.output}")
    report(results)


if __name__ == "__main__":
    main()
