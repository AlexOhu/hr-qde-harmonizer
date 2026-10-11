"""
Schritt 2b: ANN-Suche (Approximate Nearest Neighbor) zur Generierung von
Kandidatenpaaren zwischen zwei KQR.

Reduziert den vollen O(n*m)-Vergleichsraum auf die k plausibelsten Paare je
Quellkonzept (vgl. Abschnitt 3.4). Der Parameter k (ANN_TOP_K) ist laut
Konzeption vorläufig (VH1.5) und wird erst in Kapitel 5 empirisch bestimmt —
im Code als Konfigurationswert behandeln, nicht hart codieren.

Implementierungshinweis: Die aktuell in Kapitel 3 eingebundene Textfassung
(fz12_formalisierung.tex, Abschnitt "Vektorindex") beschreibt einen nativen
Neo4j-Vektorindex statt eines separaten FAISS-Index. Diese Implementierung
folgt bewusst dem älteren, aber bereits im Stub/requirements.txt angelegten
FAISS-Ansatz, damit dieser Pipeline-Schritt ohne laufende Neo4j-Instanz
unit-testbar bleibt (CLAUDE.md-Prinzip "unabhängig testbar"). Das ist eine
dokumentierte Abweichung, keine widerspruchsfreie Umsetzung beider Fassungen.

Strukturell ableitbare Paare (z. B. ESCO<->EQF/DQR) passieren laut
Konzeption einen Shortcut-Pfad und erreichen den LLM-Klassifikator in
Schritt 3 gar nicht — diese Fälle hier NICHT mit ausgeben. Sie werden
von find_structural_shortcuts() unten separat und vorgelagert behandelt.
ELM wird nicht als Vergleichs-KQR gefuehrt (vgl.
chapters/chapter_3/infm.tex) und durchlaeuft diesen
Shortcut-Pfad deshalb nicht.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, Literal

import numpy as np
from rdflib import RDF, SKOS, Graph, Namespace, URIRef

from app.models.schemas import (
    CandidatePair,
    Concept,
    Mapping,
    MappingJustification,
    ReviewStatus,
)

HARM = Namespace("http://hr-qde.org/harmonised/")

ROOT = Path(__file__).resolve().parents[3]

logger = logging.getLogger(__name__)

# Erweiterbare Praedikatmenge fuer die Hierarchie-Erkennung. Ein Konzept
# "hat Kinder", wenn es selbst ein CHILD-Praedikat traegt ODER ein anderes
# Konzept per PARENT-Praedikat auf es zeigt. Neue KQR mit eigenen
# Hierarchie-Praedikaten (esco:isPartOf, dcterms:hasPart, ...) werden hier
# ergaenzt -- kein weiterer Code muss geaendert werden.
_CHILD_PREDICATES = (SKOS.narrower,)
_PARENT_PREDICATES = (SKOS.broader, SKOS.broaderTransitive)

ScopeValue = Literal["all", "container_only", "leaf_only", "level_only"]

# Bekannte strukturelle Cross-Referenz-Prädikate zwischen KQR und die SSSOM-
# Prädikate, auf die sie direkt abgebildet werden (Abschnitt "Shortcut-Pfad:
# strukturell ableitbare Paare", para:shortcut).
#
# Befund 2026-09-05: Ein neuer Shortcut hier bedeutete bisher zwingend eine
# Python-Quelltextänderung + Neustart der API -- Reibung für Funktionsgruppe
# 1 ("KQR einpflegen"), die konzeptionell ohne Backend-Eingriff auskommen
# soll. Daher datengetrieben über data/structural_shortcut_predicates.json
# (dieselbe Konvention wie data/kqr_registry.json/.env): ein neuer Shortcut
# ist ein Dateneintrag, kein Code-Edit. Schlüssel mit führendem "_" (z. B.
# "_comment") sind Dokumentation, keine Prädikat-URIs, und werden ignoriert
# (Konvention aus eval/G_struct.json).
_STRUCTURAL_SHORTCUT_PREDICATES_PATH = ROOT / "data" / "structural_shortcut_predicates.json"

# Fallback, falls die Datei fehlt (frischer Checkout ohne data/-Verzeichnis,
# ADR-5-Prinzip "läuft auch ohne volle Datenumgebung"). Deckt nur den
# ursprünglich hartcodierten Eintrag ab; alles Weitere gehört in die JSON-Datei.
_STRUCTURAL_SHORTCUT_PREDICATES_DEFAULT: dict[str, str] = {
    "http://data.europa.eu/esco/model#isPartOf": "skos:broadMatch",
}


def load_structural_shortcut_predicates(path: Path | None = None) -> dict[str, str]:
    """Lädt die Prädikat-Abbildung für find_structural_shortcuts() aus
    data/structural_shortcut_predicates.json. Wird bei jedem Aufruf neu
    gelesen (kein Modul-Cache) -- ein neuer Shortcut-Eintrag greift damit
    ohne Neustart der API, sobald die Datei gespeichert ist.

    Fehlt die Datei oder ist sie nicht valides JSON, greift der eingebaute
    Fallback (_STRUCTURAL_SHORTCUT_PREDICATES_DEFAULT) -- ein fehlender
    Shortcut-Eintrag darf die Klassifikation nie hart zum Absturz bringen.
    """
    target = path or _STRUCTURAL_SHORTCUT_PREDICATES_PATH
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "structural_shortcut_predicates.json nicht lesbar (%s: %s) -- Fallback auf %d "
            "eingebaute Standardeintraege.",
            target, exc, len(_STRUCTURAL_SHORTCUT_PREDICATES_DEFAULT),
        )
        return dict(_STRUCTURAL_SHORTCUT_PREDICATES_DEFAULT)

    result = {k: v for k, v in raw.items() if not k.startswith("_")}
    logger.info("structural_shortcut_predicates.json geladen: %d Eintraege aus %s.", len(result), target)
    return result


def find_candidate_pairs(
    embeddings_a: dict[str, np.ndarray],
    embeddings_b: dict[str, np.ndarray],
    top_k: int,
) -> list[CandidatePair]:
    """
    Sucht je Konzept aus KQR A die top_k ähnlichsten Konzepte aus KQR B.

    Baut einen FAISS IndexFlatIP über die (L2-normalisierten) Vektoren von
    KQR B auf und fragt für jedes Konzept aus KQR A die top_k nächsten
    Nachbarn ab. similarity_score ist die Kosinus-Ähnlichkeit (Inner Product
    normalisierter Vektoren, Wertebereich [-1, 1]).
    """
    if not embeddings_a or not embeddings_b:
        return []

    import faiss

    b_uris = list(embeddings_b.keys())
    b_matrix = np.stack([embeddings_b[uri] for uri in b_uris]).astype("float32")
    faiss.normalize_L2(b_matrix)

    index = faiss.IndexFlatIP(b_matrix.shape[1])
    index.add(b_matrix)

    a_uris = list(embeddings_a.keys())
    a_matrix = np.stack([embeddings_a[uri] for uri in a_uris]).astype("float32")
    faiss.normalize_L2(a_matrix)

    k = min(top_k, len(b_uris))
    scores, indices = index.search(a_matrix, k)

    pairs: list[CandidatePair] = []
    for row, a_uri in enumerate(a_uris):
        for score, idx in zip(scores[row], indices[row]):
            if idx < 0:
                continue
            pairs.append(
                CandidatePair(
                    concept_a=a_uri,
                    concept_b=b_uris[idx],
                    similarity_score=float(score),
                )
            )
    return pairs


def has_narrower(concept: URIRef, graph: Graph) -> bool:
    """Prueft, ob ein Konzept hierarchische Kinder hat -- als
    Mehrdeutigkeitspruefung ueber eine erweiterbare Praedikatmenge, nicht
    ueber eine einzelne Kante.

    Beruecksichtigt explizite Kindrelationen am Elternknoten
    (``skos:narrower``) und inverse Relationen am Kindknoten
    (``skos:broader``, ``skos:broaderTransitive``). Damit wird die in
    RDF-Formalisierungen uebliche Bottom-up-Kodierung ("B.1 skos:broader
    PLAN", ohne "PLAN skos:narrower B.1") korrekt erfasst.
    """
    for predicate in _CHILD_PREDICATES:
        if (concept, predicate, None) in graph:
            return True
    for predicate in _PARENT_PREDICATES:
        if (None, predicate, concept) in graph:
            return True
    return False


def concept_role(uri: str, graph: Graph) -> URIRef:
    """Liefert die kanonische Rolle eines Konzepts.

    Default ``harm:CompetenceConcept`` fuer Konzepte ohne explizite
    Rollenangabe -- Rueckwaertskompatibilitaet zu KQR, die ueberhaupt keine
    Rollenannotation tragen (ESCO, EQF, die urspruengliche ecf.ttl):
    sie verhalten sich weiterhin wie bisher, als reine Kompetenzebene.
    """
    concept = URIRef(uri)
    # Kanonisch sind Rollen RDF-Typen. Die alte Annotation bleibt als
    # lesbarer Fallback fuer bereits importierte KQR-Dateien erhalten.
    if (concept, RDF.type, HARM.LevelConcept) in graph:
        return HARM.LevelConcept
    if (concept, RDF.type, HARM.CompetenceConcept) in graph:
        return HARM.CompetenceConcept
    role = graph.value(concept, HARM.conceptRole)
    return role if role is not None else HARM.CompetenceConcept


def partition_by_role(
    embeddings: dict[str, np.ndarray], graph: Graph
) -> dict[URIRef, dict[str, np.ndarray]]:
    """Teilt ein Embedding-Dict nach RDF-Rolle auf (Default
    ``harm:CompetenceConcept``, s. ``concept_role``).

    Grundlage fuer rollengleiches Pairing (Befund 2026-09-05,
    ``classification_service._run_job``): ``harm:CompetenceConcept`` wird
    nur gegen ``harm:CompetenceConcept`` verglichen, ``harm:LevelConcept``
    nur gegen ``harm:LevelConcept`` -- unabhaengig davon, ob fuer das
    jeweilige KQR-Paar ein struktureller Shortcut existiert. Hat eine Seite
    keine Konzepte einer Rolle (z. B. ESCO: nur CompetenceConcept), bilden
    sich fuer diese Rolle schlicht keine Kandidatenpaare -- kein separater
    Ausschlussmechanismus noetig.
    """
    buckets: dict[URIRef, dict[str, np.ndarray]] = {}
    for uri, vec in embeddings.items():
        buckets.setdefault(concept_role(uri, graph), {})[uri] = vec
    return buckets


def filter_by_scope(
    concept_uris: Iterable[str],
    graph: Graph,
    scope: str = "all",
) -> tuple[list[str], list[str]]:
    """Teilt eine Konzeptliste VOR dem Embedding-Schritt in
    Pipeline-Konzepte und Skelett-Konzepte auf (Projekt-Scope-Konfiguration,
    Kapitel 4).

    Regeln je Konzept:

      - ``scope == "level_only"``   -> nur als ``harm:LevelConcept``
        typisierte Knoten laufen in die Pipeline, alle anderen
        gehen in die Skelett-Schicht.
      - ``scope == "container_only"`` -> nur Konzepte MIT Kindern
        (has_narrower) laufen in die Pipeline.
      - ``scope == "leaf_only"``    -> nur Konzepte OHNE Kinder.
      - ``scope == "all"`` (Default) -> alle Konzepte, unabhaengig von der
        Rolle.

    WICHTIG (Befund 2026-09-05): ``rdf:type harm:LevelConcept``
    wird hier NICHT mehr unbedingt und paarunabhaengig in die Skelett-Schicht
    geroutet. Die fruehere Regel verhinderte jeden ANN/LLM-Vergleich fuer
    Level-Konzepte, selbst wenn fuer das konkrete KQR-Paar gar kein
    struktureller Shortcut existiert (z. B. e-CF-Niveauknoten <-> DQR-
    Niveauknoten) -- das widerspricht dem Modell, dass ein KQR-Paar ohne
    expliziten Shortcut vollstaendig ueber ANN/LLM ausgewertet wird.
    Rollentrennung erfolgt stattdessen rollengleich in
    ``classification_service._run_job`` ueber ``partition_by_role`` auf
    BEIDEN Seiten des Paars, nicht durch einseitigen Ausschluss der
    Quellseite hier.

    Rueckgabe: ``(pipeline_uris, skeleton_uris)`` -- beide in der
    Eingabereihenfolge.
    """
    pipeline: list[str] = []
    skeleton: list[str] = []
    for uri in concept_uris:
        node = URIRef(uri)
        if scope == "level_only":
            if concept_role(uri, graph) == HARM.LevelConcept:
                pipeline.append(uri)
            else:
                skeleton.append(uri)
            continue
        children = has_narrower(node, graph)
        if scope == "container_only" and not children:
            continue
        if scope == "leaf_only" and children:
            continue
        pipeline.append(uri)
    return pipeline, skeleton


def detect_container_concepts(
    graph: Graph,
) -> tuple[set[str], dict[str, list[str]]]:
    """
    Trennt Container- von Blattkonzepten VOR der ANN-Suche.

    Ein Container ist ein Konzept mit mindestens einem Kind in der
    SKOS-Hierarchie. Als Kind zaehlt

      - jedes Objekt einer ``<container> skos:narrower <kind>``-Aussage,
      - jedes Subjekt einer ``<kind> skos:broader <container>``-Aussage.

    Die zweite Form ist noetig, weil viele KQR ihre Hierarchie
    ausschliesslich von unten nach oben ueber ``skos:broader`` kodieren
    (z. B. e-CF: ``ecf:A.1 skos:broader ecf:plan``). Beide Seiten der
    Kante muessen ein ``skos:Concept`` sein -- eine ``skos:broader`` auf das
    umgebende ``skos:ConceptScheme`` macht ein Konzept nicht zum Container.

    Container laufen NICHT als Quellkonzepte in die ANN-Suche. Ihr Mapping
    leitet ``derive_container_mappings()`` nach der Klassifikation der
    Blattknoten aus den Kindmappings ab.

    Rueckgabe: (Menge der Container-URIs, Abbildung Container-URI ->
    sortierte Liste der Kind-URIs).
    """
    children: dict[str, set[str]] = {}

    def _is_concept(node: object) -> bool:
        return (node, RDF.type, SKOS.Concept) in graph

    for parent, child in graph.subject_objects(SKOS.narrower):
        if _is_concept(parent) and _is_concept(child):
            children.setdefault(str(parent), set()).add(str(child))

    for child, parent in graph.subject_objects(SKOS.broader):
        if _is_concept(parent) and _is_concept(child):
            children.setdefault(str(parent), set()).add(str(child))

    container_uris = {uri for uri, kids in children.items() if kids}
    container_children = {uri: sorted(children[uri]) for uri in container_uris}
    return container_uris, container_children


def derive_container_mappings(
    container_children: dict[str, list[str]],
    pair_mappings: list[Mapping],
    concept_lookup: dict[str, dict],
    already_derived_subjects: set[str] | None = None,
) -> list[Mapping]:
    """
    Leitet fuer jeden Container ein Mapping aus den Mappings seiner
    Kindkonzepte ab (Aufruf nach der Blatt-Klassifikation in Schritt 3).

    Grundmenge je Container sind die entschiedenen Kindmappings
    (``ReviewStatus.CONJUNCT``) -- Kinder, fuer die die Klassifikation eine
    hierarchische oder aequivalente Relation zu einem Hub-Konzept gefunden
    hat. Offene RELATED-/UNRESOLVED-Kindmappings tragen keine belastbare
    Zielrelation und bleiben aussen vor; bereits abgeleitete Mappings
    (``semapv:LogicalReasoning``) werden nicht rekursiv weiterverwendet.

    Pro (Container, Hub-Zielkonzept) entsteht genau ein abgeleitetes Mapping:

      - ``predicate_id``          = ``skos:narrowMatch`` (der Container ist
        mindestens so weit wie jedes seiner Kinder und damit weiter als das
        Hub-Zielkonzept; Subjekt = Container ist weiter als das Objekt, also
        ``skos:narrowMatch`` nach W3C SKOS -- analog zu
        ``RelationType.A_SUBSUMES_B``. Konservativ: die genaue Relation zum
        Hub-Konzept ist nicht einzeln geprueft),
      - ``mapping_confidence``    = arithmetisches Mittel der
        ``mapping_confidence`` aller auf dieses Ziel zeigenden Kindmappings,
      - ``mapping_justification`` = ``semapv:LogicalReasoning``,
      - ``review_status``         = ``CONJUNCT`` (algorithmisch abgeleitet,
        analog zum Struktur-Shortcut; schwache Faelle filtert die
        Confidence-Schwelle beim Export).

    ``already_derived_subjects`` unterdrueckt die erneute Ableitung fuer
    Container, fuer die bei einem fortgesetzten Lauf bereits ein
    abgeleitetes Mapping vorliegt.
    """
    already = already_derived_subjects or set()
    by_child: dict[str, list[Mapping]] = {}
    for mapping in pair_mappings:
        by_child.setdefault(mapping.subject_id, []).append(mapping)

    derived: list[Mapping] = []
    for container_uri, child_uris in sorted(container_children.items()):
        if container_uri in already:
            continue
        container_info = concept_lookup.get(container_uri)
        if container_info is None:
            continue

        target_conf: dict[str, list[float]] = {}
        target_label: dict[str, str] = {}
        target_kqr: dict[str, str | None] = {}
        for child_uri in child_uris:
            for mapping in by_child.get(child_uri, []):
                if mapping.review_status != ReviewStatus.CONJUNCT:
                    continue
                if mapping.mapping_justification == MappingJustification.LOGICAL_REASONING:
                    continue
                target_conf.setdefault(mapping.object_id, []).append(mapping.mapping_confidence)
                target_label[mapping.object_id] = mapping.object_label
                target_kqr[mapping.object_id] = mapping.object_kqr_id

        for target_uri, confs in sorted(target_conf.items()):
            derived.append(
                Mapping(
                    subject_id=container_uri,
                    subject_label=container_info["pref_label"],
                    subject_kqr_id=container_info.get("kqr_id"),
                    object_id=target_uri,
                    object_label=target_label[target_uri],
                    object_kqr_id=target_kqr[target_uri],
                    predicate_id="skos:narrowMatch",
                    mapping_confidence=sum(confs) / len(confs),
                    mapping_justification=MappingJustification.LOGICAL_REASONING,
                    mapping_source="algorithmic",
                    review_status=ReviewStatus.CONJUNCT,
                    justification=(
                        f'Aus {len(confs)} Kindmapping(s) von '
                        f'"{container_info["pref_label"]}" abgeleitet '
                        f'(skos:narrowMatch, konservativ; mapping_confidence = '
                        f'Mittel der Kind-Konfidenzen).'
                    ),
                )
            )
    return derived


def has_level_concept_parent(concept_uri: str, graph: Graph) -> bool:
    """True, wenn das Konzept ueber ``skos:broader`` auf mindestens ein
    Konzept zeigt, das selbst als ``harm:LevelConcept`` typisiert ist.

    Diskriminator fuer Deskriptor-Niveauknoten (z. B. die DQR-Dimensions-
    facetten ``dqr:L5_Knowledge`` mit ``skos:broader dqr:L5``) ohne Bezug
    auf KQR-Namen.
    """
    for parent in graph.objects(URIRef(concept_uri), SKOS.broader):
        if concept_role(str(parent), graph) == HARM.LevelConcept:
            return True
    return False


def _level_child_uris_by_parent(graph: Graph) -> dict[str, set[str]]:
    """Eltern-URI -> Menge ihrer ``harm:LevelConcept``-Kinder, gebildet aus
    ``<kind> skos:broader <elter>`` UND ``<elter> skos:narrower <kind>``
    (beide Kodierungsrichtungen, analog ``detect_container_concepts``)."""
    by_parent: dict[str, set[str]] = {}
    for child, parent in graph.subject_objects(SKOS.broader):
        if concept_role(str(child), graph) == HARM.LevelConcept:
            by_parent.setdefault(str(parent), set()).add(str(child))
    for parent, child in graph.subject_objects(SKOS.narrower):
        if concept_role(str(child), graph) == HARM.LevelConcept:
            by_parent.setdefault(str(parent), set()).add(str(child))
    return by_parent


def child_level_concept_uris(graph: Graph) -> set[str]:
    """URIs der Deskriptor-Niveauknoten, die NICHT durch ANN/LLM laufen,
    sondern ihr Mapping per Eltern-Ableitung erhalten
    (``derive_child_level_mappings``).

    Ein Knoten zaehlt dazu, wenn er

      - ``rdf:type harm:LevelConcept`` traegt,
      - per ``skos:broader`` auf ein anderes ``harm:LevelConcept`` zeigt
        (``has_level_concept_parent``),
      - selbst KEINE ``harm:LevelConcept``-Kinder hat (Blattknoten) und
      - dessen Level-Elternteil in >= 2 ``harm:LevelConcept``-Kinder
        verzweigt.

    Die letzten beiden Bedingungen trennen die 32 DQR-Dimensionsfacetten
    (``dqr:L{n}_Knowledge`` ...) von den 8 Niveau-Ankern ``dqr:L1..L8``:
    die Anker bilden in jeder Variante eine lineare ``skos:broader``-Kette
    (jeder Anker hat hoechstens EIN Anker-Kind), die 2D-Variante haengt an
    jeden Anker zusaetzlich vier gleichrangige Facetten. Ein Knoten, dessen
    Elternteil nur ein einziges Level-Kind hat (die Kettenspitze ``L8``),
    ist damit kein Deskriptor. Kein Bezug auf KQR-Namen -- die Regel greift
    fuer jedes KQR mit einer typisierten Niveauhierarchie.
    """
    level_children = _level_child_uris_by_parent(graph)
    branching_parents = {p for p, kids in level_children.items() if len(kids) >= 2}
    parents_with_level_children = set(level_children)

    result: set[str] = set()
    for concept in graph.subjects(RDF.type, SKOS.Concept):
        uri = str(concept)
        if concept_role(uri, graph) != HARM.LevelConcept:
            continue
        if uri in parents_with_level_children:
            continue  # hat selbst LevelConcept-Kinder -> Anker, kein Blatt
        parents = {str(p) for p in graph.objects(concept, SKOS.broader)}
        if not any(
            p in branching_parents and concept_role(p, graph) == HARM.LevelConcept
            for p in parents
        ):
            continue
        result.add(uri)
    return result


def derive_child_level_mappings(
    child_level_concepts: list[Concept],
    shortcut_mappings: list[Mapping],
    already_derived_subjects: set[str] | None = None,
) -> list[Mapping]:
    """
    Leitet fuer jeden Deskriptor-Niveauknoten (``child_level_concept_uris``)
    ein Mapping aus dem Struktur-Shortcut seines Eltern-Ankers ab -- Aufruf
    nach ``find_structural_shortcuts()``, analog zu
    ``derive_container_mappings()``, aber ueber Rolle + Hierarchie statt
    ueber ``skos:narrower``.

    Logik je Kind:

      - ``parent_mapping`` = das erste Shortcut-Mapping, dessen
        ``subject_id`` in ``child.broader`` steht,
      - Ergebnis-Mapping: ``subject_id`` = Kind, ``object_id`` /
        ``mapping_confidence`` vom Eltern-Mapping geerbt,
        ``predicate_id = skos:narrowMatch`` (``child skos:broader parent``
        und ``parent skos:exactMatch L`` => ``child skos:narrowMatch L``),
        ``mapping_justification = semapv:LogicalReasoning``,
        ``review_status = CONJUNCT`` (durch Inferenz determiniert, keine
        manuelle Pruefung -- daher nie im Review-Queue).

    Kinder ohne per Struktur-Shortcut gematchten Eltern-Anker werden mit
    einer Warnung uebersprungen. ``already_derived_subjects`` unterdrueckt
    die erneute Ableitung bei fortgesetzten Laeufen (gleiche Konvention wie
    ``derive_container_mappings``).
    """
    already = already_derived_subjects or set()
    shortcut_by_subject: dict[str, Mapping] = {}
    for mapping in shortcut_mappings:
        shortcut_by_subject.setdefault(mapping.subject_id, mapping)

    derived: list[Mapping] = []
    for child in child_level_concepts:
        if child.uri in already:
            continue
        parent_mapping = next(
            (shortcut_by_subject[p] for p in child.broader if p in shortcut_by_subject),
            None,
        )
        if parent_mapping is None:
            logger.warning(
                "Eltern-Ableitung uebersprungen: LevelConcept '%s' hat keinen "
                "per Struktur-Shortcut gematchten Eltern-Anker (broader=%s).",
                child.uri,
                child.broader,
            )
            continue
        parent_predicate = (
            parent_mapping.predicate_id.value if parent_mapping.predicate_id else "?"
        )
        derived.append(
            Mapping(
                subject_id=child.uri,
                subject_label=child.pref_label,
                subject_kqr_id=child.kqr_id,
                object_id=parent_mapping.object_id,
                object_label=parent_mapping.object_label,
                object_kqr_id=parent_mapping.object_kqr_id,
                predicate_id="skos:narrowMatch",
                mapping_confidence=parent_mapping.mapping_confidence,
                mapping_justification=MappingJustification.LOGICAL_REASONING,
                mapping_source="algorithmic",
                review_status=ReviewStatus.CONJUNCT,
                justification=(
                    f'Aus dem Eltern-Anker-Match "{parent_mapping.subject_label}" '
                    f'({parent_predicate} {parent_mapping.object_id}) abgeleitet: '
                    f"das Kind ist enger als der Anker "
                    f"(skos:narrowMatch, semapv:LogicalReasoning)."
                ),
            )
        )
    return derived


def find_structural_shortcuts(
    merged_graph: Graph,
    concept_lookup: dict[str, dict],
    *,
    predicates: dict[str, str] | None = None,
    exclude_subjects: set[str] | None = None,
) -> list[Mapping]:
    """
    Regelbasierter Vorfilter (para:vorfilterung / para:shortcut): durchsucht
    den RDF-Graphen nach bekannten strukturellen Cross-Referenzen zwischen
    KQR (STRUCTURAL_SHORTCUT_PREDICATES) und übersetzt Treffer direkt in
    Mapping-Objekte mit mapping_confidence=1.00, ohne dass das betroffene
    Paar den LLM-Klassifikator (Schritt 3) durchläuft.

    concept_lookup: Concept.uri -> {"pref_label": ..., "kqr_id": ...},
    typischerweise die Vereinigung der concept_lookup-Dicts beider KQR.
    Cross-Referenzen, deren Ziel nicht im concept_lookup enthalten ist
    (z. B. weil das Ziel-KQR noch nicht geladen wurde), werden übersprungen.

    ``predicates``: Ersetzt die aus
    ``data/structural_shortcut_predicates.json`` geladene Abbildung fuer
    genau diesen Aufruf (Praedikat-URI -> SSSOM-Praedikat). Damit kann ein
    Lauf ein zusaetzliches Crosswalk-Praedikat -- etwa ``skos:exactMatch``
    fuer einen reinen Niveau-Crosswalk gegen EQF -- als Shortcut behandeln,
    ohne die Datei zu veraendern. Default (``None``): die Datei wird geladen.
    ``exclude_subjects``: Subjekt-URIs, deren Treffer uebersprungen werden --
    fuer Deskriptor-Niveauknoten (``child_level_concept_uris``), deren
    Mapping stattdessen aus dem Eltern-Anker abgeleitet wird
    (``derive_child_level_mappings``).
    """
    predicate_map = (
        predicates if predicates is not None else load_structural_shortcut_predicates()
    )
    exclude = exclude_subjects or set()
    mappings: list[Mapping] = []
    for predicate_uri, sssom_predicate in predicate_map.items():
        for subject, obj in merged_graph.subject_objects(URIRef(predicate_uri)):
            subject_uri, object_uri = str(subject), str(obj)
            if subject_uri in exclude:
                continue
            subject_info = concept_lookup.get(subject_uri)
            object_info = concept_lookup.get(object_uri)
            if subject_info is None or object_info is None:
                continue

            mappings.append(
                Mapping(
                    subject_id=subject_uri,
                    subject_label=subject_info["pref_label"],
                    subject_kqr_id=subject_info.get("kqr_id"),
                    object_id=object_uri,
                    object_label=object_info["pref_label"],
                    object_kqr_id=object_info.get("kqr_id"),
                    predicate_id=sssom_predicate,
                    mapping_confidence=1.0,
                    mapping_justification=MappingJustification.STRUCTURAL_MATCHING,
                    mapping_source="algorithmic",
                    review_status=ReviewStatus.CONJUNCT,
                    justification="semapv:MappingChaining",
                )
            )
    return mappings


def is_occupation_uri(uri: str) -> bool:
    """Gibt True zurück, wenn die URI zu einem ESCO-Beruf (Occupation) gehört.

    Die Unterscheidung zwischen Occupation und Skill ist im formalisierten
    ESCO-TTL nicht über rdf:type annotiert, sondern ausschließlich über
    den URI-Pfad kodiert (/occupation/ vs. /skill/). Diese Funktion macht
    die Klassifikationslogik explizit und testbar.

    Andere KQR (e-CF, DQR, EQF) haben keine /occupation/-Segmente in ihren
    URIs — der Aufruf dieser Funktion auf Nicht-ESCO-URIs ist daher
    unschädlich und gibt immer False zurück.
    """
    return "/occupation/" in uri


def exclude_occupation_embeddings(
    embeddings: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """Entfernt Occupation-URIs aus einem Embedding-Dict vor der FAISS-Indexierung.

    Wird auf die Hub-Seite (target_embeddings) angewendet, bevor
    find_candidate_pairs() aufgerufen wird. Dadurch werden ausschließlich
    ESCO-Skills als Kandidatenziele generiert. Occupation-Konzepte verbleiben
    in concept_lookup und bleiben damit für Strukturelle Shortcuts abrufbar;
    sie werden lediglich nicht in den ANN-Index aufgenommen.

    Gibt ein neues Dict zurück. Das Eingabe-Dict wird nicht verändert.
    """
    return {uri: vec for uri, vec in embeddings.items() if not is_occupation_uri(uri)}
