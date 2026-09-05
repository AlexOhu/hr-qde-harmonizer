"""
Analysiert die validate_formalization()-Fehler des e-CF-Formalisierungs-
Entwurfs (data/formalized/ecf_draft.ttl, erzeugt von
scripts/03_ecf_formalize.py) im Detail: statt nur der Fehleranzahl aus dem
Lauf-Protokoll zeigt dieses Skript, welches Pflichtfeld (Tabelle 3.7) bei
welcher Konzept-URI konkret fehlt -- als Arbeitsgrundlage fuer die manuelle
Nachbesserung des Entwurfs (VH1.3).

Schreibt das Ergebnis nach data/analysis/ecf_errors.txt:
  - gruppiert nach Fehlertyp (z. B. "fehlendes Pflichtfeld skos:prefLabel@en")
  - gruppiert nach Konzept-URI (welche Felder fehlen bei diesem Konzept)
  - Summary: "X Konzepte ok, Y Konzepte mit Fehlern (Z Fehler gesamt)"

    python scripts/11_analyze_ecf_errors.py [pfad/zur/datei.ttl]
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rdflib import RDF, SKOS, Graph  # noqa: E402

from app.models.schemas import KQR  # noqa: E402
from app.pipeline.step1_formalization.formalize import validate_formalization  # noqa: E402

DEFAULT_TTL = ROOT / "data" / "formalized" / "ecf_draft.ttl"
OUTPUT_PATH = ROOT / "data" / "analysis" / "ecf_errors.txt"

# Muss zum KQR-Objekt aus scripts/03_ecf_formalize.py passen -- validate_formalization
# nutzt kqr nur fuer Fehlermeldungen ("Kein skos:Concept ... fuer KQR '{kqr.id}' gefunden"),
# nicht fuer die Feldpruefung selbst.
ECF_KQR = KQR(
    id="ecf",
    name="e-CF 3.0",
    namespace_uri="http://hr-qde.org/harmonised/ecf/",
    source_format="pdf",
)

# Matched die von validate_formalization erzeugten Pro-Konzept-Fehler
# ("{concept_uri}: fehlendes Pflichtfeld {field_name}"). Globale Fehler
# (Parse-Fehler, kein skos:Concept gefunden) passen nicht auf dieses Muster
# und werden separat behandelt.
_FIELD_ERROR_RE = re.compile(r"^(?P<uri>.+?): fehlendes Pflichtfeld (?P<field>.+)$")


def parse_errors(errors: list[str]) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str]]:
    """Gruppiert Pro-Konzept-Fehler nach Fehlertyp und nach Konzept-URI.

    Rueckgabe: (by_field_type, by_concept, unparsed_global_errors)
    """
    by_field_type: dict[str, list[str]] = defaultdict(list)
    by_concept: dict[str, list[str]] = defaultdict(list)
    unparsed: list[str] = []

    for error in errors:
        match = _FIELD_ERROR_RE.match(error)
        if match is None:
            unparsed.append(error)
            continue
        uri = match.group("uri")
        field = match.group("field")
        by_field_type[field].append(uri)
        by_concept[uri].append(field)

    return by_field_type, by_concept, unparsed


def main() -> None:
    ttl_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TTL
    if not ttl_path.exists():
        raise SystemExit(f"Fehler: {ttl_path} nicht gefunden.")

    print(f"Lade {ttl_path} ...")
    turtle_content = ttl_path.read_text(encoding="utf-8")

    errors = validate_formalization(turtle_content, ECF_KQR)
    by_field_type, by_concept, unparsed = parse_errors(errors)

    n_concepts_total = 0
    try:
        graph = Graph()
        graph.parse(data=turtle_content, format="turtle")
        n_concepts_total = len(list(graph.subjects(RDF.type, SKOS.Concept)))
    except Exception:
        pass  # Parse-Fehler steht bereits als globaler Fehler in unparsed

    n_concepts_with_errors = len(by_concept)
    n_concepts_ok = max(n_concepts_total - n_concepts_with_errors, 0)
    n_errors_total = len(errors)

    summary = (
        f"{n_concepts_total} Konzepte gesamt, {n_concepts_ok} ok, "
        f"{n_concepts_with_errors} mit Fehlern"
    )

    print(f"\nFehlersummary: {summary}")

    print("\nNach Fehlertyp:")
    if not by_field_type:
        print("  keine Feld-Fehler.")
    else:
        for field, uris in sorted(by_field_type.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            print(f"  {field}: {len(uris)}")

    print("\nBeispiele (erste 5 Fehler):")
    for error in errors[:5]:
        print(f"  - {error}")
    if not errors:
        print("  keine Fehler.")

    lines: list[str] = []
    lines.append(f"Analyse: {ttl_path}")
    lines.append(f"Konzepte gesamt (skos:Concept): {n_concepts_total}")
    lines.append("")

    if unparsed:
        lines.append("Globale Fehler (nicht Konzept-spezifisch):")
        for err in unparsed:
            lines.append(f"  - {err}")
        lines.append("")

    lines.append("Nach Fehlertyp gruppiert:")
    if not by_field_type:
        lines.append("  keine Feld-Fehler.")
    else:
        for field, uris in sorted(by_field_type.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            lines.append(f"  {field}  ({len(uris)} Konzept(e))")
            for uri in uris:
                lines.append(f"    - {uri}")
    lines.append("")

    lines.append("Nach Konzept gruppiert:")
    if not by_concept:
        lines.append("  keine Konzepte mit fehlenden Pflichtfeldern.")
    else:
        for uri, fields in sorted(by_concept.items()):
            lines.append(f"  {uri}")
            for field in fields:
                lines.append(f"    - fehlt: {field}")
    lines.append("")
    lines.append(f"Fehlersummary: {summary} ({n_errors_total} Fehler gesamt)")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nErgebnis geschrieben: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
