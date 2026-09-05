"""
Hilfsskript: Erstellt G_manual – manuell annotierbare Goldmenge (80 Paare,
balanciert über 4 Relationsklassen) aus ClassificationResult-Objekten.

Verwendung:
    # 1. Review-CSV erzeugen:
    python eval/build_gold_manual.py --kqr-a ecf --kqr-b esco_ict

    # 2. gold_relation-Spalte in G_manual_review.csv manuell befüllen.

    # 3. Finalisieren:
    python eval/build_gold_manual.py --finalize
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GOLD_DIR   = ROOT / "eval" / "gold"
REVIEW_CSV = GOLD_DIR / "G_manual_review.csv"
GOLD_JSON  = GOLD_DIR / "G_manual.json"
N_PER_CLASS = 20


def build_review_csv(kqr_a: str, kqr_b: str) -> None:
    from app.services import mapping_service
    from app.models.schemas import RelationType

    mapping_service.reload()
    results = mapping_service._classification_results

    # Nur Paare mit LLM-Mehrheitsentscheid (final_relation is not None)
    relevant = [
        r for r in results
        if r.final_relation is not None
    ]
    from app.services import kqr_service
    kqr_service.reload_registry()
    label_lookup: dict[str, str] = {}
    for kqr in kqr_service.list_kqr():
        for c in kqr_service.get_concepts(kqr.id):
            label_lookup[c.uri] = c.pref_label

    if kqr_a and kqr_b:
        concepts_a = {c.uri for c in kqr_service.get_concepts(kqr_a)}
        concepts_b = {c.uri for c in kqr_service.get_concepts(kqr_b)}
        relevant = [
            r for r in relevant
            if r.pair.concept_a in concepts_a and r.pair.concept_b in concepts_b
        ]

    by_class: dict[str, list] = {rel.value: [] for rel in RelationType}
    for r in relevant:
        by_class[r.final_relation.value].append(r)

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    with REVIEW_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "subject_id", "subject_label",
            "object_id", "object_label",
            "model_relation", "model_confidence",
            "gold_relation",   # <-- manuell befüllen
            "comment",
        ])
        for cls, items in by_class.items():
            for item in items[:N_PER_CLASS]:
                writer.writerow([
                    item.pair.concept_a, label_lookup.get(item.pair.concept_a, ""),
                    item.pair.concept_b, label_lookup.get(item.pair.concept_b, ""),
                    cls, f"{item.mapping_confidence:.2f}",
                    "",  # gold_relation: leer lassen
                    "",
                ])
    print(f"Review-CSV erstellt: {REVIEW_CSV}")
    print("Bitte 'gold_relation' in jeder Zeile befüllen,")
    print("dann: python eval/build_gold_manual.py --finalize")

def finalize_gold(review_csv: Path = REVIEW_CSV) -> None:
    """Liest die annotierte CSV ein und schreibt G_manual.json."""
    valid_relations = {"EQUIVALENT", "A_SUBSUMES_B", "B_SUBSUMES_A", "RELATED"}
    gold = []
    skipped = 0
    with review_csv.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            gold_rel = row.get("gold_relation", "").strip().upper()
            if gold_rel not in valid_relations:
                skipped += 1
                continue
            gold.append({
                "subject_id":     row["subject_id"],
                "subject_label":  row.get("subject_label", ""),
                "object_id":      row["object_id"],
                "object_label":   row.get("object_label", ""),
                "gold_relation":  gold_rel,
            })

    from collections import Counter
    dist = Counter(item["gold_relation"] for item in gold)
    print(f"G_manual: {len(gold)} Paare ({skipped} übersprungen)")
    for rel, count in sorted(dist.items()):
        print(f"  {rel}: {count}")

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    GOLD_JSON.write_text(
        json.dumps(gold, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Goldmenge gespeichert: {GOLD_JSON}")


def main() -> None:
    parser = argparse.ArgumentParser(description="G_manual aufbauen")
    parser.add_argument("--kqr-a", default="ecf")
    parser.add_argument("--kqr-b", default="esco_v1_2_ict_ausschnitt")
    parser.add_argument("--finalize", action="store_true",
                        help="Review-CSV nach Annotation einlesen")
    parser.add_argument("--review", type=Path, default=REVIEW_CSV)
    args = parser.parse_args()

    if args.finalize:
        finalize_gold(args.review)
    else:
        build_review_csv(args.kqr_a, args.kqr_b)


if __name__ == "__main__":
    main()
