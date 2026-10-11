"""
Schritt 4b: Export der harmonisierten Ontologie in standardkonformen Formaten
(Turtle, RDF/XML, JSON-LD) sowie eines Prüfberichts offener manueller
Entscheidungen (vgl. FA5, Funktionsgruppe 5 des Wireframes, Abb. 3.7).
"""

from __future__ import annotations

from pathlib import Path

from rdflib import OWL, RDF, RDFS, SKOS, Graph, Literal, Namespace, URIRef

from app.models.schemas import (
    DisjointConceptDecision,
    DisjointStrategy,
    HarmonisedCluster,
    Mapping,
    MappingJustification,
    ReviewStatus,
)

# ADR-17: Die Harmonisierungsschicht (HarmonisedConcept, HarmonisedCluster,
# derivedFrom, harmonises, integrationStrategy) laeuft unter dem Kuerzel harm:.
# Der Namensraum selbst ist unveraendert; nur das Praefix hat gewechselt.
HARM = Namespace("http://hr-qde.org/harmonised/")
# hrqde: bleibt dem HR-QDE-Skelett vorbehalten (z. B. hrqde:DQR1-DQR8, die
# Zielknoten von DisjointStrategy.ATTACH_TO_SKELETON). Dieser Namensraum wird
# von der Harmonisierung nur referenziert, nie erweitert.
HRQDE_SKELETON = Namespace("http://hr-qde.org/ontology/")

_SERIALIZE_FORMAT = {"turtle": "turtle", "xml": "xml", "json-ld": "json-ld"}

# Sprache der Label-Literale: Alle drei KQR-Quellen (ESCO, e-CF, DQR) liegen
# nach der Formalisierung ausschließlich in englischer Übersetzung vor
# (vgl. scripts/12_dqr_translate_en.py) -- daher "en", nicht "de".
_LABEL_LANG = "en"


