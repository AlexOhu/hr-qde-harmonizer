"""
R_rerun - LLM-Neulauf mit Protokollierung pro Paar und Einzellauf.

Zweck: Grundlage fuer Konfidenzintervalle, gepaarte Vergleiche mit der
Kosinus-Baseline und die Kombination Kosinus+LLM fuer EQUIVALENT.
Die Klassifikationslogik (Prompt, Parsing, Mehrheitsentscheid) wird
unveraendert aus app.pipeline.step3_classification.classify uebernommen.

Abweichungen von den Laeufen vom August/September 2026, bewusst gesetzt:
  * Temperatur wird explizit gesetzt und protokolliert (Standard 0,0).
    Die .env enthielt CLASSIFICATION_TEMPERATURE=0.3, waehrend
    ClassificationRun.temperature fest 0,0 schreibt.
  * Das Modell wird beim ersten Aufruf aufgeloest (response.model) und
    fuer alle weiteren Aufrufe fest auf diese Version gesetzt.
  * Parsing-Fehler brechen den Lauf nicht ab, sondern werden als
    ungueltige Stimme protokolliert.
  * Paare, deren Konzepte nicht in der Registry liegen, werden ausgelassen
    und im Ergebnis aufgefuehrt.

Verwendung (aus dem Repo-Wurzelverzeichnis):
    python eval/R_rerun.py --config prod --passes 3
    python eval/R_rerun.py --config ablation
    python eval/R_rerun.py --config temp03
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GOLD_JSON = ROOT / "eval" / "gold" / "G_manual.json"
OUT_DIR = ROOT / "eval" / "results" / "rerun_2026-10"
TEMPLATE = ROOT / "prompts" / "classification_prompt_template.txt"

CONFIGS = {
    # name: (liste von (n_fs, temperatur), anzahl durchgaenge)
    "prod":     ([(3, 0.0)], 3),
    # Produktionspfad e-CF <-> ESCO-Skelett: find_structural_shortcuts liefert
    # 0 Treffer, der Prompt enthaelt "(keine Crosswalk-Beispiele verfuegbar)",
    # also n_FS = 0. "prod" (n_FS = 3 mit G_struct-Ankern) ist eine Variante.
    "prod0":    ([(0, 0.0)], 3),
    "ablation": ([(0, 0.0), (1, 0.0), (5, 0.0)], 1),
    # Fuer eine durchgehend dreifache E2-Tabelle: n_FS = 1 und 5 mit je drei Durchgaengen.
    "abl15":    ([(1, 0.0), (5, 0.0)], 3),
    "temp03":   ([(3, 0.3)], 1),
}


class LoggingMistral:
    """Duenne Huelle um MistralProvider: setzt Temperatur explizit, loest
    das Modell beim ersten Aufruf auf und protokolliert response.model."""

    def __init__(self, temperature: float, model: str | None = None):
        from app.config import settings
        from app.pipeline.step3_classification.llm_provider.mistral_provider import (
            MistralProvider,
        )
        self._p = MistralProvider(settings.mistral_api_key,
                                  model or settings.mistral_model, temperature)
        self.temperature = temperature

    @property
    def model_id(self) -> str:
        return self._p.model_id

    def complete(self, prompt: str, max_tokens: int = 200) -> tuple[str, str]:
        p = self._p
        for attempt in range(1, 6):
            try:
                r = p._client.chat.complete(
                    model=p._model, temperature=self.temperature,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                return (r.choices[0].message.content or "").strip(), r.model
            except p._error_cls as exc:  # 429/5xx: warten und erneut
                if attempt == 5:
                    raise
                time.sleep(5 * attempt)
        raise RuntimeError("unreachable")

    def pin(self) -> str:
        """'latest'-Alias ueber die Modellliste der API auf eine datierte
        Version aufloesen und festsetzen. response.model liefert nur den
        angefragten Alias zurueck und taugt dafuer nicht."""
        alias = self._p._model
        if alias.endswith("-latest"):
            for m in self._p._client.models.list().data:
                if alias in (getattr(m, "aliases", None) or []) and not m.id.endswith("-latest") \
                        and m.id.startswith(alias.removesuffix("-latest")):
                    self._p._model = m.id
                    break
        return self._p._model


class _Fixed:
    """Adapter, damit call_classification_model den bereits geholten Text
    unveraendert mit der Produktionslogik parst."""

    def __init__(self, text: str, model_id: str):
        self._t, self.model_id = text, model_id

    def complete(self, prompt: str) -> str:
        return self._t


def classify_logged(item, lookup, few_shot, llm: LoggingMistral, runs: int) -> dict:
    from app.pipeline.step3_classification.classify import (
        ClassificationParseError, build_prompt, call_classification_model, majority_vote,
    )
    a, b = lookup[item["subject_id"]], lookup[item["object_id"]]
    prompt = build_prompt(a["pref_label"], a.get("definition", ""), a["kqr_id"],
                          b["pref_label"], b.get("definition", ""), b["kqr_id"], few_shot)
    run_log, valid = [], []
    for _ in range(runs):
        text, model = llm.complete(prompt)
        try:
            r = call_classification_model(prompt, _Fixed(text, f"mistral/{model}"))
            valid.append(r)
            run_log.append({"relation": r.relation.value, "reasoning": r.reasoning,
                            "model": model})
        except ClassificationParseError:
            run_log.append({"relation": "PARSE_ERROR", "raw": text, "model": model})
    final, conf = (majority_vote(valid) if valid else (None, 0.0))
    # Konfidenz bezogen auf alle Laeufe (wie Produktion bei fehlerfreien Laeufen)
    n_major = max((sum(r["relation"] == x["relation"] for x in run_log)
                   for r in run_log if r["relation"] != "PARSE_ERROR"), default=0)
    return {"subject_id": item["subject_id"], "object_id": item["object_id"],
            "subject_label": item["subject_label"], "object_label": item["object_label"],
            "gold": item["gold_relation"],
            "final": final.value if final else "UNRESOLVED",
            "votes_for_final": n_major if final else 0, "runs_total": runs,
            "confidence": conf if final else 0.0, "runs": run_log}


def main() -> None:
    import os
    from app.config import settings
    from eval.E2_few_shot import _few_shot_text_for_n_fs, _load_concept_lookup

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", choices=CONFIGS, required=True)
    ap.add_argument("--passes", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--model", default=None, help="feste Modellversion (sonst aufloesen)")
    args = ap.parse_args()
    os.chdir(ROOT)  # build_prompt liest das Template relativ

    gold = json.loads(GOLD_JSON.read_text(encoding="utf-8"))
    lookup = _load_concept_lookup()
    usable = [g for g in gold if g["subject_id"] in lookup and g["object_id"] in lookup]
    skipped = [g["subject_id"] + " -> " + g["object_id"] for g in gold if g not in usable]
    tmpl_hash = hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()[:16]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    settings_list, passes = CONFIGS[args.config]
    passes = args.passes or passes
    for n_fs, temp in settings_list:
        llm = LoggingMistral(temp, args.model)
        resolved = args.model or llm.pin()
        few_shot = _few_shot_text_for_n_fs(n_fs)
        for k in range(1, passes + 1):
            out = OUT_DIR / f"{args.config}_nfs{n_fs}_t{temp:.1f}_pass{k}.json"
            if out.exists():
                print(f"vorhanden, uebersprungen: {out.name}")
                continue
            t0 = time.time()
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                rows = list(ex.map(lambda it: classify_logged(
                    it, lookup, few_shot, llm, settings.classification_runs_per_pair), usable))
            meta = {"config": args.config, "n_fs": n_fs, "temperature": temp,
                    "pass": k, "model_requested": settings.mistral_model,
                    "model_resolved": resolved, "runs_per_pair": settings.classification_runs_per_pair,
                    "prompt_template_sha256_16": tmpl_hash, "few_shot_pool": "eval/G_struct.json",
                    "gold": "eval/gold/G_manual.json", "pairs_used": len(usable),
                    "pairs_skipped_not_in_registry": skipped,
                    "started_utc": datetime.fromtimestamp(t0, timezone.utc).isoformat(),
                    "wall_time_s": round(time.time() - t0, 1)}
            out.write_text(json.dumps({"_meta": meta, "pairs": rows}, indent=2,
                                      ensure_ascii=False), encoding="utf-8")
            acc = sum(r["final"] == r["gold"] for r in rows) / len(rows)
            print(f"{out.name}: {len(rows)} Paare, Acc={acc:.3f}, {meta['wall_time_s']} s, Modell {resolved}")


if __name__ == "__main__":
    main()
