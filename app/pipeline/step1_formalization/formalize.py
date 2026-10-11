"""
Schritt 1: Formalisierung eines KQR in ein einheitliches skos:ConceptScheme (Turtle).

Entspricht Abschnitt 3.3 der Arbeit. Drei Ausgangsformat-Klassen werden
unterschieden (Tabelle 3.8):

1. PDF-Quellen (z. B. e-CF): LLM-gestützt in drei Teilschritten
   - Segmentierung: Konzeptgrenzen im Rohtext identifizieren
   - Feldzuordnung: Inhalte auf SKOS-Pflichtfelder abbilden (Tabelle 3.7)
   - Serialisierung: Ausgabe als Turtle im HRQDE-Namensraum
2. XML mit bekanntem Schema (z. B. O*NET): deterministischer Parser/XSLT
3. Bereits RDF/SKOS-konforme Quellen: direkter Import
4. Geringe Konzeptanzahl (z. B. EQF, DQR): manuelle Übertragung, keine
   LLM-Assistenz nötig

WICHTIG: Das LLM-generierte Turtle ist laut Konzeption ein Entwurf,
kein finales Artefakt -- es muss vom Systembetreuer manuell validiert
werden (vollstaendige Automatisierung ist explizit kein Ziel dieser
Arbeit, vgl. VH1.3).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rdflib import DCTERMS, RDF, SKOS, Graph, Namespace

from app.config import settings
from app.models.schemas import KQR, Concept, FormalizationDraft

HRQDE = Namespace("https://hrqde.example.org/ontology#")
HARM = Namespace("http://hr-qde.org/harmonised/")

# Pflichtfelder fuer LLM-generierte Formalisierungen (Tabelle "skos_felder").
_REQUIRED_LITERAL_FIELDS: list[tuple[object, str | None, str]] = [
    (SKOS.prefLabel, "en", "skos:prefLabel@en"),
    (SKOS.prefLabel, "de", "skos:prefLabel@de"),
    (SKOS.definition, None, "skos:definition"),
]
_REQUIRED_URI_FIELDS: list[tuple[object, str]] = [
    (DCTERMS.source, "dcterms:source"),
    (HRQDE.derivedFrom, "hrqde:derivedFrom"),
    (HRQDE.sourceIdentifier, "hrqde:sourceIdentifier"),
]


def _extract_pdf_text(pdf_path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1:]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-len("```")]
    return stripped.strip()


def formalize_from_pdf(kqr: KQR, pdf_path: Path, few_shot_example_ttl: str, max_tokens: int = 8000) -> FormalizationDraft:
    """LLM-gestuetzte Formalisierung eines PDF-KQR (z. B. e-CF) als Turtle-Entwurf."""
    from app.pipeline.step3_classification.llm_provider.factory import get_providers_from_config

    raw_text = _extract_pdf_text(pdf_path)
    prompt = (
        "Du bist ein Ontologie-Formalisierungs-Assistent.\n"
        "Quell-KQR: " + kqr.name + " (id=" + kqr.id + ")\n"
        "Namensraum: " + kqr.namespace_uri + "\n\n"
        "Few-Shot-Vorlage:\n" + few_shot_example_ttl + "\n\n"
        "Quelltext:\n" + raw_text + "\n\n"
        "Gib ausschliesslich Turtle-Code aus, keine Erklaerungen."
    )
    providers = get_providers_from_config(settings)
    provider = providers[0]
    started_at = datetime.utcnow()
    response_text = provider.complete(prompt, max_tokens=max_tokens)
    finished_at = datetime.utcnow()
    return FormalizationDraft(
        draft_ttl=_strip_markdown_fence(response_text),
        prompt=prompt,
        model=provider.model_id,
        temperature=settings.classification_temperature,
        max_tokens=max_tokens,
        started_at=started_at,
        finished_at=finished_at,
    )


def formalize_from_xml(kqr: KQR, xml_path: Path, schema_mapping: dict) -> str:
    """Deterministischer Import eines XML-KQR (Erweiterungspunkt, nicht initial benoetigt)."""
    raise NotImplementedError


def validate_formalization(
    turtle_content: str, kqr: KQR, strict: bool = True, rdf_format: str = "turtle"
) -> list[str]:
    """
    Prueft einen Turtle-Entwurf auf Vollstaendigkeit der Pflichtfelder.

    strict=True  (Standard, LLM-generierte Formalisierungen):
        Prueft alle Felder aus Tabelle 3.7, inklusive HRQDE-Namespace-Properties
        (hrqde:derivedFrom, hrqde:sourceIdentifier), die der Formalisierungs-Prompt
        generiert. Zusaetzlich werden zweisprachige Labels (@en und @de) verlangt.

    strict=False (Direktimport, source_format in {'turtle', 'rdf'}):
        Prueft die Import-Mindestanforderungen: parsierbares RDF, mindestens ein
        skos:Concept, mindestens ein skos:prefLabel je Konzept sowie eine
        widerspruchsfreie SKOS-Hierarchie und Rollenannotation.
        HRQDE-Namespace-Properties und Zweisprachigkeit werden nicht gefordert,
        da manuell erstellte oder bereits SKOS-konforme KQR (EQF, DQR) diese
        nicht enthalten. Die Unterscheidung folgt dem Direktimport-Pfad aus
        Tabelle 3.8 (Ausgangsformat-Klassen).

    Gibt eine Liste von Validierungsfehlern zurueck (leer = valide).
    """
    errors: list[str] = []

    graph = Graph()
    try:
        graph.parse(data=turtle_content, format=rdf_format)
    except Exception as exc:
        format_label = "Turtle" if rdf_format == "turtle" else "RDF/XML"
        return [format_label + " konnte nicht geparst werden: " + str(exc)]

    concept_uris = list(graph.subjects(RDF.type, SKOS.Concept))
    if not concept_uris:
        return ["Kein skos:Concept in der Turtle-Datei fuer KQR '" + kqr.id + "' gefunden."]

    for concept_uri in concept_uris:
        labels = list(graph.objects(concept_uri, SKOS.prefLabel))
        if not labels:
            errors.append(str(concept_uri) + ": fehlendes Pflichtfeld skos:prefLabel")

        if strict:
            for predicate, lang, field_name in _REQUIRED_LITERAL_FIELDS:
                values = list(graph.objects(concept_uri, predicate))
                if lang is None:
                    if not values:
                        errors.append(str(concept_uri) + ": fehlendes Pflichtfeld " + field_name)
                else:
                    if not any(getattr(v, "language", None) == lang for v in values):
                        errors.append(str(concept_uri) + ": fehlendes Pflichtfeld " + field_name)

            for predicate, field_name in _REQUIRED_URI_FIELDS:
                if not list(graph.objects(concept_uri, predicate)):
                    errors.append(str(concept_uri) + ": fehlendes Pflichtfeld " + field_name)

        roles = {
            role
            for role in (HARM.CompetenceConcept, HARM.LevelConcept)
            if (concept_uri, RDF.type, role) in graph
        }
        if len(roles) > 1:
            errors.append(
                str(concept_uri)
                + ": darf nicht zugleich harm:CompetenceConcept und harm:LevelConcept sein"
            )

        for predicate in (SKOS.broader, SKOS.narrower):
            for related_uri in graph.objects(concept_uri, predicate):
                if related_uri == concept_uri:
                    errors.append(str(concept_uri) + ": skos-Hierarchie darf nicht auf sich selbst verweisen")
                elif (related_uri, RDF.type, SKOS.Concept) not in graph:
                    errors.append(
                        str(concept_uri)
                        + ": "
                        + str(predicate)
                        + " verweist auf kein skos:Concept: "
                        + str(related_uri)
                    )

    # Eine SKOS-Hierarchie kann sowohl von unten (broader) als auch von oben
    # (narrower) notiert sein. Beide Schreibweisen werden zu Kind -> Eltern
    # normalisiert, damit Zyklen unabhängig von der Serialisierung auffallen.
    concept_set = set(concept_uris)
    parents: dict[object, set[object]] = {concept_uri: set() for concept_uri in concept_uris}
    for concept_uri in concept_uris:
        for parent_uri in graph.objects(concept_uri, SKOS.broader):
            if parent_uri in concept_set:
                parents[concept_uri].add(parent_uri)
        for child_uri in graph.objects(concept_uri, SKOS.narrower):
            if child_uri in concept_set:
                parents[child_uri].add(concept_uri)

    visited: set[object] = set()
    active: set[object] = set()

    def visit(concept_uri: object) -> bool:
        if concept_uri in active:
            return True
        if concept_uri in visited:
            return False
        active.add(concept_uri)
        has_cycle = any(visit(parent_uri) for parent_uri in parents[concept_uri])
        active.remove(concept_uri)
        visited.add(concept_uri)
        return has_cycle

    if any(visit(concept_uri) for concept_uri in concept_uris):
        errors.append("Die SKOS-Hierarchie enthält einen Zyklus.")

    return errors


def parse_concepts(turtle_content: str, kqr_id: str) -> list[Concept]:
    """Laedt Concept-Objekte aus validiertem Turtle fuer die weitere Pipeline."""
    graph = Graph()
    graph.parse(data=turtle_content, format="turtle")

    concepts: list[Concept] = []
    for concept_uri in graph.subjects(RDF.type, SKOS.Concept):
        pref_label = _pick_label(graph, concept_uri, SKOS.prefLabel, preferred_lang="en")
        if pref_label is None:
            labels = list(graph.objects(concept_uri, SKOS.prefLabel))
            pref_label = str(labels[0]) if labels else str(concept_uri)

        definition = _pick_label(graph, concept_uri, SKOS.definition, preferred_lang="en")

        concepts.append(
            Concept(
                uri=str(concept_uri),
                kqr_id=kqr_id,
                pref_label=pref_label,
                definition=definition,
                broader=[str(o) for o in graph.objects(concept_uri, SKOS.broader)],
                narrower=[str(o) for o in graph.objects(concept_uri, SKOS.narrower)],
            )
        )
    return concepts


def _pick_label(graph: Graph, subject: object, predicate: object, preferred_lang: str) -> str | None:
    """Waehlt den Literal-Wert in bevorzugter Sprache, sonst den ersten verfuegbaren."""
    values = list(graph.objects(subject, predicate))
    if not values:
        return None
    for value in values:
        if getattr(value, "language", None) == preferred_lang:
            return str(value)
    return str(values[0])