def export_ontology(
    mappings: list[Mapping],
    clusters: list[HarmonisedCluster],
    disjoint_decisions: list[DisjointConceptDecision],
    fmt: str,
    output_path: Path,
) -> Path:
    """
    Baut einen rdflib-Graphen aus Mappings + Cluster-DAG + Disjoint-Entscheidungen
    und serialisiert ihn. fmt: "turtle" | "xml" | "json-ld"

    Reihenfolge des Graph-Aufbaus:
    1. Namespace-Präfixe binden (harm, hrqde, skos, owl, rdfs).
    2. Jeden HarmonisedCluster als owl:Class eintragen
       + rdfs:label (Sprache _LABEL_LANG) + optional rdfs:subClassOf
       (aus parent_cluster_uri).
    3. Mitgliedskonzepte als owl:NamedIndividual mit rdf:type -> Cluster-URI.
    4. Mappings als SKOS-Prädikate zwischen Konzept-URIs, inkl.
       skos:prefLabel + rdf:type skos:Concept für Subjekt/Objekt
       (Grundlage für CQ1/CQ2, vgl. eval/E5_cq_evaluation.py). Konjunkte
       Konzepte (Menge K) tragen kein harm:HarmonisedConcept (Tabelle 3.13).
    5. Disjoint-Entscheidungen (FZ3.3) als harm:integrationStrategy je
       Konzept, ebenfalls mit skos:prefLabel + harm:HarmonisedConcept
       (Grundlage für CQ3).
    """
    if fmt not in _SERIALIZE_FORMAT:
        raise ValueError(f"Unbekanntes Exportformat '{fmt}' (erlaubt: {sorted(_SERIALIZE_FORMAT)}).")

    graph = Graph()
    graph.bind("harm", HARM)
    graph.bind("hrqde", HRQDE_SKELETON)
    graph.bind("skos", SKOS)
    graph.bind("owl", OWL)
    graph.bind("rdfs", RDFS)

    for cluster in clusters:
        cluster_uri = URIRef(cluster.cluster_uri)
        graph.add((cluster_uri, RDF.type, OWL.Class))
        graph.add((cluster_uri, RDFS.label, Literal(cluster.label, lang=_LABEL_LANG)))
        if cluster.parent_cluster_uri:
            graph.add((cluster_uri, RDFS.subClassOf, URIRef(cluster.parent_cluster_uri)))

        for member_uri in cluster.member_uris:
            member_ref = URIRef(member_uri)
            graph.add((member_ref, RDF.type, OWL.NamedIndividual))
            graph.add((member_ref, RDF.type, cluster_uri))

    def _add_mapped_concept(concept_id: str, label: str) -> None:
        """Trägt ein konjunktes Konzept (Mitglied der Menge K) als
        skos:Concept in den Graphen ein. Kein harm:HarmonisedConcept —
        dieser Typ ist ausschließlich disjunkten Konzepten vorbehalten
        (vgl. Tabelle 3.13)."""
        concept_ref = URIRef(concept_id)
        graph.add((concept_ref, RDF.type, SKOS.Concept))
        graph.add((concept_ref, SKOS.prefLabel, Literal(label, lang=_LABEL_LANG)))

    def _add_disjoint_concept(concept_id: str, label: str) -> None:
        """Trägt ein disjunktes Konzept (D1/D2, harm:HarmonisedConcept)
        in den Graphen ein. Nur für DisjointConceptDecision-Objekte aufrufen,
        nie für Konzepte aus der konjunkten Menge K (vgl. Tabelle 3.13)."""
        concept_ref = URIRef(concept_id)
        graph.add((concept_ref, RDF.type, HARM.HarmonisedConcept))
        graph.add((concept_ref, SKOS.prefLabel, Literal(label, lang=_LABEL_LANG)))

    # Nur entschiedene Mappings werden materialisiert. Ein Paar mit
    # ReviewStatus.OPEN ist noch kein Bestandteil der Ontologie, ein Paar mit
    # ReviewStatus.DISJUNCT wurde im Review ausdrücklich als "kein Mapping"
    # entschieden -- beides darf nicht als SKOS-Tripel erscheinen.
    #
    # Ein CONJUNCT-Mapping wird ausschließlich als SKOS-Mapping-Tripel
    # (skos:exactMatch / skos:broadMatch / skos:narrowMatch) zwischen den
    # Konzept-URIs geschrieben. Es gibt bewusst keine mapping-typ-abhängige
    # Einhängeregel, die das Nicht-ESCO-Konzept je nach Prädikat als
    # Geschwister-, Eltern- oder Kindknoten in die ESCO-Baumstruktur umhängt:
    # rdfs:subClassOf entsteht nur aus dem Cluster-DAG (oben) und aus
    # DisjointStrategy.ATTACH_TO_SKELETON (unten).
    for mapping in mappings:
        if mapping.review_status != ReviewStatus.CONJUNCT:
            continue
        predicate = _resolve_skos_predicate(mapping.predicate_id)
        graph.add((URIRef(mapping.subject_id), predicate, URIRef(mapping.object_id)))
        _add_mapped_concept(mapping.subject_id, mapping.subject_label)
        _add_mapped_concept(mapping.object_id, mapping.object_label)

    for decision in disjoint_decisions:
        _add_disjoint_concept(decision.concept_id, decision.concept_label)
        graph.add((
            URIRef(decision.concept_id),
            HARM.integrationStrategy,
            Literal(decision.strategy.value),
        ))
        if decision.strategy == DisjointStrategy.ATTACH_TO_SKELETON and decision.anchor_class:
            # Zielknoten liegen im Skelett (hrqde:), nicht in der
            # Harmonisierungsschicht -- anchor_class kann daher als CURIE
            # 'hrqde:DQR5' oder als volle URI ankommen.
            graph.add((
                URIRef(decision.concept_id),
                RDFS.subClassOf,
                _resolve_skeleton_class(decision.anchor_class),
            ))
        if decision.context_loss_note:
            graph.add((
                URIRef(decision.concept_id),
                HARM.contextLossNote,
                Literal(decision.context_loss_note, lang=_LABEL_LANG),
            ))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=str(output_path), format=_SERIALIZE_FORMAT[fmt])
    return output_path


