"""
R_analyze - Auswertung des LLM-Neulaufs (eval/results/rerun_2026-10).

Kennzahlen je Lauf: Macro-F1 ueber vier Goldklassen, Klassen-F1,
Accuracy, K-Mitgliedschaft (Mehrheit 2/3 und Einstimmigkeit 3/3),
Selbstkonsistenz (Anteil 3/3), Parsing-Fehler, Konfusionsmatrix.
Fuer die Produktionskonfiguration zusaetzlich: Stabilitaet zwischen den
Durchgaengen, Bootstrap-Konfidenzintervalle, Kombination Kosinus+LLM fuer
EQUIVALENT (Schwelle per Leave-One-Out) und McNemar-Test LLM vs. Kosinus
fuer die K-Entscheidung.

Verwendung:
    python eval/R_analyze.py
"""

from __future__ import annotations

import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.B_baselines import (  # noqa: E402
    CLASSES, K_RELATIONS, b1_cosine_k, binary_k, cosine_scores, macro_f1_gold_classes,
)

RUN_DIR = ROOT / "eval" / "results" / "rerun_2026-10"
OUT = RUN_DIR / "R_analysis.json"
N_BOOT = 2000
SEED = 20261004


def load(name: str) -> dict:
    return json.loads((RUN_DIR / name).read_text(encoding="utf-8"))


def direction(rows: list[dict]) -> dict:
    """Richtungsgenauigkeit unter Gold-Subsumtionspaaren, die als Subsumtion
    erkannt wurden. Exakter zweiseitiger Binomialtest gegen 0,5."""
    sub = [r for r in rows if r["gold"] in ("A_SUBSUMES_B", "B_SUBSUMES_A")]
    rec = [r for r in sub if r["final"] in ("A_SUBSUMES_B", "B_SUBSUMES_A")]
    ok = sum(r["final"] == r["gold"] for r in rec)
    n = len(rec)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(min(ok, n - ok) + 1)) / 2 ** n) if n else 1.0
    return {"gold_subsumption": len(sub), "recognised_as_subsumption": n,
            "direction_correct": ok, "direction_accuracy": ok / n if n else None,
            "p_binomial_vs_0.5": p}


def _p2(k: int, n: int) -> float:
    """Exakter zweiseitiger Binomialtest gegen 0,5."""
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(k, n - k) + 1)) / 2 ** n)


def direction_mtc(n_perm: int = 20000) -> dict:
    """Mehrfachtest-Korrektur der Richtungsgenauigkeit ueber fuenf
    Konfigurationen (n_FS = 3 nur einmal, die drei Durchgaenge sind
    identisch). Bonferroni, Holm und Westfall-Young: Die Gold-Richtung wird
    je Paar gemeinsam fuer alle Konfigurationen zufaellig umgedreht,
    Statistik ist der kleinste p-Wert."""
    from functools import lru_cache

    p2 = lru_cache(None)(_p2)
    cfg = {"n_FS=0": "ablation_nfs0_t0.0_pass1.json",
           "n_FS=1": "ablation_nfs1_t0.0_pass1.json",
           "n_FS=3": "prod_nfs3_t0.0_pass1.json",
           "n_FS=5": "ablation_nfs5_t0.0_pass1.json",
           "T=0,3": "temp03_nfs3_t0.3_pass1.json"}
    data = {k: {(r["subject_id"], r["object_id"]): r for r in load(f)["pairs"]}
            for k, f in cfg.items()}
    ref = data["n_FS=3"]
    keys = [p for p, r in ref.items() if r["gold"] in ("A_SUBSUMES_B", "B_SUBSUMES_A")]
    sgn = {"A_SUBSUMES_B": 1, "B_SUBSUMES_A": -1}
    gold = np.array([sgn[ref[p]["gold"]] for p in keys])
    pred = {k: np.array([sgn.get(data[k][p]["final"], 0) for p in keys]) for k in cfg}

    names = list(cfg)
    m = len(names)
    obs = {}
    for k in names:
        n = int((pred[k] != 0).sum())
        ok = int(((pred[k] == gold) & (pred[k] != 0)).sum())
        obs[k] = {"correct": ok, "n": n, "accuracy": ok / n, "p_raw": p2(ok, n)}

    order = sorted(names, key=lambda k: obs[k]["p_raw"])
    run = 0.0
    for rank, k in enumerate(order):
        run = max(run, min(1.0, (m - rank) * obs[k]["p_raw"]))
        obs[k]["p_holm"] = run
        obs[k]["p_bonferroni"] = min(1.0, m * obs[k]["p_raw"])

    rng = np.random.default_rng(SEED)
    obs_min = min(v["p_raw"] for v in obs.values())
    hit = 0
    for _ in range(n_perm):
        g = gold * rng.choice([-1, 1], size=len(gold))
        mn = min(p2(int(((pred[k] == g) & (pred[k] != 0)).sum()), int((pred[k] != 0).sum()))
                 for k in names)
        hit += mn <= obs_min + 1e-12
    return {"m": m, "configs": obs,
            "westfall_young": {"statistic": "kleinster p-Wert", "n_perm": n_perm,
                               "seed": SEED, "p_fwer": hit / n_perm}}


