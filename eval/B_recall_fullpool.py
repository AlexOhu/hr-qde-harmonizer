"""
B_recall_fullpool - Recall@k im vollstaendigen Ziel-KQR-Raum.

E1 (eval/E1_recall_k.py) baut den FAISS-Index nur aus den Objekt-URIs der
evaluierbaren Goldpaare. Bei kleinen Goldmengen ist k dann ein grosser
Anteil des Suchraums oder groesser als dieser, und Recall@k wird
konstruktiv hoch. Dieses Skript misst denselben Recall@k gegen den
vollstaendigen Ziel-KQR, wie ihn die produktive Kandidatengenerierung
verwendet. Es veraendert E1 nicht.

Ziel-KQR je Goldmenge (fest, um den abgeloesten 956er-ESCO-Ausschnitt
auszuschliessen, vgl. ADR-25):
  G_manual (74, e-CF->ESCO)   -> esco_skeleton_oberhuber
  G_struct (DQR<->EQF)        -> eqf_2d

Verwendung:
    python eval/B_recall_fullpool.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

K_VALUES = [5, 10, 15, 20, 30, 50, 100]
OUT = ROOT / "eval" / "results" / "B_recall_fullpool.json"

GOLDSETS = [
    ("G_manual",      ROOT / "eval" / "gold" / "G_manual.json",  "esco_skeleton_oberhuber"),
    # G_manual wurde gegen den 956er-Ausschnitt gebaut; alle 74 Objekte liegen dort.
    ("G_manual@956",  ROOT / "eval" / "gold" / "G_manual.json",  "esco_v1_2_ict_ausschnitt"),
    ("G_struct",      ROOT / "eval" / "G_struct.json",           "eqf_2d"),
]


def load_pairs(path: Path) -> list[tuple[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["pairs"] if isinstance(data, dict) else data
    return [(r["subject_id"], r["object_id"]) for r in rows]


def ranks(pairs, subj_emb, pool_uris, pool_mat) -> list[int]:
    """1-basierter Rang des Goldobjekts unter allen Pool-Konzepten."""
    idx = {u: i for i, u in enumerate(pool_uris)}
    out = []
    for s, o in pairs:
        sims = pool_mat @ subj_emb[s]
        out.append(int(np.sum(sims > sims[idx[o]])) + 1)
    return out


def main() -> None:
    from app.services import kqr_service

    emb: dict[str, np.ndarray] = {}
    for kqr in kqr_service.list_kqr():
        if kqr.id == "esco_v1_2_ict_ausschnitt":
            continue
        emb.update(kqr_service.get_embeddings(kqr.id))

    result = {"_meta": {"k_values": K_VALUES,
                        "note": "Rang gegen vollstaendigen Ziel-KQR; E1-Pool = nur Goldobjekte"}}
    for name, path, target in GOLDSETS:
        pool = kqr_service.get_embeddings(target)
        pool_uris = list(pool)
        pool_mat = np.stack([pool[u] for u in pool_uris]).astype("float32")
        pool_mat /= np.linalg.norm(pool_mat, axis=1, keepdims=True)
        subj = {u: v / np.linalg.norm(v) for u, v in emb.items()}

        pairs = load_pairs(path)
        ev = [(s, o) for s, o in pairs if s in subj and o in pool]
        r_full = ranks(ev, subj, pool_uris, pool_mat)

        gold_objs = sorted({o for _, o in ev})
        gm = pool_mat[[pool_uris.index(o) for o in gold_objs]]
        r_e1 = ranks(ev, subj, gold_objs, gm)

        n = len(ev)
        result[name] = {
            "target_kqr": target, "pool_size_full": len(pool_uris),
            "pool_size_e1_style": len(gold_objs),
            "pairs_total": len(pairs), "pairs_evaluable": n,
            "recall_full":  {k: sum(r <= k for r in r_full) / n for k in K_VALUES} if n else {},
            "recall_e1_style": {k: sum(r <= k for r in r_e1) / n for k in K_VALUES} if n else {},
            "median_rank_full": float(np.median(r_full)) if n else None,
            "max_rank_full": max(r_full) if n else None,
        }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
