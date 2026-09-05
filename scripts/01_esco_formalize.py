"""
Formalisiert den ICT-gefilterten ESCO-Ausschnitt (Ergebnis von
00_esco_filter_ict.py, data/raw/esco-v1.2.1-ict-filtered.ttl) fuer den
Direktimport-Pfad (Tabelle "kqr_formate", Fall 3: bereits RDF/SKOS-
konforme Quelle).

Die Quelldatei enthaelt bereits gueltiges SKOS (skos:Concept, prefLabel,
definition, broader/narrower) fuer Skills, Occupations und Skill-Groups,
aber noch keine der drei HRQDE-Pflichtfelder aus Tabelle 3.7. Dieses
Skript ergaenzt sie je Konzept:

  - dcterms:source        Literal "ESCO v1.2.1" (nur falls noch nicht
                           vorhanden -- die Quelle koennte bereits eine
                           abweichende Provenance-Angabe tragen)
  - hrqde:derivedFrom      Literal "esco"
  - hrqde:sourceIdentifier Literal, letztes Pfadsegment der Konzept-URI
                           (z.B. "sw-development")

Anders als 00_esco_filter_ict.py laedt dieses Skript die (deutlich
kleinere) gefilterte Datei komplett per rdflib -- kein Streaming noetig.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rdflib import DCTERMS, RDF, SKOS, Graph, Literal, Namespace, URIRef  # noqa: E402
from tqdm import tqdm  # noqa: E402

from app.models.schemas import KQR  # noqa: E402
from app.pipeline.step1_formalization.formalize import validate_formalization  # noqa: E402

SOURCE_PATH = ROOT / "data" / "raw" / "esco-v1.2.1-ict-filtered.ttl"
OUTPUT_PATH = ROOT / "data" / "formalized" / "esco.ttl"

HRQDE = Namespace("https://hrqde.example.org/ontology#")
SOURCE_LABEL = "ESCO v1.2.1"


def augment(graph: Graph) -> int:
    """Ergaenzt die drei HRQDE-Pflichtfelder je skos:Concept. Gibt die Anzahl bearbeiteter Konzepte zurueck."""
    concepts = list(graph.subjects(RDF.type, SKOS.Concept))
    for subject in tqdm(concepts, desc="Formalisiere ESCO-Konzepte", unit="Konzept"):
        if not isinstance(subject, URIRef):
            continue

        if not list(graph.objects(subject, DCTERMS.source)):
            graph.add((subject, DCTERMS.source, Literal(SOURCE_LABEL)))

        graph.add((subject, HRQDE.derivedFrom, Literal("esco")))

        source_identifier = str(subject).rstrip("/").rsplit("/", 1)[-1]
        graph.add((subject, HRQDE.sourceIdentifier, Literal(source_identifier)))

    return len(concepts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_PATH, help="Pfad zur ICT-gefilterten ESCO-Datei")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Zielpfad fuer das formalisierte Turtle")
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"ESCO-Quelldatei nicht gefunden: {args.source} (erst 00_esco_filter_ict.py ausfuehren)")

    print(f"Lade {args.source} ...")
    graph = Graph()
    graph.parse(args.source, format="turtle")
    graph.bind("dcterms", DCTERMS)
    graph.bind("hrqde", HRQDE)

    n_concepts = augment(graph)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(graph.serialize(format="turtle"), encoding="utf-8")
    print(f"Geschrieben: {args.output}")

    kqr = KQR(
        id="esco",
        name="ESCO v1.2.1 (ICT-Ausschnitt)",
        namespace_uri="http://data.europa.eu/esco/",
        source_format="turtle",
        is_hub=True,
    )
    errors = validate_formalization(graph.serialize(format="turtle"), kqr)

    print(f"\n{n_concepts} Konzepte verarbeitet, {len(errors)} Validierungsfehler gefunden")
    if errors:
        for err in errors[:20]:
            print(f"  - {err}")
        if len(errors) > 20:
            print(f"  ... ({len(errors) - 20} weitere)")


if __name__ == "__main__":
    main()
