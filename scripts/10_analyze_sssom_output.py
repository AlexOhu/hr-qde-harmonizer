"""
Analysiert eine SSSOM-Export-TSV (Schritt 4a, app/pipeline/step4_export/
sssom_writer.py) und gibt eine Kennzahlen-Uebersicht auf der Konsole aus:
Relationsverteilung, Confidence-Statistik, Top/Bottom-10 nach Confidence
und ein ASCII-Histogramm der Confidence-Verteilung.

Ohne Argument wird die neueste Datei unter data/sssom/ (nach Aenderungs-
zeitpunkt) geladen; alternativ kann ein fester Pfad uebergeben werden:

    python scripts/10_analyze_sssom_output.py [pfad/zur/datei.tsv]
"""

from __future__ import annotations

import csv
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SSSOM_DIR = ROOT / "data" / "sssom"

# predicate_id -> Kurzname fuer die Relationszaehlung. Alles, was hier nicht
# hinein passt (z.B. leeres predicate_id oder ein kuenftiges skos:UNRESOLVED-
# Provisorium), landet im "unresolved"-Sammelbecken -- vgl. RelationType in
# app/models/schemas.py, wo UNRESOLVED aktuell auf skos:relatedMatch
# abgebildet und ohnehin nicht exportiert wird (_EXCLUDED_FROM_K).
_RELATION_LABELS = {
    "skos:exactMatch": "exactMatch",
    "skos:broadMatch": "broadMatch",
    "skos:narrowMatch": "narrowMatch",
    "skos:relatedMatch": "relatedMatch",
}
_RELATION_ORDER = ["exactMatch", "broadMatch", "narrowMatch", "relatedMatch", "unresolved"]


def find_latest_sssom_file(sssom_dir: Path) -> Path:
    candidates = sorted(sssom_dir.glob("*.tsv"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise SystemExit(f"Fehler: keine .tsv-Dateien unter {sssom_dir} gefunden.")
    return candidates[-1]


def load_rows(tsv_path: Path) -> list[dict[str, str]]:
    with tsv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def relation_label(predicate_id: str) -> str:
    return _RELATION_LABELS.get(predicate_id, "unresolved")


def parse_confidence(raw: str) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def print_relation_counts(rows: list[dict[str, str]]) -> None:
    counts = {label: 0 for label in _RELATION_ORDER}
    for row in rows:
        counts[relation_label(row.get("predicate_id", ""))] += 1

    print("\nNach Relation:")
    for label in _RELATION_ORDER:
        print(f"  {label:<14} {counts[label]}")


def print_confidence_stats(confidences: list[float]) -> None:
    print("\nConfidence-Statistik:")
    if not confidences:
        print("  keine gueltigen mapping_confidence-Werte vorhanden.")
        return
    print(f"  Min:    {min(confidences):.4f}")
    print(f"  Max:    {max(confidences):.4f}")
    print(f"  Mean:   {statistics.mean(confidences):.4f}")
    print(f"  Median: {statistics.median(confidences):.4f}")


def print_extremes(rows_with_confidence: list[tuple[dict[str, str], float]], n: int = 10) -> None:
    ranked = sorted(rows_with_confidence, key=lambda item: item[1], reverse=True)

    def print_table(title: str, entries: list[tuple[dict[str, str], float]]) -> None:
        print(f"\n{title}:")
        if not entries:
            print("  keine Daten vorhanden.")
            return
        for row, confidence in entries:
            relation = relation_label(row.get("predicate_id", ""))
            print(f"  {row.get('subject_id', '')} -> {row.get('object_id', '')}")
            print(f"    relation={relation}  confidence={confidence:.4f}")

    print_table(f"Top-{n} hoechste Confidence", ranked[:n])
    print_table(f"Bottom-{n} niedrigste Confidence", list(reversed(ranked[-n:])) if ranked else [])


def print_histogram(confidences: list[float], bucket_width: float = 0.2) -> None:
    print("\nHistogramm (Confidence-Buckets):")
    if not confidences:
        print("  keine Daten vorhanden.")
        return

    n_buckets = round(1.0 / bucket_width)
    bucket_counts = [0] * n_buckets
    for value in confidences:
        idx = min(int(value / bucket_width), n_buckets - 1)
        bucket_counts[idx] += 1

    max_count = max(bucket_counts)
    bar_width = 50
    for i, count in enumerate(bucket_counts):
        lo = i * bucket_width
        hi = lo + bucket_width
        bracket = "]" if i == n_buckets - 1 else ")"
        bar_len = round((count / max_count) * bar_width) if max_count else 0
        bar = "#" * bar_len
        print(f"  [{lo:.1f}-{hi:.1f}{bracket} {bar:<{bar_width}} {count}")


def main() -> None:
    if len(sys.argv) > 1:
        tsv_path = Path(sys.argv[1])
        if not tsv_path.exists():
            raise SystemExit(f"Fehler: {tsv_path} nicht gefunden.")
    else:
        tsv_path = find_latest_sssom_file(SSSOM_DIR)

    print(f"Lade {tsv_path} ...")
    rows = load_rows(tsv_path)
    print(f"\nGesamt Mappings: {len(rows)}")

    print_relation_counts(rows)

    rows_with_confidence: list[tuple[dict[str, str], float]] = []
    n_invalid = 0
    for row in rows:
        confidence = parse_confidence(row.get("mapping_confidence", ""))
        if confidence is None:
            n_invalid += 1
            continue
        rows_with_confidence.append((row, confidence))
    if n_invalid:
        print(f"\nWarnung: {n_invalid} Zeile(n) ohne gueltige mapping_confidence ignoriert.")

    confidences = [c for _, c in rows_with_confidence]
    print_confidence_stats(confidences)
    print_extremes(rows_with_confidence)
    print_histogram(confidences)


if __name__ == "__main__":
    main()
