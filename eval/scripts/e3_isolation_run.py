"""
E3 – Isolierte Neukalibrierung: revidierter vs. Alt-Prompt (Block 4).

Einziger geänderter Faktor zwischen den beiden Läufen ist das
Prompt-Template. Alles andere ist identisch:
  Provider  : mistral / mistral-small-latest (.env)
  n_FS      : 3
  Few-Shot  : eval/G_struct.json (wie E2/E3 seit 2026-08-31)
  Goldmenge : eval/gold/G_manual.json (74 Paare)
  Läufe/Paar: settings.classification_runs_per_pair (3, Mehrheitsentscheid)

  revised  = prompts/classification_prompt_template.txt (mit Richtungshinweis, Block 4)
  pre-rev. = <scratch>/classification_prompt_template.pre-revision.txt
             (rekonstruiert aus MA_Oberhuber_0.61.pdf, Listing 4.5)

Aufruf:
  python e3_isolation_run.py --dry-run
  python e3_isolation_run.py --repeats 3 --out E3_neukalibrierung.json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

os.environ.setdefault("MISTRAL_MIN_REQUEST_INTERVAL_S", "0.35")
os.environ.setdefault("MISTRAL_MAX_ATTEMPTS", "5")
os.environ.setdefault("MISTRAL_RETRY_BACKOFF_SECONDS", "5.0")

ROOT = Path(r"E:\Fernuni\Master\Masterarbeit\hrqde-harmonizer")
SCRATCH = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

GOLD = ROOT / "eval" / "gold" / "G_manual.json"
TPL_REVISED = ROOT / "prompts" / "classification_prompt_template.txt"
TPL_PREREV = SCRATCH / "classification_prompt_template.pre-revision.txt"

import app.pipeline.step3_classification.classify as classify_mod
from app.pipeline.step3_classification.classify import classify_pair
from app.pipeline.step3_classification.llm_provider import get_providers_from_config
from app.models.schemas import CandidatePair
from app.config import settings
from eval.E2_few_shot import _load_concept_lookup, _few_shot_text_for_n_fs
from eval.E3_confidence import precision_recall_f1, THRESHOLDS


def _one_pass(gold, concept_lookup, few_shot_text, providers, tag):
    preds: list[tuple[str, float]] = []
    gold_labels: list[str] = []
    run_rel_counter: Counter = Counter()
    conf_counter: Counter = Counter()
    final_counter: Counter = Counter()
    t0 = time.time()
    for n, item in enumerate(gold, 1):
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
        predicted = result.final_relation.value if result.final_relation else "UNRESOLVED"
        preds.append((predicted, result.mapping_confidence))
        gold_labels.append(item["gold_relation"])
        for r in result.runs:
            run_rel_counter[r.relation.value] += 1
        conf_counter[round(result.mapping_confidence, 2)] += 1
        final_counter[predicted] += 1
        print(".", end="", flush=True)
        if n % 37 == 0:
            print(f" {n}/{len(gold)}", flush=True)
    print(f"  [{tag}] {time.time() - t0:.0f}s", flush=True)

    rows = []
    for theta in THRESHOLDS:
        p, r, f1_, acc = precision_recall_f1(preds, gold_labels, theta)
        rows.append({
            "theta": theta,
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1_, 4),
            "accepted": acc,
        })
    return {
        "rows": rows,
        "final_relation_dist": dict(final_counter),
        "confidence_dist": {str(k): v for k, v in sorted(conf_counter.items())},
        "single_run_relation_dist": dict(run_rel_counter),
    }


def _median_rows(passes: list[dict]) -> list[dict]:
    out = []
    for i, theta in enumerate(THRESHOLDS):
        P = [p["rows"][i]["precision"] for p in passes]
        R = [p["rows"][i]["recall"] for p in passes]
        F = [p["rows"][i]["f1"] for p in passes]
        A = [p["rows"][i]["accepted"] for p in passes]
        out.append({
            "theta": theta,
            "precision_median": round(statistics.median(P), 4), "precision_runs": P,
            "recall_median": round(statistics.median(R), 4), "recall_runs": R,
            "f1_median": round(statistics.median(F), 4), "f1_runs": F,
            "accepted_median": statistics.median(A), "accepted_runs": A,
        })
    return out


def run_for_template(path: Path, label: str, gold, concept_lookup, few_shot_text,
                     providers, repeats: int) -> dict:
    classify_mod.PROMPT_TEMPLATE_PATH = str(path)
    print(f"\n===== {label}  ({path.name})  x{repeats} =====", flush=True)
    passes = []
    for k in range(1, repeats + 1):
        print(f"--- pass {k}/{repeats} ---", flush=True)
        passes.append(_one_pass(gold, concept_lookup, few_shot_text, providers,
                                f"{label} p{k}"))
    return {"label": label, "template": str(path), "passes": passes,
            "median": _median_rows(passes)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=str, default="E3_neukalibrierung.json")
    args = ap.parse_args()

    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    concept_lookup = _load_concept_lookup()
    # G_manual (Juli 2026) referenziert DQR-Dimensionsdeskriptoren unter den
    # alten data.bmbf.de-URIs. Nach der Namespace-Migration (Commit f15f382)
    # tragen dieselben Deskriptoren hr-qde.org/harmonised/source/dqr/-URIs
    # (KQR dqr_2d, identische deutsche Definitionen). Alias-Keys ergaenzen,
    # damit die 74-Paar-Goldmenge unveraendert nutzbar bleibt. Alle 7
    # betroffenen Paare sind RELATED (gold nicht in K): betrifft nur die
    # Precision ueber False Positives, nicht den Recall.
    _OLD = "http://data.bmbf.de/dqr/"
    _NEW = "http://hr-qde.org/harmonised/source/dqr/"
    _aliased = 0
    for it in gold:
        for key in ("subject_id", "object_id"):
            uri = it[key]
            if uri.startswith(_OLD):
                new = uri.replace(_OLD, _NEW)
                if new in concept_lookup:
                    concept_lookup[uri] = concept_lookup[new]  # dqr_2d, einheitlich
                    _aliased += 1
    print(f"DQR-URI-Aliasse ergaenzt: {_aliased}")
    few_shot_text = _few_shot_text_for_n_fs(3)

    missing = sorted({e for it in gold for e in (it["subject_id"], it["object_id"])
                      if e not in concept_lookup})
    print(f"G_manual: {len(gold)} Paare | concept_lookup: {len(concept_lookup)} URIs | "
          f"fehlend: {len(missing)}")
    for m in missing:
        print("  FEHLT:", m)
    print("\nFew-Shot-Block (n_FS=3):\n" + few_shot_text)

    if args.dry_run:
        for path, lbl in [(TPL_REVISED, "revised"), (TPL_PREREV, "pre-revision")]:
            classify_mod.PROMPT_TEMPLATE_PATH = str(path)
            it = gold[0]
            from app.pipeline.step3_classification.classify import build_prompt
            p = build_prompt(
                concept_lookup[it["subject_id"]]["pref_label"],
                concept_lookup[it["subject_id"]].get("definition", ""),
                concept_lookup[it["subject_id"]]["kqr_id"],
                concept_lookup[it["object_id"]]["pref_label"],
                concept_lookup[it["object_id"]].get("definition", ""),
                concept_lookup[it["object_id"]]["kqr_id"],
                few_shot_text,
            )
            print(f"\n----- PROMPT [{lbl}] ({len(p)} Zeichen) -----\n{p}\n")
        if missing:
            print("ABBRUCH: fehlende Konzepte im Lookup.")
            sys.exit(1)
        print("dry-run ok.")
        return

    if missing:
        raise SystemExit(f"{len(missing)} G_manual-Konzepte nicht auflösbar - Abbruch.")

    providers = get_providers_from_config(settings)
    print("Provider:", [p.model_id for p in providers])

    t0 = time.time()
    revised = run_for_template(TPL_REVISED, "revised", gold, concept_lookup,
                               few_shot_text, providers, args.repeats)
    prerev = run_for_template(TPL_PREREV, "pre-revision", gold, concept_lookup,
                              few_shot_text, providers, args.repeats)

    payload = {
        "_meta": {
            "experiment": "E3 isolierte Neukalibrierung (revidierter vs. Alt-Prompt)",
            "date": time.strftime("%Y-%m-%d"),
            "isolated_factor": "prompts/classification_prompt_template.txt Block 4 "
                               "(Richtungshinweis) + Few-Shot-Header-Label",
            "held_constant": {
                "provider": [p.model_id for p in providers],
                "n_fs": 3,
                "few_shot_pool": "eval/G_struct.json",
                "gold": "eval/gold/G_manual.json (74 Paare)",
                "runs_per_pair": settings.classification_runs_per_pair,
                "temperature": 0.0,
            },
            "pre_revision_source": "MA_Oberhuber_0.61.pdf, Listing 4.5 (S. 129), "
                                   "rekonstruiert",
            "repeats": args.repeats,
            "wall_time_s": round(time.time() - t0),
        },
        "revised": revised,
        "pre_revision": prerev,
    }
    outpath = SCRATCH / args.out
    outpath.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\ngeschrieben: {outpath}")

    def show(block):
        print(f"\n--- {block['label']} (Median über {args.repeats}) ---")
        print(f"{'theta':>6} {'P_med':>7} {'R_med':>7} {'F1_med':>7} {'acc_med':>8}   runs(R)")
        for row in block["median"]:
            print(f"{row['theta']:>6.2f} {row['precision_median']:>7.4f} "
                  f"{row['recall_median']:>7.4f} {row['f1_median']:>7.4f} "
                  f"{row['accepted_median']:>8}   {row['recall_runs']}")
        for k, pss in enumerate(block["passes"], 1):
            print(f"  pass{k} final_relation_dist: {pss['final_relation_dist']}")
            print(f"  pass{k} confidence_dist:     {pss['confidence_dist']}")
    show(revised)
    show(prerev)


if __name__ == "__main__":
    main()
