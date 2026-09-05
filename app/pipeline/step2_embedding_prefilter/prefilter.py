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

Strukturell ableitbare Paare (z. B. ESCO<->EQF/DQR, ELM<->ESCO) passieren
laut Konzeption einen Shortcut-Pfad und erreichen den LLM-Klassifikator
in Schritt 3 gar nicht — diese Fälle hier NICHT mit ausgeben. Sie werden
von find_structural_shortcuts() unten separat und vorgelagert behandelt.
"""

from __future__ import annotations

from typing import Iterable, Literal

import numpy as np
from rdflib import RDF, SKOS, Graph, Namespace, URIRef

from app.models.schemas import CandidatePair, Mapping, MappingJustification, ReviewStatus

HARM = Namespace("http://hr-qde.org/harmonised/")

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
# strukturell ableitbare Paare", para:shortcut). Datengetrieben statt
# hartcodierter KQR-Namen, damit neue KQR mit eigenen Cross-Referenz-
# Prädikaten ergänzt werden können, ohne diese Funktion zu ändern.
STRUCTURAL_SHORTCUT_PREDICATES: dict[str, str] = {
    # ESCO -> EQF/DQR-Niveau: esco:isPartOf ist im ESCO-Dump maschinenlesbar kodiert.
    "http://data.europa.eu/esco/model#isPartOf": "skos:broadMatch",
    # ELM-Lernmöglichkeit -> ESCO-Skill: elm:relatedEscoSkill ist im ELM-Dump per URI kodiert.
    "http://data.europa.eu/elm/model#relatedEscoSkill": "skos:exactMatch",
}


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


def filter_by_scope(
    concept_uris: Iterable[str],
    graph: Graph,
    scope: str = "all",
) -> tuple[list[str], list[str]]:
    """Teilt eine Konzeptliste VOR dem Embedding-Schritt in
    Pipeline-Konzepte und Skelett-Konzepte auf (Projekt-Scope-Konfiguration,
    Kapitel 4).

    Regeln je Konzept:

      - ``harm:conceptRole harm:LevelConcept``  -> IMMER Skelett-Schicht,
        niemals ANN/LLM, unabhaengig vom ``scope``.
      - ``scope == "level_only"``   -> nur LevelConcept-Knoten sind relevant;
        alle anderen Konzepte werden verworfen.
      - ``scope == "container_only"`` -> nur Konzepte MIT Kindern
        (has_narrower) laufen in die Pipeline.
      - ``scope == "leaf_only"``    -> nur Konzepte OHNE Kinder.
      - ``scope == "all"`` (Default) -> alle Nicht-Level-Konzepte.

    Rueckgabe: ``(pipeline_uris, skeleton_uris)`` -- beide in der
    Eingabereihenfolge.
    """
    pipeline: list[str] = []
    skeleton: list[str] = []
    for uri in concept_uris:
        node = URIRef(uri)
        role = graph.value(node, HARM.conceptRole)
        if role == HARM.LevelConcept:
            skeleton.append(uri)
            continue
        if scope == "level_only":
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


def find_structural_shortcuts(
    merged_graph: Graph,
    concept_lookup: dict[str, dict],
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
    """
    mappings: list[Mapping] = []
    for predicate_uri, sssom_predicate in STRUCTURAL_SHORTCUT_PREDICATES.items():
        for subject, obj in merged_graph.subject_objects(URIRef(predicate_uri)):
            subject_uri, object_uri = str(subject), str(obj)
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
