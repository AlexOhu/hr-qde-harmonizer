"""Isolierter, produktionsneutraler Runner fuer den Embedding-Modellvergleich.

Schreibt nur die mit --output angegebene JSON-Datei. Modellzugriff ist strikt
offline und erfolgt ueber einen expliziten lokalen Snapshotpfad.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

CODE_ROOT = Path(r"E:\Fernuni\Master\Masterarbeit\hrqde-harmonizer")
sys.path.insert(0, str(CODE_ROOT))

E5_INSTRUCTION = (
    "Given a competency or proficiency statement from one qualification framework, "
    "retrieve the semantically equivalent or most closely corresponding concept in "
    "the target qualification framework."
)
E1_K = [5, 10, 15, 20, 30, 50, 100]
E1B_K = [1, 3, 5, 8]

DATASETS = [
    {
        "name": "G_manual",
        "gold": CODE_ROOT / "eval" / "gold" / "G_manual.json",
        "target_kqr": "esco_skeleton_oberhuber",
        "pool_policy": "complete_target_kqr",
        "k_values": E1_K,
    },
    {
        "name": "G_manual@956",
        "gold": CODE_ROOT / "eval" / "gold" / "G_manual.json",
        "target_kqr": "esco_v1_2_ict_ausschnitt",
        "pool_policy": "complete_target_kqr",
        "k_values": E1_K,
    },
    {
        "name": "G_struct",
        "gold": CODE_ROOT / "eval" / "G_struct.json",
        "target_kqr": "eqf_2d",
        "pool_policy": "complete_target_kqr",
        "k_values": E1_K,
    },
    {
        "name": "G_levels",
        "gold": CODE_ROOT / "eval" / "G_levels.json",
        "target_kqr": "dqr_1d",
        "pool_policy": "evaluable_gold_objects",
        "k_values": E1B_K,
    },
]


def load_pairs(path: Path) -> list[tuple[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["pairs"] if isinstance(data, dict) else data
    return [(row["subject_id"], row["object_id"]) for row in rows]


def concept_text(concept: object) -> str:
    return f"{concept.pref_label}. {concept.definition or ''}".strip()


def peak_process_rss_bytes() -> int | None:
    """Vom Windows-Kernel gefuehrtes Peak Working Set des aktuellen Prozesses."""
    if os.name != "nt":
        return None

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    get_current_process = ctypes.windll.kernel32.GetCurrentProcess
    get_current_process.restype = ctypes.c_void_p
    handle = get_current_process()
    get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
    get_process_memory_info.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ProcessMemoryCounters),
        ctypes.c_ulong,
    ]
    get_process_memory_info.restype = ctypes.c_int
    ok = get_process_memory_info(
        handle, ctypes.byref(counters), counters.cb
    )
    return int(counters.PeakWorkingSetSize) if ok else None


def encode(model: object, texts: list[str], batch_size: int) -> np.ndarray:
    return model.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    ).astype("float32")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["mpnet", "e5"], required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    snapshot = args.snapshot.resolve()
    if not snapshot.is_dir():
        raise SystemExit(f"Lokaler Snapshot fehlt: {snapshot}")

    from sentence_transformers import SentenceTransformer
    from app.services import kqr_service

    started = time.perf_counter()
    stage = time.perf_counter()
    model = SentenceTransformer(str(snapshot), local_files_only=True, device="cpu")
    model_load_s = time.perf_counter() - stage

    # B_recall_fullpool.py kombiniert fuer die Query-Seite alle registrierten
    # KQR ausser dem historischen 956er-Zielpool. Reihenfolge/Overwrite werden
    # durch list_kqr() und dict-Zuweisung gespiegelt.
    query_concepts: dict[str, object] = {}
    concepts_by_kqr: dict[str, list[object]] = {}
    for kqr in kqr_service.list_kqr():
        concepts = kqr_service.get_concepts(kqr.id)
        concepts_by_kqr[kqr.id] = concepts
        if kqr.id != "esco_v1_2_ict_ausschnitt":
            query_concepts.update({concept.uri: concept for concept in concepts})

    pairs_by_name = {dataset["name"]: load_pairs(dataset["gold"]) for dataset in DATASETS}
    query_uris = sorted(
            {
                subject
                for pairs in pairs_by_name.values()
                for subject, _ in pairs
                if subject in query_concepts
            }
    )
    raw_query_texts = [concept_text(query_concepts[uri]) for uri in query_uris]
    if args.model == "e5":
        query_texts = [
            f"Instruct: {E5_INSTRUCTION}\nQuery: {text}" for text in raw_query_texts
        ]
    else:
        query_texts = raw_query_texts

    stage = time.perf_counter()
    query_matrix = encode(model, query_texts, args.batch_size)
    query_encode_s = time.perf_counter() - stage
    query_vectors = dict(zip(query_uris, query_matrix))

    target_vectors: dict[str, dict[str, np.ndarray]] = {}
    target_encode_s: dict[str, float] = {}
    for kqr_id in sorted({dataset["target_kqr"] for dataset in DATASETS}):
        concepts = concepts_by_kqr[kqr_id]
        stage = time.perf_counter()
        matrix = encode(model, [concept_text(concept) for concept in concepts], args.batch_size)
        target_encode_s[kqr_id] = time.perf_counter() - stage
        target_vectors[kqr_id] = {
            concept.uri: vector for concept, vector in zip(concepts, matrix)
        }

    stage = time.perf_counter()
    results: dict[str, object] = {}
    for dataset in DATASETS:
        pairs = pairs_by_name[dataset["name"]]
        target = target_vectors[dataset["target_kqr"]]
        evaluable = [(s, o) for s, o in pairs if s in query_vectors and o in target]
        if dataset["pool_policy"] == "evaluable_gold_objects":
            pool_uris = sorted({o for _, o in evaluable})
        else:
            pool_uris = list(target)
        pool_matrix = np.stack([target[uri] for uri in pool_uris]).astype("float32")
        pool_index = {uri: i for i, uri in enumerate(pool_uris)}

        pair_results = []
        ranks = []
        for subject, gold_object in evaluable:
            scores = pool_matrix @ query_vectors[subject]
            gold_score = float(scores[pool_index[gold_object]])
            rank = int(np.sum(scores > gold_score)) + 1
            ranks.append(rank)
            pair_results.append(
                {
                    "subject_id": subject,
                    "object_id": gold_object,
                    "gold_score": gold_score,
                    "rank": rank,
                    "hits": {
                        str(k): rank <= min(k, len(pool_uris))
                        for k in dataset["k_values"]
                    },
                }
            )

        n = len(evaluable)
        results[dataset["name"]] = {
            "target_kqr": dataset["target_kqr"],
            "pool_policy": dataset["pool_policy"],
            "pool_size": len(pool_uris),
            "pairs_total": len(pairs),
            "pairs_evaluable": n,
            "k_values": dataset["k_values"],
            "recall": {
                str(k): sum(rank <= min(k, len(pool_uris)) for rank in ranks) / n
                if n
                else None
                for k in dataset["k_values"]
            },
            "median_rank": float(np.median(ranks)) if ranks else None,
            "max_rank": max(ranks) if ranks else None,
            "pairs": pair_results,
        }
    ranking_s = time.perf_counter() - stage

    payload = {
        "model_role": args.model,
        "model_id": (
            "intfloat/multilingual-e5-large-instruct"
            if args.model == "e5"
            else "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
        ),
        "snapshot_path": str(snapshot),
        "snapshot_revision": snapshot.name,
        "device": "cpu",
        "batch_size": args.batch_size,
        "query_instruction": E5_INSTRUCTION if args.model == "e5" else None,
        "query_template": "Instruct: {instruction}\\nQuery: {text}" if args.model == "e5" else "{text}",
        "target_template": "{text}",
        "normalization": "SentenceTransformer.encode(normalize_embeddings=True)",
        "tie_rule": "rank = 1 + count(score > gold_score)",
        "timing_seconds": {
            "model_load": model_load_s,
            "query_encoding": query_encode_s,
            "target_encoding_by_kqr": target_encode_s,
            "ranking": ranking_s,
            "total": time.perf_counter() - started,
        },
        "peak_process_rss_bytes": peak_process_rss_bytes(),
        "results": results,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
