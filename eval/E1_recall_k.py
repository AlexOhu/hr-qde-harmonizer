"""
E1 - Recall@k: ANN-Suchparameter (VH1.5)

ELM wird nicht als Vergleichs-KQR
verwendet (vgl. Kapitel 3): ELM enthaelt keine eigenen Kompetenzinstanzen.
Goldmengen aus eval/:

  G_struct.json       - 8 normative DQR<->EQF-Niveaupaare (confidence=1.0,
                        struktureller Shortcut, kein LLM-Aufruf). EQF ist
                        aktuell nicht formalisiert -> erwartungsgemaess
                        0 evaluierbare Paare.
  G_levels.json       - 113 e-CF-Dimension-3 <-> DQR-Anker-Paare aus
                        e-CF 3.0 (CWA 16234-1:2014). Diese Goldmenge wird
                        separat ueber --gold ausgewertet.

Verwendung:
    python eval/E1_recall_k.py [--k-values 5 10 15 20 30]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

K_VALUES = [5, 10, 15, 20, 30]

_STRUCT_PATH = ROOT / "eval" / "G_struct.json"


def _load_gold_pairs(path: Path) -> tuple[list[tuple[str, str]], list[dict]]:
    """Liefert (gold_pairs, raw_pairs). gold_pairs enthaelt alle Paare
    unabhaengig vom Aufloesungsstatus; die Filterung auf 'evaluierbar'
    erfolgt in recall_at_k() anhand der tatsaechlich vorhandenen Embeddings."""
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_pairs = data["pairs"]
    pairs = [(p["subject_id"], p["object_id"]) for p in raw_pairs]
    return pairs, raw_pairs


def _load_all_embeddings(kqr_ids: list[str] | None = None) -> dict[str, np.ndarray]:
    """Kombiniert Embeddings der registrierten KQR (bereits persistiert/gecacht
    ueber kqr_service, kein On-the-fly-Recompute noetig).

    ``kqr_ids`` beschraenkt den Embedding-Raum auf die genannten KQR. Fuer den
    Liefer-Nachzug wird ``esco_skeleton_oberhuber ecf dqr_3`` gesetzt, damit
    nicht der abgeloeste 956er-Ausschnitt (``esco_v1_2_ict_ausschnitt``)
    mitgemischt wird (ADR-25)."""
    from app.services import kqr_service

    wanted = set(kqr_ids) if kqr_ids else None
    embeddings: dict[str, np.ndarray] = {}
    for kqr in kqr_service.list_kqr():
        if wanted is not None and kqr.id not in wanted:
            continue
        try:
            embeddings.update(kqr_service.get_embeddings(kqr.id))
        except (KeyError, ValueError):
            continue
    return embeddings


def recall_at_k(
    gold_pairs: list[tuple[str, str]],
    embeddings: dict[str, np.ndarray],
    k: int,
) -> tuple[float, int, int]:
    """Gibt (recall, hits, total_evaluable) zurueck.

    G_evaluierbar = Teilmenge von gold_pairs, bei der beide URIs ein
    Embedding besitzen. Fuer jedes evaluierbare Paar wird geprueft, ob
    object_uri unter den Top-k-Nachbarn von subject_uri liegt, gesucht
    im Embedding-Raum aller eindeutigen Objekt-URIs der evaluierbaren
    Goldpaare. Bei G_levels sind dies die sechs DQR-Anker L3--L8, nicht die
    acht Knoten der Quelldatei. Recall@8 ist deshalb eine konstruktive
    Obergrenze. Die produktive Kandidatengenerierung verwendet dagegen den
    vollstaendigen Ziel-KQR-Raum.
    """
    import faiss

    evaluable = [(s, o) for s, o in gold_pairs if s in embeddings and o in embeddings]
    if not evaluable:
        return 0.0, 0, 0

    object_uris = list({o for _, o in evaluable})
    obj_matrix = np.stack([embeddings[u] for u in object_uris]).astype("float32")
    faiss.normalize_L2(obj_matrix)
    index = faiss.IndexFlatIP(obj_matrix.shape[1])
    index.add(obj_matrix)

    subject_uris = [s for s, _ in evaluable]
    subj_matrix = np.stack([embeddings[u] for u in subject_uris]).astype("float32")
    faiss.normalize_L2(subj_matrix)

    k_eff = min(k, len(object_uris))
    _, indices = index.search(subj_matrix, k_eff)

    hits = 0
    for row, (_, gold_object) in enumerate(evaluable):
        neighbors = {object_uris[idx] for idx in indices[row] if idx >= 0}
        if gold_object in neighbors:
            hits += 1

    return hits / len(evaluable), hits, len(evaluable)


def _print_table(
    title: str,
    gold_pairs: list[tuple[str, str]],
    embeddings: dict[str, np.ndarray],
    k_values: list[int],
) -> list[dict]:
    total = len(gold_pairs)
    evaluable_count = len([(s, o) for s, o in gold_pairs if s in embeddings and o in embeddings])
    excluded = total - evaluable_count

    print(f"\n=== {title} (n={total}, evaluierbar={evaluable_count}, ausgeschlossen={excluded}) ===")

    if evaluable_count == 0:
        print("\n k   | Recall@k | Neu  | Kumulativ")
        print("-----|----------|------|----------")
        for k in k_values:
            print(f"{k:>4} |      n/a |  n/a |       n/a")
        print(f"\nAusgeschlossene Paare (URI nicht im Korpus): {excluded}/{total}")
        return []

    print("\n k   | Recall@k | Neu  | Kumulativ")
    print("-----|----------|------|----------")
    results = []
    prev_hits = 0
    for k in k_values:
        recall, hits, n_eval = recall_at_k(gold_pairs, embeddings, k)
        new_hits = hits - prev_hits
        results.append({
            "k": k, "recall": round(recall, 4), "hits": hits,
            "new_hits": max(new_hits, 0), "total_evaluable": n_eval,
        })
        print(f"{k:>4} | {recall:>8.3f} | {max(new_hits, 0):>4} | {hits:>9}")
        prev_hits = hits

    if excluded:
        print(f"\nAusgeschlossene Paare (URI nicht im Korpus): {excluded}/{total}")

    min_k_90 = next((r["k"] for r in results if r["recall"] >= 0.90), None)
    print(f"Empfehlung k: {min_k_90 if min_k_90 else 'Datenbasis zu klein fuer Aussage (Recall>=0.90 nie erreicht)'}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="E1: Recall@k (G_struct)")
    parser.add_argument("--k-values", nargs="+", type=int, default=K_VALUES)
    parser.add_argument("--kqr", nargs="+", default=None,
                        help="Embedding-Raum auf diese KQR beschraenken "
                             "(Liefer-Nachzug: esco_skeleton_oberhuber ecf dqr_3)")
    parser.add_argument("--gold", type=Path, default=None,
                        help="Einzelne Goldmenge (z. B. eval/G_levels.json) statt "
                             "G_struct auswerten.")
    parser.add_argument("--output", type=Path, default=ROOT / "eval" / "results" / "E1_recall_k.json")
    args = parser.parse_args()

    k_values = sorted(args.k_values)

    embeddings = _load_all_embeddings(args.kqr)
    scope = ", ".join(args.kqr) if args.kqr else "alle registrierten KQR"
    print(f"Embedding-Raum: {len(embeddings)} Konzepte ({scope}).")

    if args.gold is not None:
        gold_pairs, _ = _load_gold_pairs(args.gold)
        results = _print_table(args.gold.stem, gold_pairs, embeddings, k_values)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({args.gold.stem: results}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nErgebnis gespeichert: {args.output}")
        return

    struct_pairs, _ = _load_gold_pairs(_STRUCT_PATH)

    struct_results = _print_table(
        "G_struct: DQR<->EQF Niveaupaare", struct_pairs, embeddings, k_values
    )
    if not struct_results:
        print("Grund: EQF ist nicht formalisiert (data/formalized/ enthaelt kein eqf.ttl).")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {"g_struct": struct_results},
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nErgebnis gespeichert: {args.output}")


if __name__ == "__main__":
    main()