def _resolve_skeleton_class(anchor_class: str) -> URIRef:
    """Löst eine Ankerklasse des HR-QDE-Skeletts auf. Akzeptiert sowohl das
    CURIE-Kurzformat 'hrqde:DQR5' als auch eine bereits vollständige URI."""
    if anchor_class.startswith("hrqde:"):
        return HRQDE_SKELETON[anchor_class.split(":", 1)[1]]
    return URIRef(anchor_class)


def _resolve_skos_predicate(predicate_id: "MappingPredicate | str") -> URIRef:
    """Mapping.predicate_id liegt als MappingPredicate-CURIE vor
    ('skos:exactMatch'); hier auf den vollen SKOS-Namespace aufgelöst.

    predicate_id ist eine str-Subklasse (MappingPredicate), .split greift
    daher direkt auf den CURIE-Wert zu (nicht str(), das bei (str, Enum)
    'MappingPredicate.EXACT_MATCH' liefern würde)."""
    local_name = predicate_id.split(":", 1)[-1]
    return SKOS[local_name]


def export_audit_report(mappings: list[Mapping], unresolved: list[Mapping], output_path: Path) -> Path:
    """
    Erzeugt eine Markdown-Datei mit drei Abschnitten:
    1. Automatische Mappings (Shortcut + LLM) — Anzahl, Konfidenzverteilung.
    2. Manuell bestätigte/korrigierte Mappings (mapping_source == "manual").
    3. Offene UNRESOLVED-Fälle mit subject_label, object_label, Begründung.

    Entspricht dem Accountability-Prinzip (Abschnitt 3.8.3, FA5).
    """
    automatic = [m for m in mappings if m.mapping_source == "algorithmic"]
    manual = [m for m in mappings if m.mapping_source == "manual"]

    lines: list[str] = ["# Prüfbericht", ""]

    lines.append("## 1. Automatische Mappings (Shortcut + LLM)")
    lines.append("")
    lines.append(f"Anzahl: {len(automatic)}")
    lines.append("")
    lines.append("| mapping_justification | Anzahl | Ø Konfidenz |")
    lines.append("|---|---|---|")
    for justification in MappingJustification:
        subset = [m for m in automatic if m.mapping_justification == justification]
        if not subset:
            continue
        avg_confidence = sum(m.mapping_confidence for m in subset) / len(subset)
        lines.append(f"| {justification.value} | {len(subset)} | {avg_confidence:.2f} |")
    lines.append("")

    lines.append("## 2. Manuell bestätigte/korrigierte Mappings")
    lines.append("")
    if not manual:
        lines.append("Keine manuellen Entscheidungen vorhanden.")
    else:
        lines.append("| subject | object | predicate | Autor | Begründung |")
        lines.append("|---|---|---|---|---|")
        for m in manual:
            predicate = m.predicate_id.value if m.predicate_id else "—"
            lines.append(
                f"| {m.subject_label} | {m.object_label} | {predicate} | "
                f"{m.author or '?'} | {m.justification or ''} |"
            )
    lines.append("")

    lines.append("## 3. Offene Fälle ohne LLM-Mehrheitsentscheid")
    lines.append("")
    if not unresolved:
        lines.append("Keine offenen Fälle ohne Mehrheitsentscheid.")
    else:
        # mapping_id steht seit v0.2 mit in der Tabelle: die Fälle sind
        # persistiert und über PUT /mappings/{mapping_id}/review direkt
        # entscheidbar, statt nur im Bericht aufzutauchen.
        lines.append("| mapping_id | subject_label | object_label | Begründung |")
        lines.append("|---|---|---|---|")
        for m in unresolved:
            lines.append(
                f"| {m.mapping_id} | {m.subject_label} | {m.object_label} | "
                f"{m.justification or ''} |"
            )
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
