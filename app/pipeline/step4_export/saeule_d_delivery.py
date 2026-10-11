"""
Schritt 4c: Erzeugung der drei Lieferartefakte fuer Saeule D.

Die Lieferung besteht aus drei getrennten Dateien:

  1. ``oberhuber-harmonised-ontology-v{V}.ttl``
     Die formalisierten Nicht-ESCO-Konzepte mit Provenienz und die Konzepte
     ohne Entsprechung (``harm:HarmonisedConcept`` + Integrationsstrategie).
     KEINE ESCO-Knoten, KEINE Mappings, KEINE selbst gepraegten Niveau-Knoten.

  2. ``oberhuber-mappings-v{V}.ttl``
     Ein ``sssom:MappingSet`` mit ``harm:HubMapping``-Records (e-CF <-> ESCO-
     Skill), e-CF-Dimension-3-zu-DQR-``harm:LevelMapping``-Records und acht
     DQR<->EQF-``harm:LevelMapping``-Records. Alle Slots
     folgen SSSOM: ``sssom:predicate_id`` als IRI, ``sssom:mapping_confidence``
     als ``xsd:decimal``.

  3. ``oberhuber-integration-strategy-v{V}.md``
     Strategie je disjunktem Konzept und das Begleitprotokoll.

Validiert wird gegen die kanonischen Bezugsdokumente ``hrqde-shape-
harmonisation.ttl`` und ``hrqde-harmonisation-schema.ttl`` (Adrian Vogler,
v0.3.1). Ziel: 0 Violations.

ADR-23 ``harm:EQF{n}``/``harm:DQR{n}`` werden nicht gepraegt; die
       LevelMappings referenzieren ``hrqde:DQR{n}`` und die
       qf-eu-level-Autoritaets-URI direkt.
ADR-24 Drei getrennte Lieferartefakte statt einer kombinierten Datei.
ADR-26 ``harm:HubMapping``/``harm:OccupationMapping`` aus dem gelieferten
       Schema; ``sssom:mapping_confidence`` als ``xsd:decimal``,
       ``predicate_id`` als IRI.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from rdflib import DCTERMS, OWL, RDF, RDFS, SKOS, XSD, Graph, Literal, Namespace, URIRef

from app.models.schemas import (
    DisjointConceptDecision,
    DisjointStrategy,
    LevelMapping,
    Mapping,
    MappingJustification,
    ReviewStatus,
)
from app.pipeline.step2_embedding_prefilter.prefilter import (
    detect_container_concepts,
    is_occupation_uri,
)

HARM = Namespace("http://hr-qde.org/harmonised/")
HARM_ECF = Namespace("http://hr-qde.org/harmonised/source/ecf/")
HRQDE_SKELETON = Namespace("http://hr-qde.org/ontology/")
SEMAPV = Namespace("https://w3id.org/semapv/vocab/")
SSSOM = Namespace("https://w3id.org/sssom/")
QF_EU_LEVEL = "http://data.europa.eu/snb/qf-eu-level/"

# URI-Muster: harm:{rahmen}/{kennung}-Konzepte werden im
# Lieferartefakt unter harm:source/{rahmen}/{kennung} serialisiert. Nur die
# Satelliten-Rahmen selbst (Quellkonzepte); KQR-Entitaeten, Mapping- und
# Cluster-Individuen (kqr_ecf, mapping/..., levelmapping/..., mappingset/...)
# bleiben unveraendert. Die interne Pipeline-Repraesentation (mappings.json,
# classification_results.json, ecf_graph) bleibt bei harm:{rahmen}/{kennung};
# umgeschrieben wird ausschliesslich beim Serialisieren der Lieferartefakte.
_DELIVERY_SOURCE_RAHMEN = {"ecf", "dqr", "eqf"}


def _delivery_uri(original: URIRef | str) -> URIRef:
    text = str(original)
    prefix = str(HARM)
    if not text.startswith(prefix):
        return URIRef(text)
    rest = text[len(prefix):]
    if rest.startswith("source/") or "/" not in rest:
        return URIRef(text)
    rahmen, _, kennung = rest.partition("/")
    if rahmen not in _DELIVERY_SOURCE_RAHMEN:
        return URIRef(text)
    return HARM[f"source/{rahmen}/{kennung}"]


ONTOLOGY_URI = URIRef("http://hr-qde.org/harmonised/oberhuber-harmonised-ontology")

# SSSOM-Praedikate, die im Konjunkt-Zweig zulaessig sind.
_K_PREDICATES = {"skos:exactMatch", "skos:closeMatch", "skos:broadMatch", "skos:narrowMatch"}

# e-CF 3.0 (CWA 16234-1:2014): e-CF-Proficiency-Stufe -> EQF-Niveau(s). Die Zuordnung wird
# als regulaere harm:LevelMapping-Records fuer die e-CF-Levelknoten serialisiert.
ECF_EQF_CROSSWALK: dict[str, list[int]] = {
    "e-1": [3],
    "e-2": [4],
    "e-3": [5, 6],
    "e-4": [7],
    "e-5": [8],
}

# ADR-23: DQR<->EQF, normativ aus dem Deutschen EQR-Zuordnungsbericht (2013).
# Subjekt = Skelett-Niveauknoten, Objekt = EQF-Autoritaets-URI. Kein e-CF-Bezug.
LEVEL_MAPPING_TOOL = "Deutscher EQR-Zuordnungsbericht 2013"

# KQR-Individuen des gelieferten Schemas (Kleinschreibung, ``a harm:KQR``).
_KQR_ENTITIES: dict[str, tuple[str, str]] = {
    "esco": ("kqr_esco", "ESCO v1.2 (Informatik-Korridor)"),
    "ecf": ("kqr_ecf", "European e-Competence Framework 3.0"),
    "eqf": ("kqr_eqf", "European Qualifications Framework (2017)"),
    "dqr": ("kqr_dqr", "Deutscher Qualifikationsrahmen (2013)"),
}


# ---------------------------------------------------------------------------
# Hilfsfunktionen (Label-/Definitionszugriff, e-CF-Struktur)
# ---------------------------------------------------------------------------

def _pref_label(graph: Graph, uri: URIRef, lang: str) -> str | None:
    for value in graph.objects(uri, SKOS.prefLabel):
        if getattr(value, "language", None) == lang:
            return str(value)
    return None


def _any_label(graph: Graph, uri: URIRef) -> str:
    labels = list(graph.objects(uri, SKOS.prefLabel))
    return str(labels[0]) if labels else str(uri).rsplit("/", 1)[-1]


def _definition(graph: Graph, uri: URIRef, lang: str) -> str | None:
    values = list(graph.objects(uri, SKOS.definition))
    for value in values:
        if getattr(value, "language", None) == lang:
            return str(value)
    return str(values[0]) if values else None


_SRC_ID = Namespace("https://hrqde.example.org/ontology#")  # Platzhalter-NS der Formalisierung


def _source_identifier(graph: Graph, uri: URIRef) -> str | None:
    """Liest die interne oder kanonische sourceIdentifier-Property."""
    ident = next(graph.objects(uri, _SRC_ID.sourceIdentifier), None)
    if ident is None:
        ident = next(graph.objects(uri, HARM.sourceIdentifier), None)
    return str(ident) if ident is not None else None


def _ecf_sort_ident(ecf_graph: Graph, comp_id: str) -> str:
    ident = _source_identifier(ecf_graph, URIRef(comp_id))
    if ident is None:
        return comp_id
    if "." in ident:
        area, _, num = ident.partition(".")
        if num.isdigit():
            return f"{area}.{int(num):02d}"
    return ident


def _ecf_level_concepts(ecf_graph: Graph) -> list[URIRef]:
    return sorted(
        (URIRef(str(c)) for c in ecf_graph.subjects(RDF.type, HARM.LevelConcept)),
        key=str,
    )


def _ecf_competence_concepts(ecf_graph: Graph) -> list[URIRef]:
    return sorted(
        (URIRef(str(c)) for c in ecf_graph.subjects(RDF.type, HARM.CompetenceConcept)),
        key=str,
    )


def _ecf_leaf_concepts(ecf_graph: Graph, excluded: list[URIRef] | None = None) -> list[URIRef]:
    containers, _ = detect_container_concepts(ecf_graph)
    excluded_ids = {str(c) for c in (excluded or [])}
    leaves = [
        URIRef(str(c))
        for c in ecf_graph.subjects(RDF.type, SKOS.Concept)
        if str(c) not in containers and str(c) not in excluded_ids
    ]
    return sorted(leaves, key=str)


def _ecf_area_concepts(ecf_graph: Graph) -> list[URIRef]:
    containers, _ = detect_container_concepts(ecf_graph)
    return sorted((URIRef(c) for c in containers), key=str)


def _same_concept_uri(left: str, right: URIRef | str) -> bool:
    """Vergleicht interne und Liefer-URIs derselben Quellkonzepte."""
    return _delivery_uri(left) == _delivery_uri(right)


# ---------------------------------------------------------------------------
# e-CF-Dimension-3-Crosswalk -> LevelMapping-Records
# ---------------------------------------------------------------------------

def generate_level_mappings_from_ecf(ecf_graph: Graph) -> list[LevelMapping]:
    """Erzeugt die normativen e-CF-Dimension-3-zu-DQR-LevelMappings.

    Die Levelknoten tragen bereits ``harm:eqfCrosswalkTarget`` auf den
    DQR-Anker in ``dqr_1d``. Der Crosswalk ist deshalb kein HubMapping und
    keine narrative Sonderform, sondern ein regulärer LevelMapping-Record.
    """
    rows: list[LevelMapping] = []
    for level_uri in ecf_graph.subjects(RDF.type, HARM.LevelConcept):
        for dqr_uri in ecf_graph.objects(level_uri, HARM.eqfCrosswalkTarget):
            level_label = _pref_label(ecf_graph, URIRef(str(level_uri)), "en") or _any_label(
                ecf_graph, URIRef(str(level_uri))
            )
            rows.append(
                LevelMapping(
                    subject_id=str(level_uri),
                    subject_label=level_label,
                    proficiency_level=_proficiency_from_level_uri(str(level_uri)),
                    object_id=str(dqr_uri),
                    object_label=_any_label(ecf_graph, URIRef(str(dqr_uri))),
                    predicate_id="skos:closeMatch",
                    mapping_confidence=Decimal("1.0"),
                    mapping_justification=MappingJustification.MANUAL_MAPPING_CURATION,
                    mapping_tool="e-CF 3.0 (CWA 16234-1:2014)",
                )
            )
    rows.sort(key=lambda r: (
        _ecf_sort_ident(ecf_graph, r.subject_id), r.proficiency_level or "", r.object_id
    ))
    return rows


def _proficiency_from_level_uri(level_uri: str) -> str | None:
    """Liest ``Niveau{n}`` aus einem e-CF-Dimension-3-URI."""
    marker = ".Niveau"
    if marker not in level_uri:
        return None
    return f"e-{level_uri.rsplit(marker, 1)[-1]}"


def dqr_eqf_level_mappings() -> list[LevelMapping]:
    """Die acht normativen DQR<->EQF-Niveauzuordnungen (ADR-23). Subjekt ist
    der Skelett-Knoten ``hrqde:DQR{n}``, Objekt die EQF-Autoritaets-URI."""
    return [
        LevelMapping(
            subject_id=f"{HRQDE_SKELETON}DQR{n}",
            subject_label=f"DQR-Niveau {n}",
            proficiency_level=None,
            object_id=f"{QF_EU_LEVEL}{n}",
            object_label=f"EQF Level {n}",
            predicate_id="skos:exactMatch",
            mapping_confidence=Decimal("1.0"),
            mapping_justification=MappingJustification.MANUAL_MAPPING_CURATION,
            mapping_tool=LEVEL_MAPPING_TOOL,
        )
        for n in range(1, 9)
    ]


# ---------------------------------------------------------------------------
# Gemeinsame Graph-Bausteine
# ---------------------------------------------------------------------------

def _bind(graph: Graph) -> None:
    graph.bind("harm", HARM)
    graph.bind("harm-ecf", HARM_ECF)  # Unterpfad, eigener Praefix
    graph.bind("hrqde", HRQDE_SKELETON)  # Skelett-NS, nur referenziert
    graph.bind("skos", SKOS)
    graph.bind("owl", OWL)
    graph.bind("rdfs", RDFS)
    graph.bind("dcterms", DCTERMS)
    graph.bind("semapv", SEMAPV)
    graph.bind("sssom", SSSOM)
    graph.bind("xsd", XSD)


def _ontology_header(graph: Graph, version: str, title: str) -> None:
    graph.add((ONTOLOGY_URI, RDF.type, OWL.Ontology))
    graph.add((ONTOLOGY_URI, DCTERMS.created, Literal(date.today().isoformat(), datatype=XSD.date)))
    graph.add((ONTOLOGY_URI, OWL.versionInfo, Literal(version)))
    graph.add((ONTOLOGY_URI, DCTERMS.title, Literal(title, lang="de")))
    for src in ("ESCO v1.2 (Informatik-Korridor)", "e-CF 3.0 (CWA 16234-1:2014)",
                "EQF 2017 (OJ C 189)", "DQR 2013"):
        graph.add((ONTOLOGY_URI, DCTERMS.source, Literal(src)))


def _semapv_iri(justification: MappingJustification) -> URIRef:
    # SEMAPV enumerates no LLMBasedMatching term. The internal provider
    # provenance is therefore exported as the closest standard term.
    local = justification.value.split(":", 1)[1]
    if local == "LLMBasedMatching":
        local = "CompositeMatching"
    return SEMAPV[local]


def _decimal(value: object) -> Literal:
    return Literal(Decimal(str(round(float(value), 4))), datatype=XSD.decimal)


def _target(output_path: Path, default_name: str) -> Path:
    return output_path if output_path.suffix else output_path / default_name


# ---------------------------------------------------------------------------
# Artefakt 1: oberhuber-harmonised-ontology-v{V}.ttl
# ---------------------------------------------------------------------------

def write_ontology(
    output_path: Path,
    ecf_graph: Graph,
    k_mappings: list[Mapping],
    disjoint_decisions: list[DisjointConceptDecision] | None,
    version: str = "0.2",
) -> dict:
    """Schreibt Artefakt 1. Rueckgabe: Statistik-Dict."""
    disjoint_decisions = disjoint_decisions or []
    target = _target(output_path, f"oberhuber-harmonised-ontology-v{version}.ttl")

    graph = Graph()
    _bind(graph)
    _ontology_header(graph, version, "HR-QDE harmonisierte Basis-Ontologie (Informatik-Korridor)")

    # KQR-Entitaeten -----------------------------------------------------
    for _key, (local, label) in _KQR_ENTITIES.items():
        node = HARM[local]
        graph.add((node, RDF.type, HARM.KQR))
        graph.add((node, RDFS.label, Literal(label, lang="en")))

    ecf_levels = _ecf_level_concepts(ecf_graph)
    ecf_competences = _ecf_competence_concepts(ecf_graph)
    ecf_leaves = _ecf_leaf_concepts(ecf_graph, excluded=ecf_levels)
    ecf_areas = _ecf_area_concepts(ecf_graph)

    # e-CF-Konzepte (Dimension 2) + Provenienz --------------------------
    # Intern (Matching gegen k_mappings/disjoint_decisions) bleibt bei den
    # Original-URIs; nur die geschriebenen Tripel tragen die Liefer-URI
    # (harm:source/ecf/... statt harm:ecf/...).
    for concept in (*ecf_areas, *ecf_competences, *ecf_levels):
        node = _delivery_uri(concept)
        graph.add((node, RDF.type, SKOS.Concept))
        if (concept, RDF.type, HARM.CompetenceConcept) in ecf_graph:
            graph.add((node, RDF.type, HARM.CompetenceConcept))
        if (concept, RDF.type, HARM.LevelConcept) in ecf_graph:
            graph.add((node, RDF.type, HARM.LevelConcept))
        for lang in ("en", "de"):
            lbl = _pref_label(ecf_graph, concept, lang)
            if lbl:
                graph.add((node, SKOS.prefLabel, Literal(lbl, lang=lang)))
        definition = _definition(ecf_graph, concept, "en")
        if definition:
            graph.add((node, SKOS.definition, Literal(definition, lang="en")))
        graph.add((node, HARM.derivedFrom, HARM.kqr_ecf))
        ident = _source_identifier(ecf_graph, concept)
        if ident:
            graph.add((node, HARM.sourceIdentifier, Literal(ident)))
        for parent in ecf_graph.objects(concept, SKOS.broader):
            if URIRef(str(parent)) in set(ecf_areas):
                graph.add((node, SKOS.broader, _delivery_uri(parent)))
        for level in ecf_graph.objects(concept, HARM.hasLevel):
            graph.add((node, HARM.hasLevel, _delivery_uri(level)))

    # Anker-Bestimmung: welche e-CF-Blaetter haben ein CONJUNCT-K-Mapping?
    ecf_leaf_ids = {str(u) for u in ecf_leaves}
    k_conjunct = _conjunct_ecf_esco(k_mappings)
    anchored_ecf = {
        str(u) for u in ecf_leaves
        if any(_same_concept_uri(m.subject_id, u) or _same_concept_uri(m.object_id, u)
               for m in k_conjunct)
    }

    # harm:HarmonisedConcept fuer die disjunkten e-CF-Blaetter ----------
    # Entscheidungen tragen die interne URI (harm:ecf/...), die Blaetter aus
    # ecf_level die Liefer-URI (harm:source/ecf/...). Abgleich daher ueber
    # die normalisierte Liefer-URI, wie bei den K-Mappings (_same_concept_uri).
    decision_by_id = {str(_delivery_uri(d.concept_id)): d for d in disjoint_decisions}
    harmonised_concepts: list[URIRef] = []
    strategy_counts: dict[str, int] = {}
    for leaf in ecf_leaves:
        if str(leaf) in anchored_ecf:
            continue
        harmonised_concepts.append(leaf)
        decision = decision_by_id.get(str(_delivery_uri(leaf)))
        strategy = decision.strategy.value if decision else DisjointStrategy.OWN_CLASS.value
        strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        node = _delivery_uri(leaf)
        graph.add((node, RDF.type, HARM.HarmonisedConcept))
        graph.add((node, HARM.integrationStrategy, Literal(strategy)))
        comment = _harmonised_comment(decision)
        graph.add((node, RDFS.comment, Literal(comment, lang="de")))
        if decision:
            graph.add((node, DCTERMS.creator, Literal(decision.author)))
            created_at = decision.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            else:
                created_at = created_at.astimezone(timezone.utc)
            graph.add((node, DCTERMS.created, Literal(created_at, datatype=XSD.dateTime)))

    target.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=str(target), format="turtle", encoding="utf-8")

    return {
        "artifact": "ontology",
        "path": str(target),
        "triples": len(graph),
        "version": version,
        "kqr_entities": len(_KQR_ENTITIES),
        "ecf_concepts": len(ecf_leaves),
        "ecf_level_concepts": len(ecf_levels),
        "ecf_areas": len(ecf_areas),
        "harmonised_concepts": len(harmonised_concepts),
        "harmonised_by_strategy": strategy_counts,
        # Normalisierte Liefer-URIs, Abgleich gegen disjoint_decisions.
        "harmonised_concept_ids": sorted(str(_delivery_uri(u)) for u in harmonised_concepts),
        "harmonised_decided": sum(
            1 for u in harmonised_concepts if str(_delivery_uri(u)) in decision_by_id
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _harmonised_comment(decision: DisjointConceptDecision | None) -> str:
    """Kommentar fuer harm:HarmonisedConcept.

    Das Schema (v0.3.1) kennt keine eigene Property fuer die Ankerklasse
    einer attach_to_skeleton-Entscheidung, und direkte SKOS-Kanten auf
    ESCO sind in der Lieferung ausgeschlossen (nur reifizierte Mappings).
    Die Ankerklasse wird deshalb im Kommentar mitgefuehrt, damit sie in
    der Lieferung nicht verloren geht."""
    if decision is None:
        return (
            "Kein e-CF-Blatt-Mapping in K nach LLM-Klassifikation und Review; "
            "ohne gespeicherte Integrationsentscheidung als eigenstaendige Klasse "
            "der Harmonisierungsschicht gefuehrt (Rueckfallstrategie des Exports)."
        )
    parts: list[str] = []
    if (decision.justification or "").strip():
        parts.append(decision.justification.strip())
    if (decision.context_loss_note or "").strip():
        parts.append(f"Kontextverlust: {decision.context_loss_note.strip()}")
    if (decision.anchor_class or "").strip():
        parts.append(f"Ankerklasse: {decision.anchor_class.strip()}")
    return " ".join(parts) or "Integrationsentscheidung ohne Begruendung."


# ---------------------------------------------------------------------------
# Artefakt 2: oberhuber-mappings-v{V}.ttl
# ---------------------------------------------------------------------------

def write_mappings(
    output_path: Path,
    k_mappings: list[Mapping],
    ecf_graph: Graph | None = None,
    version: str = "0.2",
) -> dict:
    """Schreibt Artefakt 2 (``sssom:MappingSet`` + Hub-/Level-Mappings)."""
    target = _target(output_path, f"oberhuber-mappings-v{version}.ttl")

    graph = Graph()
    _bind(graph)

    mapping_set = HARM[f"mappingset/oberhuber-v{version}"]
    graph.add((mapping_set, RDF.type, SSSOM.MappingSet))
    graph.add((mapping_set, SSSOM.mapping_set_version, Literal(version)))

    k_conjunct = _conjunct_ecf_esco(k_mappings)
    hub_records: list[URIRef] = []
    occ_records: list[URIRef] = []
    by_predicate: dict[str, int] = {}

    for m in k_conjunct:
        is_occ = is_occupation_uri(m.object_id)
        rec = HARM[f"mapping/{m.mapping_id}"]
        rec_type = HARM.OccupationMapping if is_occ else HARM.HubMapping
        graph.add((rec, RDF.type, rec_type))
        graph.add((rec, SSSOM.subject_id, _delivery_uri(m.subject_id)))
        graph.add((rec, SSSOM.object_id, _delivery_uri(m.object_id)))
        graph.add((rec, SSSOM.predicate_id, SKOS[m.predicate_id.split(":", 1)[-1]]))
        graph.add((rec, SSSOM.mapping_confidence, _decimal(m.mapping_confidence)))
        graph.add((rec, SSSOM.mapping_justification, _semapv_iri(m.mapping_justification)))
        graph.add((rec, SSSOM.mapping_tool, Literal(m.mapping_tool, datatype=XSD.string)))
        graph.add((mapping_set, SSSOM.mappings, rec))
        if is_occ:
            occ_records.append(rec)
            note = (m.context_loss_note or m.justification or "").strip() or (
                "Bezug auf einen ESCO-Beruf statt auf einen Skill; bewusst gesetzt."
            )
            graph.add((rec, HARM.justification, Literal(note, datatype=XSD.string)))
        else:
            hub_records.append(rec)
        key = m.predicate_id.value if m.predicate_id else "none"
        by_predicate[key] = by_predicate.get(key, 0) + 1

    # e-CF-Dimension-3 -> DQR (kanonische Niveaukette) ------------------
    level_records: list[URIRef] = []
    ecf_level_records = generate_level_mappings_from_ecf(ecf_graph) if ecf_graph else []
    for index, lm in enumerate(ecf_level_records, start=1):
        rec = HARM[f"levelmapping/ECF_D3__DQR_{index:03d}"]
        graph.add((rec, RDF.type, HARM.LevelMapping))
        graph.add((rec, SSSOM.subject_id, _delivery_uri(lm.subject_id)))
        graph.add((rec, SSSOM.object_id, _delivery_uri(lm.object_id)))
        graph.add((rec, SSSOM.predicate_id, SKOS[lm.predicate_id.split(":", 1)[-1]]))
        graph.add((rec, SSSOM.mapping_confidence, _decimal(lm.mapping_confidence)))
        graph.add((rec, SSSOM.mapping_justification, _semapv_iri(lm.mapping_justification)))
        graph.add((rec, SSSOM.mapping_tool, Literal(lm.mapping_tool, datatype=XSD.string)))
        graph.add((mapping_set, SSSOM.mappings, rec))
        level_records.append(rec)

    # 8x harm:LevelMapping DQR <-> EQF (ADR-23) -------------------------
    for lm in dqr_eqf_level_mappings():
        n = lm.subject_id.rsplit("DQR", 1)[-1]
        rec = HARM[f"levelmapping/DQR{n}__EQF{n}"]
        graph.add((rec, RDF.type, HARM.LevelMapping))
        graph.add((rec, SSSOM.subject_id, URIRef(lm.subject_id)))
        graph.add((rec, SSSOM.object_id, URIRef(lm.object_id)))
        graph.add((rec, SSSOM.predicate_id, SKOS[lm.predicate_id.split(":", 1)[-1]]))
        graph.add((rec, SSSOM.mapping_confidence, _decimal(lm.mapping_confidence)))
        graph.add((rec, SSSOM.mapping_justification, _semapv_iri(lm.mapping_justification)))
        graph.add((rec, SSSOM.mapping_tool, Literal(lm.mapping_tool, datatype=XSD.string)))
        graph.add((mapping_set, SSSOM.mappings, rec))
        level_records.append(rec)

    target.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=str(target), format="turtle", encoding="utf-8")

    above_threshold = sum(1 for m in k_conjunct if m.mapping_confidence >= 0.67)
    return {
        "artifact": "mappings",
        "path": str(target),
        "triples": len(graph),
        "version": version,
        "hub_mappings": len(hub_records),
        "occupation_mappings": len(occ_records),
        "level_mappings": len(level_records),
        "ecf_level_mappings": len(ecf_level_records),
        "hub_mappings_above_threshold_067": above_threshold,
        "hub_mappings_by_predicate": by_predicate,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _conjunct_ecf_esco(k_mappings: list[Mapping]) -> list[Mapping]:
    """Die im Review als CONJUNCT bestaetigten e-CF<->ESCO-K-Mappings."""
    return [
        m for m in k_mappings
        if m.review_status == ReviewStatus.CONJUNCT
        and m.predicate_id in _K_PREDICATES
        and "ecf" in {m.subject_kqr_id, m.object_kqr_id}
        and any((kid or "").startswith("esco") for kid in (m.subject_kqr_id, m.object_kqr_id))
    ]


# ---------------------------------------------------------------------------
# Artefakt 3: oberhuber-integration-strategy-v{V}.md
# ---------------------------------------------------------------------------

def write_integration_strategy(
    output_path: Path,
    ecf_graph: Graph,
    disjoint_decisions: list[DisjointConceptDecision] | None,
    ontology_stats: dict,
    mapping_stats: dict,
    coverage: dict | None = None,
    limitations: list[str] | None = None,
    version: str = "0.2",
) -> dict:
    """Schreibt Artefakt 3 (Strategie-Doku + CEN-Crosswalk + Begleitprotokoll)."""
    disjoint_decisions = disjoint_decisions or []
    coverage = coverage or {}
    limitations = limitations or []
    target = _target(output_path, f"oberhuber-integration-strategy-v{version}.md")

    lines: list[str] = []
    lines.append(f"# Integrationsstrategie und Begleitprotokoll — Saeule D v{version}")
    lines.append("")
    lines.append(f"Lieferdatum: {date.today().isoformat()}")
    lines.append(f"Pipeline-Version: {mapping_stats.get('version', version)}")
    lines.append("")

    # 1. Begleitprotokoll ---------------------------------------------------
    lines.append("## 1. Begleitprotokoll")
    lines.append("")
    lines.append("### Konzepte je Rahmen")
    lines.append("")
    lines.append("| Rahmen | Konzepte in der Lieferung |")
    lines.append("|---|---|")
    lines.append(f"| e-CF 3.0 (Dimension 2) | {ontology_stats.get('ecf_concepts', 0)} "
                 f"(+ {ontology_stats.get('ecf_areas', 0)} Bereiche) |")
    lines.append(f"| e-CF 3.0 (Dimension 3) | {ontology_stats.get('ecf_level_concepts', 0)} LevelConcepts |")
    lines.append("| DQR 2013 (Niveaus) | 8 (als Skelett-Referenz `hrqde:DQR1`–`DQR8`) |")
    lines.append("| EQF 2017 (Niveaus) | 8 (als Autoritaets-URI `qf-eu-level/1`–`8`) |")
    lines.append("")
    lines.append("### Mappings je Typ")
    lines.append("")
    lines.append("| Typ | Anzahl | Zaehlt zur Coverage |")
    lines.append("|---|---|---|")
    lines.append(f"| `harm:HubMapping` (e-CF ↔ ESCO-Skill) | {mapping_stats.get('hub_mappings', 0)} | ja |")
    lines.append(f"| `harm:LevelMapping` (e-CF Dimension 3 ↔ DQR) | {mapping_stats.get('ecf_level_mappings', 0)} | nein |")
    lines.append(f"| `harm:LevelMapping` (DQR ↔ EQF) | 8 | nein |")
    lines.append(f"| `harm:OccupationMapping` | {mapping_stats.get('occupation_mappings', 0)} | nein |")
    lines.append("")
    if coverage:
        ratio = coverage.get("coverage_ratio")
        ratio_str = f"{ratio:.3f} ({ratio * 100:.1f} %)" if isinstance(ratio, (int, float)) else "—"
        lines.append("### Coverage-Quote")
        lines.append("")
        lines.append(f"- `coverage_resolved` (finalisierte HubMappings): {coverage.get('coverage_resolved', '—')}")
        lines.append(f"- `coverage_total` (K ∪ C_conf inkl. offener Reviews): {coverage.get('coverage_total', '—')}")
        lines.append(f"- `coverage_ratio`: {ratio_str}")
        lines.append(f"- `open_review_count`: {coverage.get('open_review_count', '—')}")
        lines.append("")
    lines.append("### Bekannte Limitationen")
    lines.append("")
    if limitations:
        for item in limitations:
            lines.append(f"- {item}")
    else:
        lines.append("- keine ueber die unten dokumentierten hinaus")
    lines.append("")
    lines.append("### Repraesentation")
    lines.append("")
    lines.append("Mappings liegen ausschliesslich reifiziert als `harm:HubMapping`/"
                 "`harm:LevelMapping` in `oberhuber-mappings-v{V}.ttl` vor. Es gibt "
                 "keine zusaetzliche direkte SKOS-Kante, daher keine Doppelzaehlung.")
    lines.append("")

    # 2. Integrationsstrategie je disjunktem Konzept ----------------------
    lines.append("## 2. Integrationsstrategie je disjunktem Konzept")
    lines.append("")
    by_strategy = ontology_stats.get("harmonised_by_strategy", {})
    lines.append("| Strategie | Anzahl |")
    lines.append("|---|---|")
    for value in ("own_class", "attach_to_skeleton", "map_to_nearest", "out_of_scope"):
        lines.append(f"| `{value}` | {by_strategy.get(value, 0)} |")
    lines.append("")
    # Nur Entscheidungen zu Konzepten, die in dieser Lieferung tatsaechlich
    # als harm:HarmonisedConcept erscheinen (Entscheidungen zu Hub-Konzepten
    # oder zu Konzepten mit K-Mapping wirken nicht auf die Lieferung).
    harmonised_ids = ontology_stats.get("harmonised_concept_ids")
    if harmonised_ids is None:
        relevant = list(disjoint_decisions)
    else:
        wanted = set(harmonised_ids)
        relevant = [d for d in disjoint_decisions if str(_delivery_uri(d.concept_id)) in wanted]
    n_harmonised = ontology_stats.get("harmonised_concepts", 0)
    n_open = max(n_harmonised - len(relevant), 0)
    if relevant:
        lines.append("| Konzept | Strategie | Ankerklasse | Begruendung / Kontextverlust | Autor | Datum |")
        lines.append("|---|---|---|---|---|---|")
        for d in sorted(relevant, key=lambda x: x.concept_id):
            note_parts = [p.strip() for p in (d.justification, d.context_loss_note) if (p or "").strip()]
            note = " / ".join(note_parts).replace("|", "\\|")
            anchor = f"`{d.anchor_class.strip()}`" if (d.anchor_class or "").strip() else "—"
            lines.append(
                f"| `{_delivery_uri(d.concept_id)}` | `{d.strategy.value}` | {anchor} | {note or '—'} "
                f"| {d.author} | {d.created_at.date().isoformat()} |"
            )
        lines.append("")
    if n_open:
        lines.append(f"{n_open} von {n_harmonised} disjunkten Konzepten haben keine gespeicherte "
                     "Integrationsentscheidung und tragen die Rueckfallstrategie `own_class` "
                     "des Exports. Diese ist kein Ergebnis von "
                     "`disjoint_service.suggest_strategy` (siehe Limitationen).")
    elif n_harmonised:
        lines.append(f"Fuer alle {n_harmonised} disjunkten Konzepte liegt eine gespeicherte "
                     "Integrationsentscheidung mit Begruendung und Autor vor.")
    lines.append("")

    # 3. Niveaukette ------------------------------------------------------
    lines.append("## 3. Niveaukette: e-CF Dimension 2 → Dimension 3 → DQR")
    lines.append("")
    lines.append("e-CF-Dimension-2-Kompetenzen sind als `harm:CompetenceConcept` "
                 "typisiert und über `harm:hasLevel` mit ihren "
                 "`harm:LevelConcept`-Beschreibungen verbunden. Jede normative "
                 "Zuordnung eines Dimension-3-Knotens auf einen DQR-Anker wird "
                 "als `harm:LevelMapping` mit `skos:closeMatch` serialisiert. "
                 "Diese Records zählen nicht zur ESCO-Coverage.")
    lines.append("")
    lines.append("| e-CF-LevelConcept | Proficiency | DQR-Anker |")
    lines.append("|---|---|---|")
    for lm in generate_level_mappings_from_ecf(ecf_graph):
        ident = _source_identifier(ecf_graph, URIRef(lm.subject_id)) or lm.subject_id
        dqr_n = lm.object_id.rsplit("/", 1)[-1]
        lines.append(f"| {ident} — {lm.subject_label} | {lm.proficiency_level or '—'} | DQR {dqr_n} |")
    lines.append("")
    lines.append("Provenienz: normative e-CF-3.0-Crosswalk (CWA 16234-1:2014); "
                 "`mapping_justification = semapv:ManualMappingCuration`, "
                 "`mapping_confidence = 1.0`.")
    lines.append("")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")

    return {
        "artifact": "integration_strategy",
        "path": str(target),
        "version": version,
        "disjoint_documented": len(relevant),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Orchestrierung
# ---------------------------------------------------------------------------

def write_delivery(
    output_dir: Path,
    ecf_graph: Graph,
    k_mappings: list[Mapping],
    disjoint_decisions: list[DisjointConceptDecision] | None = None,
    coverage: dict | None = None,
    limitations: list[str] | None = None,
    version: str = "0.2",
) -> dict:
    """Erzeugt alle drei Lieferartefakte in ``output_dir``."""
    disjoint_decisions = disjoint_decisions or []
    ontology_stats = write_ontology(
        output_dir, ecf_graph, k_mappings, disjoint_decisions, version=version
    )
    mapping_stats = write_mappings(output_dir, k_mappings, ecf_graph=ecf_graph, version=version)
    strategy_stats = write_integration_strategy(
        output_dir, ecf_graph, disjoint_decisions, ontology_stats, mapping_stats,
        coverage=coverage, limitations=limitations, version=version,
    )
    return {
        "ontology": ontology_stats,
        "mappings": mapping_stats,
        "integration_strategy": strategy_stats,
    }
