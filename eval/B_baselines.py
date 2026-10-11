"""
B – Baselines fuer E2/E3 ohne LLM-Klassifikation.

B0  Triviale Baselines (alles in K, Mehrheitsklasse, stratifizierter Zufall)
B1  Kosinus-Schwellwert fuer die K-Mitgliedschaft (Vergleich zu E3)
B2  Drei-Band-Heuristik ueber Kosinus fuer die 4-Klassen-Aufgabe (Vergleich zu E2)
B3  Exakter Label-Abgleich fuer EQUIVALENT
E2fix  Neuberechnung des E2-Macro-F1 ueber die vier Goldklassen

Kosinus wird wie in Prototyp 2 berechnet (pref_label + definition,
L2-normalisiert, embedding_model aus app.config).

Achtung: Die Schwellwerte von B1/B2 werden auf G_manual selbst optimiert.
Die Werte sind daher eine optimistische Obergrenze der Baseline, analog
zur Kalibrierung von theta* in E3 auf derselben Goldmenge.

Verwendung:
    python eval/B_baselines.py [--output eval/results/B_baselines.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GOLD_JSON  = ROOT / "eval" / "gold" / "G_manual.json"
E2_RESULT  = ROOT / "eval" / "results" / "E2_few_shot.json"
OUTPUT_DIR = ROOT / "eval" / "results"

CLASSES = ["EQUIVALENT", "A_SUBSUMES_B", "B_SUBSUMES_A", "RELATED"]
K_RELATIONS = {"EQUIVALENT", "A_SUBSUMES_B", "B_SUBSUMES_A"}
MISSING_URIS: list[str] = []


# ---------------------------------------------------------------- Metriken

def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def binary_k(pred_in_k: list[bool], gold: list[str]) -> dict:
    tp = sum(p and g in K_RELATIONS for p, g in zip(pred_in_k, gold))
    fp = sum(p and g not in K_RELATIONS for p, g in zip(pred_in_k, gold))
    fn = sum((not p) and g in K_RELATIONS for p, g in zip(pred_in_k, gold))
    p, r, f = prf(tp, fp, fn)
    return {"precision": p, "recall": r, "f1": f, "accepted": sum(pred_in_k)}


def macro_f1_gold_classes(pred: list[str], gold: list[str]) -> dict:
    """Macro-F1 ueber die vier Goldklassen. Vorhersagen ausserhalb der
    Goldklassen (z. B. UNRESOLVED) zaehlen als Fehler, bilden aber keine
    eigene Klasse im Mittelwert."""
    per_class = {}
    for c in CLASSES:
        tp = sum(p == g == c for p, g in zip(pred, gold))
        fp = sum(p == c and g != c for p, g in zip(pred, gold))
        fn = sum(p != c and g == c for p, g in zip(pred, gold))
        per_class[c] = prf(tp, fp, fn)[2]
    acc = sum(p == g for p, g in zip(pred, gold)) / len(gold)
    return {"per_class_f1": per_class,
            "macro_f1": sum(per_class.values()) / len(CLASSES),
            "accuracy": acc}


def auc(scores: list[float], positive: list[bool]) -> float:
    """ROC-AUC als Mann-Whitney-U (Ties zaehlen 0,5)."""
    pos = [s for s, y in zip(scores, positive) if y]
    neg = [s for s, y in zip(scores, positive) if not y]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


# ---------------------------------------------------------------- Daten

def norm_label(s: str) -> str:
    return " ".join(s.lower().split())


def cosine_scores(gold: list[dict]) -> list[float]:
    from app.config import settings
    from eval.E2_few_shot import _load_concept_lookup
    from app.pipeline.step2_embedding_prefilter.embed import _get_model

    lookup = _load_concept_lookup()
    missing = sorted({i[k] for i in gold for k in ("subject_id", "object_id")} - lookup.keys())
    if missing:
        # Fallback: Label aus der Goldmenge, ohne Definition (im Ergebnis vermerkt)
        print(f"WARNUNG: {len(missing)} Konzepte nicht in der KQR-Registry, "
              f"Label-Fallback: {missing}")
    MISSING_URIS.extend(missing)

    def text(uri: str, label: str) -> str:
        c = lookup.get(uri)
        if c is None:
            return label
        return f"{c['pref_label']}. {c['definition'] or ''}".strip()

    model = _get_model(settings.embedding_model)
    a = model.encode([text(i["subject_id"], i["subject_label"]) for i in gold],
                     convert_to_numpy=True, normalize_embeddings=True)
    b = model.encode([text(i["object_id"], i["object_label"]) for i in gold],
                     convert_to_numpy=True, normalize_embeddings=True)
    return [float(x) for x in np.sum(a * b, axis=1)]


# ---------------------------------------------------------------- Baselines

def b0_trivial(gold: list[str]) -> dict:
    prior = Counter(gold)
    majority = prior.most_common(1)[0][0]
    return {
        "B0_all_in_K": binary_k([True] * len(gold), gold),
        "B0_majority_class": {"class": majority,
                              **macro_f1_gold_classes([majority] * len(gold), gold)},
        "B0_stratified_random_expected_macro_f1":
            sum(prior[c] / len(gold) for c in CLASSES) / len(CLASSES),
    }


def b1_cosine_k(scores: list[float], gold: list[str]) -> dict:
    best = None
    for t in sorted(set(scores)):
        m = binary_k([s >= t for s in scores], gold)
        if best is None or m["f1"] > best["f1"]:
            best = {"threshold": t, **m}
    return {"B1_cosine_k_best": best,
            "B1_auc_k_vs_related": auc(scores, [g in K_RELATIONS for g in gold])}


def b2_three_band(scores: list[float], gold: list[str]) -> dict:
    """cos >= t_hi -> EQUIVALENT, t_lo <= cos < t_hi -> A_SUBSUMES_B
    (haeufigste Subsumtionsrichtung), cos < t_lo -> RELATED."""
    grid = sorted(set(scores)) + [1.01]
    best = None
    for i, lo in enumerate(grid):
        for hi in grid[i:]:
            pred = ["EQUIVALENT" if s >= hi else
                    "A_SUBSUMES_B" if s >= lo else "RELATED" for s in scores]
            m = macro_f1_gold_classes(pred, gold)
            if best is None or m["macro_f1"] > best["macro_f1"]:
                best = {"t_lo": lo, "t_hi": hi, **m}
    return {"B2_three_band_best": best}


def b3_label_match(items: list[dict], gold: list[str]) -> dict:
    pred_eq = [norm_label(i["subject_label"]) == norm_label(i["object_label"])
               for i in items]
    tp = sum(p and g == "EQUIVALENT" for p, g in zip(pred_eq, gold))
    fp = sum(p and g != "EQUIVALENT" for p, g in zip(pred_eq, gold))
    fn = sum((not p) and g == "EQUIVALENT" for p, g in zip(pred_eq, gold))
    p, r, f = prf(tp, fp, fn)
    return {"B3_label_match_equivalent": {"precision": p, "recall": r, "f1": f,
                                          "matches": sum(pred_eq)}}


def _band(s: float, lo: float, hi: float) -> str:
    return "EQUIVALENT" if s >= hi else "A_SUBSUMES_B" if s >= lo else "RELATED"


def loocv(scores: list[float], gold: list[str]) -> dict:
    """Leave-One-Out: Schwellen auf n-1 Paaren waehlen, das ausgelassene
    Paar vorhersagen. Liefert eine nicht auf G_manual ueberangepasste
    Schaetzung fuer B1 und B2."""
    n = len(scores)
    k_pred, cls_pred = [], []
    for i in range(n):
        s_tr = scores[:i] + scores[i + 1:]
        g_tr = gold[:i] + gold[i + 1:]
        t = b1_cosine_k(s_tr, g_tr)["B1_cosine_k_best"]["threshold"]
        k_pred.append(scores[i] >= t)
        b = b2_three_band(s_tr, g_tr)["B2_three_band_best"]
        cls_pred.append(_band(scores[i], b["t_lo"], b["t_hi"]))
    return {"B1_cosine_k_loocv": binary_k(k_pred, gold),
            "B2_three_band_loocv": macro_f1_gold_classes(cls_pred, gold)}


def e2_fix() -> list[dict]:
    """Rechnet die gespeicherten E2-Klassen-F1 auf Macro ueber vier Goldklassen um."""
    data = json.loads(E2_RESULT.read_text(encoding="utf-8"))
    out = []
    for r in data["results"]:
        pc = r["per_class"]
        f1s = [pc.get(c, {}).get("f1", 0.0) for c in CLASSES]
        out.append({"n_fs": r["n_fs"],
                    "macro_f1_reported": r["macro_f1"],
                    "macro_f1_4_gold_classes": sum(f1s) / len(CLASSES),
                    "unresolved_counted_as_class": "UNRESOLVED" in pc})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Baselines fuer E2/E3")
    ap.add_argument("--gold", type=Path, default=GOLD_JSON)
    ap.add_argument("--output", type=Path, default=OUTPUT_DIR / "B_baselines.json")
    args = ap.parse_args()

    items = json.loads(args.gold.read_text(encoding="utf-8"))
    gold = [i["gold_relation"] for i in items]
    scores = cosine_scores(items)

    from app.config import settings
    result = {
        "_meta": {"gold": str(args.gold.relative_to(ROOT)), "n": len(items),
                  "class_counts": Counter(gold),
                  "embedding_model": settings.embedding_model,
                  "label_fallback_uris": MISSING_URIS,
                  "note": "B1/B2-Schwellen auf G_manual optimiert (optimistische Obergrenze)."},
        **b0_trivial(gold),
        **b1_cosine_k(scores, gold),
        **b2_three_band(scores, gold),
        **b3_label_match(items, gold),
        **loocv(scores, gold),
        "E2_fix": e2_fix(),
        "pairs": [{"subject_label": i["subject_label"], "object_label": i["object_label"],
                   "gold": g, "cosine": round(s, 4)}
                  for i, g, s in zip(items, gold, scores)],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    show = {k: v for k, v in result.items() if k != "pairs"}
    print(json.dumps(show, indent=2, ensure_ascii=False))
    by_class = {c: [s for s, g in zip(scores, gold) if g == c] for c in CLASSES}
    print("\nKosinus je Goldklasse (min / median / max):")
    for c, v in by_class.items():
        print(f"  {c:<14} {min(v):.3f} / {float(np.median(v)):.3f} / {max(v):.3f}  (n={len(v)})")
    print(f"\nErgebnis gespeichert: {args.output}")


if __name__ == "__main__":
    main()