def metrics(rows: list[dict]) -> dict:
    pred = [r["final"] for r in rows]
    gold = [r["gold"] for r in rows]
    m = macro_f1_gold_classes(pred, gold)
    unanimous = [r["votes_for_final"] == r["runs_total"] for r in rows]
    return {
        **m,
        "k_majority": binary_k([p in K_RELATIONS for p in pred], gold),
        "k_unanimous": binary_k([p in K_RELATIONS and u for p, u in zip(pred, unanimous)], gold),
        "self_consistency_3of3": sum(unanimous) / len(rows),
        "unresolved": sum(p == "UNRESOLVED" for p in pred),
        "parse_errors": sum(x["relation"] == "PARSE_ERROR" for r in rows for x in r["runs"]),
        "pred_distribution": dict(Counter(pred)),
        "direction": direction(rows),
        "confusion": {g: dict(Counter(p for p, gg in zip(pred, gold) if gg == g)) for g in CLASSES},
    }


def hybrid(pred: list[str], scores: list[float], t: float) -> list[str]:
    return ["EQUIVALENT" if s >= t else p for p, s in zip(pred, scores)]


def best_t(pred, scores, gold) -> float:
    best, bt = -1.0, 1.01
    for t in sorted(set(scores)) + [1.01]:
        f = macro_f1_gold_classes(hybrid(pred, scores, t), gold)["macro_f1"]
        if f > best:
            best, bt = f, t
    return bt


def loo_hybrid(pred, scores, gold) -> tuple[list[str], list[float]]:
    out, ts = [], []
    for i in range(len(pred)):
        t = best_t(pred[:i] + pred[i + 1:], scores[:i] + scores[i + 1:], gold[:i] + gold[i + 1:])
        ts.append(t)
        out.append("EQUIVALENT" if scores[i] >= t else pred[i])
    return out, ts


def loo_cosine_k(scores, gold) -> list[bool]:
    out = []
    for i in range(len(scores)):
        t = b1_cosine_k(scores[:i] + scores[i + 1:], gold[:i] + gold[i + 1:])["B1_cosine_k_best"]["threshold"]
        out.append(scores[i] >= t)
    return out


def bootstrap(gold, preds: dict[str, list[str]], kpreds: dict[str, list[bool]]) -> dict:
    rnd = random.Random(SEED)
    n = len(gold)
    acc = {f"macro_f1:{k}": [] for k in preds} | {f"f1_K:{k}": [] for k in kpreds}
    acc["diff_macro_f1:hybrid_minus_llm"] = []
    for _ in range(N_BOOT):
        idx = [rnd.randrange(n) for _ in range(n)]
        g = [gold[i] for i in idx]
        mf = {k: macro_f1_gold_classes([v[i] for i in idx], g)["macro_f1"] for k, v in preds.items()}
        for k, v in mf.items():
            acc[f"macro_f1:{k}"].append(v)
        for k, v in kpreds.items():
            acc[f"f1_K:{k}"].append(binary_k([v[i] for i in idx], g)["f1"])
        if "hybrid_loocv" in mf and "llm" in mf:
            acc["diff_macro_f1:hybrid_minus_llm"].append(mf["hybrid_loocv"] - mf["llm"])
    return {k: {"ci95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))],
                "mean": float(np.mean(v))} for k, v in acc.items() if v}


