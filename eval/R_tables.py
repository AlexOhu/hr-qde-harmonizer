"""
R_tables - Zahlen fuer die Tabellen und Saetze in Kapitel 5 aus den gespeicherten Laeufen.

E2: je n_FS der Durchgang mit dem mittleren Macro-F1 von drei Durchgaengen
    (n_FS = 0: prod0, 1 und 5: abl15, 3: prod).
E3: Primaerkonfiguration n_FS = 0 (prod0), derselbe mittlere Durchgang.

Verwendung:  python eval/R_tables.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.B_baselines import CLASSES, K_RELATIONS, binary_k, macro_f1_gold_classes  # noqa: E402

RUN = ROOT / "eval" / "results" / "rerun_2026-10"
CFG = {0: "prod0_nfs0_t0.0", 1: "abl15_nfs1_t0.0", 3: "prod_nfs3_t0.0", 5: "abl15_nfs5_t0.0"}


def de(x: float, n: int = 3) -> str:
    return f"{x:.{n}f}".replace(".", ",")


def load_runs(stem: str) -> list[list[dict]]:
    return [json.loads(f.read_text(encoding="utf-8"))["pairs"] for f in sorted(RUN.glob(f"{stem}_pass*.json"))]


def per_run(rows: list[dict]) -> dict:
    pred = [r["final"] for r in rows]
    gold = [r["gold"] for r in rows]
    m = macro_f1_gold_classes(pred, gold)
    pc = m["per_class_f1"]
    unanimous = [r["votes_for_final"] == r["runs_total"] for r in rows]
    kmaj = binary_k([p in K_RELATIONS for p in pred], gold)
    kun = binary_k([p in K_RELATIONS and u for p, u in zip(pred, unanimous)], gold)
    return {"pc": pc, "macro": m["macro_f1"], "acc": m["accuracy"], "kmaj": kmaj, "kun": kun,
            "selfcons": sum(unanimous) / len(rows), "pred": pred, "gold": gold}


def median_run(rs: list[dict]) -> tuple[int, dict]:
    order = sorted(range(len(rs)), key=lambda i: rs[i]["macro"])
    i = order[len(order) // 2]
    return i, rs[i]


def boot_ci_f1(pred: list[str], gold: list[str], n: int = 2000, seed: int = 20261004) -> tuple[float, float]:
    rnd = random.Random(seed)
    vals = []
    for _ in range(n):
        idx = [rnd.randrange(len(gold)) for _ in range(len(gold))]
        vals.append(binary_k([pred[i] in K_RELATIONS for i in idx], [gold[i] for i in idx])["f1"])
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


def main() -> None:
    out: dict = {}
    print("E2-Tabelle (Durchgang mit mittlerem Macro-F1 von drei):")
    print("n_FS | F1_EQUIV | F1_A>B | F1_B>A | F1_REL | Macro-F1 | Acc | (Durchgaenge Macro-F1)")
    for n, stem in CFG.items():
        runs = [per_run(r) for r in load_runs(stem)]
        i, r = median_run(runs)
        pc = r["pc"]
        print(f"{n} | {de(pc['EQUIVALENT'])} | {de(pc['A_SUBSUMES_B'])} | {de(pc['B_SUBSUMES_A'])} | "
              f"{de(pc['RELATED'])} | {de(r['macro'])} | {de(r['acc'])} | "
              f"{[de(x['macro']) for x in runs]} (n={len(runs)}, Median = Durchgang {i + 1})")
        out[n] = {"passes": len(runs), "median_pass": i + 1, "macro_f1_all": [x["macro"] for x in runs],
                  "row": {"eq": pc["EQUIVALENT"], "ab": pc["A_SUBSUMES_B"], "ba": pc["B_SUBSUMES_A"],
                          "rel": pc["RELATED"], "macro": r["macro"], "acc": r["acc"]}}
        if n == 0:
            prim = runs
            pi, pr = i, r
    gold = pr["gold"]
    print(f"\nGoldmenge: {len(gold)} Paare, " + ", ".join(f"{c} {sum(g == c for g in gold)}" for c in CLASSES))

    print("\nE3 (n_FS = 0, T = 0, mittlerer Durchgang %d):" % (pi + 1))
    lo, hi = boot_ci_f1(pr["pred"], gold)
    for name, k in (("Mehrheit (>= 2/3)", pr["kmaj"]), ("Einstimmigkeit (3/3)", pr["kun"])):
        print(f"  {name}: P {de(k['precision'])}  R {de(k['recall'])}  F1 {de(k['f1'])}  uebernommen {k['accepted']}")
    print(f"  F1 Mehrheit KI95 {de(lo)} bis {de(hi)}")
    print("  Selbstkonsistenz je Durchgang:", [de(x['selfcons'], 2) for x in prim])
    print("  F1 Mehrheit je Durchgang:", [de(x['kmaj']['f1']) for x in prim],
          " Einstimmigkeit:", [de(x['kun']['f1']) for x in prim])
    print("  Verteilung der Vorhersagen (mittlerer Durchgang):",
          {c: pr["pred"].count(c) for c in set(pr["pred"])})
    sub = [(p, g) for p, g in zip(pr["pred"], gold) if g in ("A_SUBSUMES_B", "B_SUBSUMES_A")]
    rec = [(p, g) for p, g in sub if p in ("A_SUBSUMES_B", "B_SUBSUMES_A")]
    print(f"  Richtung: {sum(p == g for p, g in rec)} von {len(rec)} ({de(sum(p == g for p, g in rec) / len(rec) * 100, 1)} %), "
          f"als Subsumtion erkannt {len(rec)} von {len(sub)}")
    stable = sum(len({r[i]['final'] for r in load_runs('prod0_nfs0_t0.0')}) == 1 for i in range(len(gold))) / len(gold)
    print(f"  Identische Endrelation ueber 3 Durchgaenge: {de(stable * 100, 1)} %")
    out["E3"] = {"maj": pr["kmaj"], "un": pr["kun"], "ci": [lo, hi],
                 "selfcons": [x["selfcons"] for x in prim], "pass": pi + 1,
                 "direction_ok": sum(p == g for p, g in rec), "direction_n": len(rec),
                 "recognised": len(rec), "gold_sub": len(sub), "stable": stable,
                 "n_pairs": len(gold), "gold_counts": {c: sum(g == c for g in gold) for c in CLASSES}}
    (RUN / "R_tables.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
