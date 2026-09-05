"""
Formalisiert den DQR (Ergebnis von Schritt 1, Tabelle "kqr_formate" Fall 4:
geringe Konzeptanzahl -- manuelle Uebertragung, keine LLM-Assistenz noetig).

Die acht Rohdateien data/raw/dqr/DQR_Niveau_1..8.ttl enthalten bereits
gueltiges SKOS (skos:Concept, prefLabel@de, definition@de, broader/narrower)
je Niveau, aber noch keine der drei HRQDE-Pflichtfelder aus Tabelle 3.7.
Dieses Skript fuehrt alle acht Dateien zu einem gemeinsamen Graphen zusammen
(ein DQR-KQR, keine acht) und ergaenzt je skos:Concept NUR:

  - dcterms:source        Literal "Deutscher Qualifikationsrahmen 2013"
                           (nur falls noch nicht vorhanden -- die acht
                           Hauptniveau-Konzepte tragen bereits eine
                           abweichende Provenance-Angabe und bleiben
                           unveraendert)
  - hrqde:derivedFrom      Literal "dqr"
  - hrqde:sourceIdentifier Literal, letztes Pfadsegment der Konzept-URI
                           (z.B. "Level1", "L1_Knowledge")

skos:prefLabel@de und skos:definition@de werden nirgends angefasst.

Fuer die acht Hauptniveaus (dqr:Level1 .. dqr:Level8) fehlt zusaetzlich
skos:prefLabel@en -- im Rohmaterial existiert dafuer nur skos:altLabel@en.
Die englische Bezeichnung wird NICHT als separat gepflegte Konstantenliste
hinterlegt, sondern aus dem je Niveau bereits vorhandenen
dqr:mapsToEQF/skos:exactMatch-Ziel abgeleitet (z.B. eqf:Level3 ->
"EQF Level 3"). Die uebrigen (Unter-)Konzepte haben kein EQF-Mapping und
bleiben daher ohne skos:prefLabel@en -- das ist erwartet, siehe unten.

Ergebnis ist laut VH1.3 kein automatisch validiertes Artefakt:
validate_formalization prueft die Pflichtfelder aus Tabelle 3.7 und wird
fuer die Unterkonzepte ohne skos:prefLabel@en Fehler melden. Das ist hier
kein Skriptfehler, sondern der erwartete manuelle Pruefschritt.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rdflib import DCTERMS, RDF, SKOS, Graph, Literal, Namespace, URIRef  # noqa: E402
from tqdm import tqdm  # noqa: E402

from app.models.schemas import KQR  # noqa: E402
from app.pipeline.step1_formalization.formalize import validate_formalization  # noqa: E402

INPUT_DIR = ROOT / "data" / "raw" / "dqr"
OUTPUT_PATH = ROOT / "data" / "formalized" / "dqr.ttl"

HRQDE = Namespace("https://hrqde.example.org/ontology#")
DQR = Namespace("http://data.bmbf.de/dqr/")
SOURCE_LABEL = "Deutscher Qualifikationsrahmen 2013"

_EQF_LEVEL_RE = re.compile(r"Level(\d+)$")


def _local_segment(uri: object) -> str:
    return str(uri).rstrip("/").rsplit("/", 1)[-1]


def _eqf_en_label(graph: Graph, subject: URIRef) -> str | None:
    """Leitet 'EQF Level N' aus dem vorhandenen dqr:mapsToEQF/skos:exactMatch-Ziel ab."""
    targets = list(graph.objects(subject, DQR.mapsToEQF)) + list(graph.objects(subject, SKOS.exactMatch))
    for target in targets:
        match = _EQF_LEVEL_RE.search(_local_segment(target))
        if match:
            return f"EQF Level {match.group(1)}"
    return None


def augment(graph: Graph) -> int:
    """Ergaenzt die drei HRQDE-Pflichtfelder je skos:Concept. Gibt die Anzahl bearbeiteter Konzepte zurueck."""
    concepts = list(graph.subjects(RDF.type, SKOS.Concept))
    for subject in tqdm(concepts, desc="Augmentiere DQR-Konzepte", unit="Konzept"):
        if not isinstance(subject, URIRef):
            continue

        if not list(graph.objects(subject, DCTERMS.source)):
            graph.add((subject, DCTERMS.source, Literal(SOURCE_LABEL)))

        graph.add((subject, HRQDE.derivedFrom, Literal("dqr")))
        graph.add((subject, HRQDE.sourceIdentifier, Literal(_local_segment(subject))))

        has_pref_en = any(getattr(label, "language", None) == "en" for label in graph.objects(subject, SKOS.prefLabel))
        if not has_pref_en:
            en_label = _eqf_en_label(graph, subject)
            if en_label is not None:
                graph.add((subject, SKOS.prefLabel, Literal(en_label, lang="en")))

    return len(concepts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR, help="Verzeichnis mit DQR_Niveau_*.ttl")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Zielpfad fuer das formalisierte Turtle")
    args = parser.parse_args()

    ttl_files = sorted(args.input_dir.glob("*.ttl"))
    if not ttl_files:
        raise SystemExit(f"Keine .ttl-Dateien gefunden in {args.input_dir}")

    graph = Graph()
    for path in ttl_files:
        print(f"Lade {path} ...")
        graph.parse(path, format="turtle")
    graph.bind("dcterms", DCTERMS)
    graph.bind("hrqde", HRQDE)

    n_concepts = augment(graph)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(graph.serialize(format="turtle"), encoding="utf-8")
    print(f"Geschrieben: {args.output}")

    kqr = KQR(
        id="dqr",
        name="Deutscher Qualifikationsrahmen 2013",
        namespace_uri="http://data.bmbf.de/dqr/",
        source_format="turtle",
    )
    errors = validate_formalization(graph.serialize(format="turtle"), kqr)

    print(f"\n{len(ttl_files)} Dateien, {n_concepts} Konzepte verarbeitet, {len(errors)} Validierungsfehler gefunden")
    if errors:
        print("(Fehler bei Unterkonzepten ohne skos:prefLabel@en sind erwartet, siehe Docstring)")
        for err in errors[:20]:
            print(f"  - {err}")
        if len(errors) > 20:
            print(f"  ... ({len(errors) - 20} weitere)")
    else:
        print("Validierung erfolgreich: alle Pflichtfelder aus Tabelle 3.7 vorhanden.")


if __name__ == "__main__":
    main()