def mcnemar_exact(a: list[bool], b: list[bool], gold: list[str]) -> dict:
    """Exakter McNemar-Test auf Korrektheit der K-Entscheidung."""
    ca = [x == (g in K_RELATIONS) for x, g in zip(a, gold)]
    cb = [x == (g in K_RELATIONS) for x, g in zip(b, gold)]
    b01 = sum(x and not y for x, y in zip(ca, cb))
    b10 = sum(y and not x for x, y in zip(ca, cb))
    n = b01 + b10
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b01, b10) + 1)) / 2 ** n) if n else 1.0
    return {"only_first_correct": b01, "only_second_correct": b10, "p_exact_two_sided": p}


def main() -> None:
    files = sorted(p.name for p in RUN_DIR.glob("*_pass*.json"))
    res: dict = {"_meta": {"files": files, "n_boot": N_BOOT, "seed": SEED}}
    res["per_run"] = {}
    for f in files:
        d = load(f)
        res["per_run"][f] = {"meta": {k: d["_meta"][k] for k in
                                      ("n_fs", "temperature", "model_resolved", "pairs_used")},
                             **metrics(d["pairs"])}

    # Primaerkonfiguration = Produktionspfad: e-CF <-> ESCO-Skelett hat 0 Struktur-Shortcuts,
    # der Prompt enthaelt keine Few-Shot-Beispiele (n_FS = 0). n_FS = 3 mit G_struct-Ankern
    # ("prod_") ist eine Variante.
    prod = [load(f)["pairs"] for f in files if f.startswith("prod0_")]
    variant = [load(f)["pairs"] for f in files if f.startswith("prod_")]
    if not prod:
        raise SystemExit("Keine Produktionslaeufe gefunden.")
    gold = [r["gold"] for r in prod[0]]
    mf = [metrics(p)["macro_f1"] for p in prod]
    stable = sum(len({p[i]["final"] for p in prod}) == 1 for i in range(len(gold))) / len(gold)
    res["primary_across_passes"] = {"macro_f1": mf, "mean": float(np.mean(mf)),
                                 "min": min(mf), "max": max(mf),
                                 "share_pairs_identical_final_all_passes": stable}

    if variant:
        vmf = [metrics(p)["macro_f1"] for p in variant]
        res["variant_nfs3_across_passes"] = {"macro_f1": vmf, "mean": float(np.mean(vmf))}

    llm = [r["final"] for r in prod[0]]
    scores = cosine_scores(prod[0])
    hyb_loo, ts = loo_hybrid(llm, scores, gold)
    t_in = best_t(llm, scores, gold)
    cos_k = loo_cosine_k(scores, gold)
    llm_k = [p in K_RELATIONS for p in llm]
    swaps = sum((g, p) in {("A_SUBSUMES_B", "B_SUBSUMES_A"), ("B_SUBSUMES_A", "A_SUBSUMES_B")}
                for g, p in zip(gold, llm))
    res["primary_pass1"] = {
        "llm": metrics(prod[0]),
        "hybrid_insample": {"t": t_in, **macro_f1_gold_classes(hybrid(llm, scores, t_in), gold)},
        "hybrid_loocv": {"t_median": float(np.median(ts)), **macro_f1_gold_classes(hyb_loo, gold)},
        "cosine_k_loocv": binary_k(cos_k, gold),
        "mcnemar_llm_vs_cosine_k": mcnemar_exact(llm_k, cos_k, gold),
        "direction_swaps_between_subsumption_classes": swaps,
        "bootstrap": bootstrap(gold, {"llm": llm, "hybrid_loocv": hyb_loo},
                               {"llm": llm_k, "cosine_loocv": cos_k}),
    }
    res["direction_multiple_testing"] = direction_mtc()
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Lauf                              MacroF1  Acc    F1_K(2/3) F1_K(3/3) 3/3   UNRES  Parse")
    for f, m in res["per_run"].items():
        print(f"{f:<34}{m['macro_f1']:.3f}   {m['accuracy']:.3f}  {m['k_majority']['f1']:.3f}     "
              f"{m['k_unanimous']['f1']:.3f}     {m['self_consistency_3of3']:.2f}  "
              f"{m['unresolved']:<6} {m['parse_errors']}")
    print(json.dumps({k: v for k, v in res.items() if k not in ("per_run", "_meta")},
                     indent=1, ensure_ascii=False)[:6000])


if __name__ == "__main__":
    main()
