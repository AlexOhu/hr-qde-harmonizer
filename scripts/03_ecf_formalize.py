"""
Formalisiert das e-CF-PDF (PDF-Pfad, Abschnitt 3.3.2) ueber
formalize_from_pdf: LLM-gestuetzte Segmentierung, Feldzuordnung und
Serialisierung als Turtle-Entwurf. Nutzt tests/fixtures/satellite_kqr.ttl
als Few-Shot-Vorlage (zeigt bereits ein e-CF-artiges Konzept im
Zielschema).

Der Entwurf ist laut Konzeption (VH1.3) UNVALIDIERT und muss vom
Systembetreuer manuell nachgebessert werden, bis validate_formalization
eine leere Fehlerliste liefert -- das ist hier bewusst kein
automatisiertes Gate, sondern ein manueller Pruefschritt.

Fuer die Wiedergabe in der Arbeit schreibt dieses Skript neben dem
Turtle-Entwurf zwei weitere Artefakte (gleicher Basisname, andere
Endung):
  - <output>.prompt.txt  der exakt an das LLM gesendete Prompt
  - <output>.run.json    Lauf-Metadaten (Modell, Parameter, Timing,
                          PDF-Checksumme, Validierungsfehler) als
                          reproduzierbares Provenance-Protokoll,
                          analog zu ClassificationRun/Mapping.

Voraussetzung: mindestens ein Provider aus LLM_PROVIDERS (.env) hat
seinen API-Key gesetzt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rdflib import RDF, SKOS, Graph  # noqa: E402

from app.models.schemas import KQR  # noqa: E402
from app.pipeline.step1_formalization.formalize import (  # noqa: E402
    formalize_from_pdf,
    validate_formalization,
)

DEFAULT_PDF = ROOT / "data" / "raw" / "European-e-Competence-Framework-3.0_DE.pdf"
# Für die e-CF-Formalisierung eignet sich ein Auszug aus
# data/formalized/ecf_template.ttl als Few-Shot besser als das
# generische fixture (es zeigt die Bereich-Kompetenz-Hierarchie).
# Bis die Template-Datei final validiert ist, bleibt das fixture aktiv.
FEW_SHOT_PATH = ROOT / "tests" / "fixtures" / "satellite_kqr.ttl"
OUTPUT_PATH = ROOT / "data" / "formalized" / "ecf_draft.ttl"

TOOL_VERSION = "HR-QDE-Harmonizer-v0.1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF, help="Pfad zum e-CF-PDF")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Zielpfad fuer das Turtle")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"e-CF-PDF nicht gefunden: {args.pdf}")
    if not FEW_SHOT_PATH.exists():
        raise SystemExit(f"Few-Shot-Vorlage nicht gefunden: {FEW_SHOT_PATH}")

    kqr = KQR(
        id="ecf",
        name="e-CF 3.0",
        namespace_uri="http://hr-qde.org/harmonised/ecf/",
        source_format="pdf",
    )
    few_shot = FEW_SHOT_PATH.read_text(encoding="utf-8")

    print(f"Formalisiere {args.pdf.name} ({kqr.name}) ...")
    draft = formalize_from_pdf(kqr, args.pdf, few_shot)
    print(f"Modell: {draft.model} (temperature={draft.temperature}, max_tokens={draft.max_tokens})")
    print(f"Dauer: {draft.duration_seconds:.1f}s")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(draft.draft_ttl, encoding="utf-8")
    print(f"Entwurf geschrieben: {args.output}")

    prompt_path = args.output.with_suffix(".prompt.txt")
    prompt_path.write_text(draft.prompt, encoding="utf-8")
    print(f"Prompt geschrieben: {prompt_path}")

    errors = validate_formalization(draft.draft_ttl, kqr)

    n_concepts = 0
    try:
        graph = Graph()
        graph.parse(data=draft.draft_ttl, format="turtle")
        n_concepts = len(list(graph.subjects(RDF.type, SKOS.Concept)))
    except Exception:
        pass  # Turtle nicht parsebar -- Fehler steht bereits in errors[0]

    run_log = {
        "tool_version": TOOL_VERSION,
        "kqr_id": kqr.id,
        "kqr_name": kqr.name,
        "source_pdf": str(args.pdf),
        "source_pdf_sha256": _sha256(args.pdf),
        "few_shot_path": str(FEW_SHOT_PATH),
        "model": draft.model,
        "temperature": draft.temperature,
        "max_tokens": draft.max_tokens,
        "started_at": draft.started_at.isoformat(),
        "finished_at": draft.finished_at.isoformat(),
        "duration_seconds": draft.duration_seconds,
        "output_ttl": str(args.output),
        "prompt_file": str(prompt_path),
        "n_concepts": n_concepts,
        "n_validation_errors": len(errors),
        "validation_errors": errors,
    }
    run_log_path = args.output.with_suffix(".run.json")
    run_log_path.write_text(json.dumps(run_log, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Lauf-Protokoll geschrieben: {run_log_path}")

    print(f"\nSummary: Entwurf erstellt mit {n_concepts} Konzepten, {len(errors)} Validierungsfehler")

    if errors:
        print("\nValidierungsfehler -- manuelle Nachbesserung noetig (VH1.3):")
        for err in errors:
            print(f"  - {err}")
        print(
            f"\nBitte {args.output} manuell bearbeiten und anschliessend erneut mit "
            f"validate_formalization pruefen, bevor der Entwurf importiert wird."
        )
    else:
        print("\nValidierung erfolgreich: alle Pflichtfelder aus Tabelle 3.7 vorhanden.")
        print("Bereit fuer den Import ueber die UI oder POST /kqr/.")


if __name__ == "__main__":
    main()
