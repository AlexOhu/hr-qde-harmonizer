"""
Analysiert data/raw/ELM.rdf (European Learning Model, RDF/XML) auf Struktur
und Abdeckung der HRQDE-Pflichtfelder, um zu entscheiden, ob fuer diese
Quelle Direktimport (Fall 3, Tabelle "kqr_formate", analog zu
01_esco_formalize.py) moeglich ist oder ein eigenes Mapping-Skript noetig
wird.

Die ELM-Namespace-URI wird bewusst nicht hartcodiert, sondern aus den
rdf:type-Werten der geladenen Datei abgeleitet (Klassen mit lokalem Namen
"LearningOpportunity" / "LearningAchievementSpecification"), da sie zum
Zeitpunkt dieses Skripts nicht verifiziert vorlag.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rdflib import DCTERMS, RDF, SKOS, Graph, Namespace, URIRef  # noqa: E402
from rdflib.term import Literal  # noqa: E402

SOURCE_PATH = ROOT / "data" / "raw" / "ELM.rdf"


def local_name(uri: URIRef) -> str:
    """Letztes Pfad- bzw. Fragment-Segment einer URI, z. B. "LearningOpportunity"."""
    s = str(uri)
    if "#" in s:
        return s.rsplit("#", 1)[-1]
    return s.rstrip("/").rsplit("/", 1)[-1]


def derive_namespace(uri: URIRef) -> str:
    """Basis-Namespace einer Klassen-URI (alles vor dem letzten Segment aus local_name)."""
    s = str(uri)
    if "#" in s:
        return s.rsplit("#", 1)[0] + "#"
    return s.rstrip("/").rsplit("/", 1)[0] + "/"


def find_type_uri(graph: Graph, wanted_local_name: str) -> URIRef | None:
    """Sucht unter allen rdf:type-Objekten eine Klasse mit gegebenem lokalem Namen."""
    for type_uri in {o for o in graph.objects(None, RDF.type) if isinstance(o, URIRef)}:
        if local_name(type_uri) == wanted_local_name:
            return type_uri
    return None


def describe_instance(graph: Graph, subject: URIRef) -> None:
    print(f"  URI: {subject}")
    labels = list(graph.objects(subject, SKOS.prefLabel)) or list(graph.objects(subject, DCTERMS.title))
    for label in labels:
        lang = f"@{label.language}" if isinstance(label, Literal) and label.language else ""
        print(f"  Label{lang}: {label}")
    print("  Properties:")
    for pred, obj in sorted(graph.predicate_objects(subject), key=lambda po: str(po[0])):
        print(f"    {pred} -> {obj}")


def check_field_coverage(graph: Graph, subjects: set[URIRef]) -> dict[str, float]:
    """Anteil der Subjekte, die je HRQDE-Pflichtfeld mindestens einen Wert besitzen."""
    if not subjects:
        return {}
    checks = {
        "dcterms:source": lambda s: bool(list(graph.objects(s, DCTERMS.source))),
        "skos:prefLabel@en": lambda s: any(
            isinstance(o, Literal) and o.language == "en" for o in graph.objects(s, SKOS.prefLabel)
        ),
        "skos:prefLabel@de": lambda s: any(
            isinstance(o, Literal) and o.language == "de" for o in graph.objects(s, SKOS.prefLabel)
        ),
        "skos:definition": lambda s: bool(list(graph.objects(s, SKOS.definition))),
    }
    return {name: sum(1 for s in subjects if check(s)) / len(subjects) for name, check in checks.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_PATH, help="Pfad zur ELM-RDF/XML-Datei")
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"ELM-Quelldatei nicht gefunden: {args.source}")

    print(f"Lade {args.source} ...")
    graph = Graph()
    graph.parse(args.source, format="xml")

    print(f"\nTriples insgesamt: {len(graph)}")

    concepts = set(graph.subjects(RDF.type, SKOS.Concept))
    print(f"skos:Concept Instanzen: {len(concepts)}")

    lo_type = find_type_uri(graph, "LearningOpportunity")
    las_type = find_type_uri(graph, "LearningAchievementSpecification")
    elm_source_type = lo_type or las_type
    elm = Namespace(derive_namespace(elm_source_type)) if elm_source_type is not None else None
    if elm is not None:
        graph.bind("elm", elm)

    learning_opportunities = set(graph.subjects(RDF.type, elm.LearningOpportunity)) if elm is not None else set()
    achievement_specs = (
        set(graph.subjects(RDF.type, elm.LearningAchievementSpecification)) if elm is not None else set()
    )

    print(
        f"elm:LearningOpportunity Instanzen: {len(learning_opportunities)}"
        + (f" (Namespace: {elm})" if elm is not None else " (elm-Namespace nicht gefunden)")
    )
    print(
        f"elm:LearningAchievementSpecification Instanzen: {len(achievement_specs)}"
        + (f" (Namespace: {elm})" if elm is not None else " (elm-Namespace nicht gefunden)")
    )

    has_source = bool(list(graph.subjects(DCTERMS.source, None)))
    has_pref_label = bool(list(graph.subjects(SKOS.prefLabel, None)))
    has_definition = bool(list(graph.subjects(SKOS.definition, None)))
    print(f"\ndcterms:source irgendwo vorhanden: {has_source}")
    print(f"skos:prefLabel irgendwo vorhanden: {has_pref_label}")
    print(f"skos:definition irgendwo vorhanden: {has_definition}")

    if learning_opportunities:
        print("\nBeispiel elm:LearningOpportunity:")
        describe_instance(graph, sorted(learning_opportunities, key=str)[0])
    else:
        print("\nKein Beispiel fuer elm:LearningOpportunity gefunden.")

    if achievement_specs:
        print("\nBeispiel elm:LearningAchievementSpecification:")
        describe_instance(graph, sorted(achievement_specs, key=str)[0])
    else:
        print("\nKein Beispiel fuer elm:LearningAchievementSpecification gefunden.")

    relevant_subjects = concepts | learning_opportunities | achievement_specs
    coverage = check_field_coverage(graph, relevant_subjects)

    print(
        f"\nFeld-Abdeckung ueber {len(relevant_subjects)} relevante Instanzen "
        "(skos:Concept + elm:LearningOpportunity + elm:LearningAchievementSpecification):"
    )
    for field_name, ratio in coverage.items():
        print(f"  {field_name}: {ratio:.1%}")

    avg_coverage = sum(coverage.values()) / len(coverage) if coverage else 0.0
    print(f"\nDurchschnittliche Pflichtfeld-Abdeckung: {avg_coverage:.1%}")
    if avg_coverage > 0.8:
        print("Empfehlung: Direktimport moeglich")
    else:
        print("Empfehlung: Mapping-Skript erforderlich")


if __name__ == "__main__":
    main()
