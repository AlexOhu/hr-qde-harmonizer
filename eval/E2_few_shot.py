"""
E2 – Few-Shot-Ablation: optimale Anzahl Few-Shot-Beispiele (VH₁.₆)

Variiert n_FS ∈ {0, 1, 3, 5} und misst Macro-F1 auf G_manual.

Verwendung:
    python eval/E2_few_shot.py [--n-fs-values 0 1 3 5]
                                [--gold eval/gold/G_manual.json]
                                [--output eval/results/E2_few_shot.json]
    python eval/E2_few_shot.py --report
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GOLD_JSON  = ROOT / "eval" / "gold" / "G_manual.json"
OUTPUT_DIR = ROOT / "eval" / "results"

ALLOWED_RELATIONS = ["EQUIVALENT", "A_SUBSUMES_B", "B_SUBSUMES_A", "RELATED"]
# A_SUBSUMES_B und B_SUBSUMES_A werden für F1 zusammengefasst
_SUBS = {"A_SUBSUMES_B", "B_SUBSUMES_A"}


def f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0


def compute_macro_f1(
    predictions: list[str],
    gold_labels: list[str],
) -> dict[str, float]:
    """Gibt klassenweise Precision/Recall/F1 sowie Macro-F1 zurück.

    Macro-F1 mittelt über die vier Goldklassen (ALLOWED_RELATIONS).
    Vorhersagen außerhalb dieser Klassen (UNRESOLVED) zählen als Fehler
    (FN der Goldklasse), bilden aber keine eigene Klasse im Mittelwert.
    Korrektur 2026-10-04: Zuvor ging UNRESOLVED als fünfte Klasse mit
    F1 = 0 in den Nenner ein, sobald es vorhergesagt wurde. Dadurch waren
    Läufe mit und ohne UNRESOLVED-Vorhersagen nicht vergleichbar
    (vgl. eval/B_baselines.py, Abschnitt E2_fix).
    """
    classes = list(ALLOWED_RELATIONS)
    per_class: dict[str, dict] = {}
    for cls in classes:
        tp = sum(p == g == cls for p, g in zip(predictions, gold_labels))
        fp = sum(p == cls and g != cls for p, g in zip(predictions, gold_labels))
        fn = sum(p != cls and g == cls for p, g in zip(predictions, gold_labels))
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec  = tp / (tp + fn) if (tp + fn) else 0.0
        per_class[cls] = {"precision": prec, "recall": rec, "f1": f1(prec, rec)}

    macro_f1 = sum(v["f1"] for v in per_class.values()) / len(per_class) if per_class else 0.0
    accuracy = sum(p == g for p, g in zip(predictions, gold_labels)) / len(gold_labels)
    return {"per_class": per_class, "macro_f1": macro_f1, "accuracy": accuracy}


def _load_concept_lookup() -> dict[str, dict]:
    from app.services import kqr_service
    concept_lookup: dict[str, dict] = {}
    for kqr in kqr_service.list_kqr():
        try:
            for c in kqr_service.get_concepts(kqr.id):
                concept_lookup[c.uri] = {
                    "pref_label": c.pref_label,
                    "definition":  c.definition or "",
                    "kqr_id":      c.kqr_id,
                }
        except ValueError:
            pass
    return concept_lookup


_STRUCT_CROSSWALK_PATH = ROOT / "eval" / "G_struct.json"


def _few_shot_text_for_n_fs(n_fs: int) -> str:
    """Baut den Few-Shot-Block aus den ersten n_fs Crosswalk-Ankern
    (gleiches Format wie app.services.classification_service._build_few_shot_text).

    Anker-Quelle (Entscheidung 2026-08-31, vgl. eval/PROTOKOLL.md): die
    normative Crosswalk-Goldmenge eval/G_struct.json (DQR<->EQF-Dimensionspaare
    aus dem German EQF Referencing Report). Der urspruengliche Pool (persistierte
    Struktur-Shortcut-Mappings mit match_type=="struct") existiert nach ADR-17
    nicht mehr; find_structural_shortcuts liefert auf den aktuellen
    Formalisierungen 0 Treffer. G_struct deckt den Prompt-Wortlaut
    "aus der Crosswalk-Goldmenge (Schritt 2)" ab und ist deterministisch.
    """
    if n_fs <= 0:
        return "(keine Crosswalk-Beispiele verfügbar)"
    data = json.loads(_STRUCT_CROSSWALK_PATH.read_text(encoding="utf-8"))
    anchors = data["pairs"][:n_fs]
    if not anchors:
        return "(keine Crosswalk-Beispiele verfügbar)"
    return "\n".join(
        f'- "{a["subject_label"]}" {a.get("predicate", "skos:exactMatch")} "{a["object_label"]}"'
        for a in anchors
    )


def classify_pair_with_n_fs(
    subject_id: str, object_id: str, n_fs: int,
    concept_lookup: dict[str, dict], providers, runs_per_pair: int,
    few_shot_text: str,
) -> str:
    """Ruft den Dreifach-Mehrheitsentscheid (classify_pair) mit n_fs Few-Shot-Beispielen auf."""
    from app.pipeline.step3_classification.classify import classify_pair
    from app.models.schemas import CandidatePair

    pair = CandidatePair(concept_a=subject_id, concept_b=object_id,
                         similarity_score=1.0)
    result = classify_pair(
        pair,
        concept_lookup[subject_id],
        concept_lookup[object_id],
        few_shot_text,
        providers,
        runs_per_pair,
    )
    # Kein Mehrheitsentscheid -> "UNRESOLVED" (früher RelationType.UNRESOLVED).
    return result.final_relation.value if result.final_relation else "UNRESOLVED"

def run_experiment(
    gold_path: Path, n_fs_values: list[int]
) -> list[dict]:
    from app.config import settings
    from app.pipeline.step3_classification.llm_provider import get_providers_from_config

    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    print(f"G_manual: {len(gold)} Paare")

    concept_lookup = _load_concept_lookup()
    providers = get_providers_from_config(settings)

    results = []
    for n_fs in n_fs_values:
        print(f"\nn_FS={n_fs} ...")
        few_shot_text = _few_shot_text_for_n_fs(n_fs)
        predictions, gold_labels = [], []
        for item in gold:
            pred = classify_pair_with_n_fs(
                item["subject_id"], item["object_id"], n_fs,
                concept_lookup, providers, settings.classification_runs_per_pair,
                few_shot_text,
            )
            predictions.append(pred)
            gold_labels.append(item["gold_relation"])
            print(".", end="", flush=True)
        print()

        metrics = compute_macro_f1(predictions, gold_labels)
        results.append({"n_fs": n_fs, **metrics})
        print(f"  Macro-F1={metrics['macro_f1']:.4f}  "
              f"Accuracy={metrics['accuracy']:.4f}")
    return results


def report(results: list[dict]) -> None:
    print("\n--- E2: Few-Shot-Ablation ---")
    hdr = f"{'n_FS':>5} {'F1[EQ]':>8} {'F1[SU]':>8} {'F1[RE]':>8} {'Macro-F1':>10} {'Acc':>7}"
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        pc = r["per_class"]
        f1_eq   = pc.get("EQUIVALENT",  {}).get("f1", 0.0)
        f1_subs = (pc.get("A_SUBSUMES_B", {}).get("f1", 0.0) +
                   pc.get("B_SUBSUMES_A", {}).get("f1", 0.0)) / 2
        f1_rel  = pc.get("RELATED",      {}).get("f1", 0.0)
        print(f"{r['n_fs']:>5} {f1_eq:>8.4f} {f1_subs:>8.4f} {f1_rel:>8.4f}"
              f" {r['macro_f1']:>10.4f} {r['accuracy']:>7.4f}")
    best = max(results, key=lambda x: x["macro_f1"])
    print(f"\nOptimum: n_FS*={best['n_fs']}  Macro-F1={best['macro_f1']:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="E2: Few-Shot-Ablation")
    parser.add_argument("--n-fs-values", nargs="+", type=int, default=[0, 1, 3, 5])
    parser.add_argument("--gold", type=Path, default=GOLD_JSON)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / "E2_few_shot.json")
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

    results = run_experiment(args.gold, args.n_fs_values)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"results": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nErgebnis gespeichert: {args.output}")
    report(results)


if __name__ == "__main__":
    main()
