"""
Zentrale Datenmodelle, die alle Pipeline-Schritte gemeinsam verwenden.

Diese Modelle spiegeln die in Kapitel 3 definierten Strukturen:
- Concept / KQR: Ergebnis von Schritt 1 (Formalisierung, Abschnitt 3.3)
- CandidatePair: Ergebnis von Schritt 2 (Embedding & Vorfilter, Abschnitt 3.4)
- ClassificationResult / Mapping: Ergebnis von Schritt 3 (Abschnitt 3.5)
- SSSOMRecord: Exportzeile gemäß Tabelle 3.9
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class KQRStatus(str, Enum):
    """Zustände eines KQR im Prozessverlauf (vgl. Abschnitt 3.8.3, Action Constraint)."""

    ROH = "roh"
    FORMALISIERT = "formalisiert"
    BEREIT = "bereit"


class KQR(BaseModel):
    """Ein Kompetenz-, Qualifikations- oder Berufsrahmenwerk (z. B. ESCO, e-CF, EQF)."""

    id: str
    name: str
    namespace_uri: str
    source_format: str  # z.B. "pdf", "xml", "rdf", "csv"
    status: KQRStatus = KQRStatus.ROH
    concept_count: int | None = None
    # Hub-Rahmen (z.B. ESCO) ist Ankerpunkt aller schichteninternen Vergleiche,
    # vgl. Tabelle "kqr_schichten" (Abschnitt fz12_formalisierung).
    is_hub: bool = False


class FormalizationDraft(BaseModel):
    """Ergebnis eines LLM-gestützten Formalisierungslaufs (Schritt 1, PDF-Pfad).

    Enthält neben dem rohen Turtle-Entwurf alle Angaben, die für eine
    reproduzierbare Dokumentation des Laufs nötig sind (z. B. im Anhang
    der Arbeit) — analog zur Provenance bei ClassificationRun/Mapping.
    """

    draft_ttl: str
    prompt: str
    model: str  # LLMProvider.model_id, z.B. "mistral/mistral-small-latest"
    temperature: float
    max_tokens: int
    started_at: datetime
    finished_at: datetime

    @property
    def duration_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()


class Concept(BaseModel):
    """Ein einzelnes SKOS-Konzept nach der Formalisierung (Schritt 1)."""

    uri: str
    kqr_id: str
    pref_label: str
    definition: str | None = None
    broader: list[str] = Field(default_factory=list)  # skos:broader URIs
    narrower: list[str] = Field(default_factory=list)  # skos:narrower URIs


class CandidatePair(BaseModel):
    """Ein Kandidatenpaar nach ANN-Suche in Schritt 2, vor der Klassifikation."""

    concept_a: str  # Concept.uri
    concept_b: str  # Concept.uri
    similarity_score: float
    layer: str | None = None  # HDBSCAN-Cluster-Zuordnung, falls vorhanden


class RelationType(str, Enum):
    """Die vier Relationstypen aus Abschnitt 3.5.1.

    Klassifikationsschritt-intern: RelationType ist die Ausgabe eines einzelnen
    LLM-Laufs (ClassificationRun) und der Mehrheitsentscheid
    (ClassificationResult.final_relation). Das persistierte und über die API
    ausgetauschte Vokabular ist ausschließlich MappingPredicate; ein fehlender
    Mehrheitsentscheid ist final_relation=None (kein eigener Relationswert).
    """

    EQUIVALENT = "EQUIVALENT"
    A_SUBSUMES_B = "A_SUBSUMES_B"
    B_SUBSUMES_A = "B_SUBSUMES_A"
    RELATED = "RELATED"

    def to_skos_predicate(self) -> "MappingPredicate":
        """Abbildung auf das SKOS-Mapping-Prädikat (MappingPredicate).

        subject_id ist Konzept A, object_id ist Konzept B (sssom_writer). Nach
        SKOS und Kapitel 2 (sssom.tex) besagt ``A skos:narrowMatch B``, dass B
        enger ist als A, und ``A skos:broadMatch B``, dass B weiter ist als A.
        A_SUBSUMES_B heißt "A ist Oberbegriff von B", also B enger  -> narrowMatch;
        B_SUBSUMES_A heißt "B ist Oberbegriff von A", also B weiter -> broadMatch.
        Die frühere Zuordnung war invertiert (broad/narrow vertauscht) und
        widersprach damit SKOS, Kapitel 2 sowie dem Struktur-Shortcut-Pfad
        (find_structural_shortcuts).
        """
        mapping = {
            RelationType.EQUIVALENT: MappingPredicate.EXACT_MATCH,
            RelationType.A_SUBSUMES_B: MappingPredicate.NARROW_MATCH,
            RelationType.B_SUBSUMES_A: MappingPredicate.BROAD_MATCH,
            RelationType.RELATED: MappingPredicate.RELATED_MATCH,
        }
        return mapping[self]


class MappingJustification(str, Enum):
    """Verfahrensnachweis eines Mappings als SEMAPV-CURIE (SSSOM-Feld
    mapping_justification, Vokabular-Version 2026-06-10,
    https://w3id.org/semapv/vocab/).

    Ersetzt das fruehere Feld match_type. Die Zuordnung folgt dem
    erzeugenden Verfahren, nicht einer nachtraeglichen Klassifikation:

    - StructuralMatching: Struktur-Shortcut ueber bekannte Cross-Referenz-
      Praedikate (find_structural_shortcuts, Schritt 2).
    - LLMBasedMatching: LLM-Dreifachklassifikation mit Mehrheitsentscheid
      (Schritt 3).
    - MappingReview: menschliche Entscheidung im Review (PUT
      /mappings/{id}/review bzw. PUT /mappings/{id}).
    - LogicalReasoning: aus bereits vorliegenden Mappings abgeleitet, ohne
      eigenen LLM- oder Regelmatch. Verwendet fuer Container-Konzepte
      (skos:narrower-/skos:broader-Eltern), deren Mapping die Pipeline nach
      der Blatt-Klassifikation aus den Kindmappings ableitet
      (prefilter.derive_container_mappings): predicate_id konservativ
      skos:broadMatch, mapping_confidence als Mittel der Kind-Konfidenzen.

    Der FAISS-Vorfilter erzeugt bewusst keinen eigenen Wert: er liefert
    Kandidatenpaare, kein fertiges Mapping (semapv:EmbeddingBasedBlocking
    waere Blocking, kein Matching).
    """

    STRUCTURAL_MATCHING = "semapv:StructuralMatching"
    LLM_BASED_MATCHING = "semapv:LLMBasedMatching"
    MAPPING_REVIEW = "semapv:MappingReview"
    LOGICAL_REASONING = "semapv:LogicalReasoning"
    MANUAL_MAPPING_CURATION = "semapv:ManualMappingCuration"


# Alte match_type-Werte -> mapping_justification. Wird von
# beim Laden persistierter Mapping-Objekte aus frueheren Datenstaenden
# verwendet.
LEGACY_MATCH_TYPE_JUSTIFICATION: dict[str, MappingJustification] = {
    "lex": MappingJustification.STRUCTURAL_MATCHING,
    "struct": MappingJustification.STRUCTURAL_MATCHING,
    "llm": MappingJustification.LLM_BASED_MATCHING,
    "lex+llm": MappingJustification.LLM_BASED_MATCHING,
    "llm+struct": MappingJustification.LLM_BASED_MATCHING,
}


class ReviewStatus(str, Enum):
    """Entscheidungsstand eines persistierten Mapping-Objekts.

    OPEN gilt fuer Kandidatenpaare, die die Klassifikation als RELATED
    eingestuft hat oder fuer die kein Mehrheitsentscheid zustande kam
    (predicate_id=None): sie sind persistiert und ueber /mappings/ erreichbar,
    gehoeren aber noch nicht zur konjunkten Menge K. CONJUNCT und DISJUNCT
    sind die beiden Auswege aus PUT /mappings/{id}/review.
    """

    OPEN = "open"
    CONJUNCT = "conjunct"
    DISJUNCT = "disjunct"


class MappingPredicate(str, Enum):
    """Das eine Mapping-Relationsvokabular: SKOS-Mapping-Praedikate als CURIE.

    Persistiert in Mapping.predicate_id, ausgetauscht über die API (Konjunkt-
    Zweig von PUT /mappings/{id}/review und die Korrektur PUT /mappings/{id}).
    Enthaelt gegenueber RelationType.to_skos_predicate() zusaetzlich
    skos:closeMatch, das die LLM-Klassifikation nie erzeugt, ein Reviewer
    aber vergeben koennen muss.
    """

    EXACT_MATCH = "skos:exactMatch"
    CLOSE_MATCH = "skos:closeMatch"
    BROAD_MATCH = "skos:broadMatch"
    NARROW_MATCH = "skos:narrowMatch"
    RELATED_MATCH = "skos:relatedMatch"


class ClassificationRun(BaseModel):
    """Ein einzelner LLM-Klassifikationslauf (von 3, vgl. Mehrheitsentscheid Abschnitt 3.5.2)."""

    relation: RelationType
    reasoning: str
    model: str
    temperature: float


class ClassificationResult(BaseModel):
    """Ergebnis der Dreifachklassifikation inkl. Mehrheitsentscheid für ein CandidatePair."""

    pair: CandidatePair
    runs: list[ClassificationRun]
    # None = kein Mehrheitsentscheid (majority_vote fand keine Mehrheit). Das
    # abgeleitete Mapping traegt dann predicate_id=None und ReviewStatus.OPEN.
    final_relation: RelationType | None
    mapping_confidence: float  # Anteil übereinstimmender Läufe (0-1)


class Mapping(BaseModel):
    """Eine dokumentierte Mapping-Entscheidung inkl. Provenance (FA4)."""

    mapping_id: str = Field(default_factory=lambda: str(uuid4()))
    subject_id: str
    subject_label: str
    subject_kqr_id: str | None = None  # Herkunfts-KQR von subject_id, z.B. "e-cf"
    object_id: str
    object_label: str
    object_kqr_id: str | None = None  # Herkunfts-KQR von object_id, z.B. "esco"
    # None gilt genau fuer offene Paare ohne LLM-Mehrheitsentscheid: sie tragen
    # ReviewStatus.OPEN und bekommen erst im Review ein Praedikat. Ein offenes
    # RELATED-Ergebnis traegt dagegen skos:relatedMatch.
    predicate_id: MappingPredicate | None = None
    mapping_confidence: float
    mapping_tool: str = "HR-QDE-Harmonizer-v0.1"
    # Verfahrensnachweis nach SEMAPV (ersetzt das entfernte Feld match_type).
    mapping_justification: MappingJustification
    # algorithmic: automatisch erzeugt (Vorfilter-Shortcut oder LLM);
    # manual: durch Systembetreuer angelegt/überschrieben (UC3, FA3/FA4).
    mapping_source: Literal["algorithmic", "manual"] = "algorithmic"
    author: str | None = None  # bei manueller Entscheidung: Nutzername
    created_at: datetime = Field(default_factory=datetime.utcnow)
    justification: str | None = None
    # Entscheidungsstand. RELATED-Ergebnisse und Paare ohne Mehrheitsentscheid
    # werden mit stabiler mapping_id persistiert und tragen OPEN, bis
    # PUT /mappings/{id}/review sie nach CONJUNCT oder DISJUNCT ueberfuehrt.
    review_status: ReviewStatus = ReviewStatus.CONJUNCT
    # Pflichtvermerk bei DisjointStrategy.MAP_TO_NEAREST (Kontextverlust).
    context_loss_note: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_shapes(cls, data: object) -> object:
        """Persistierte Mappings aus frueheren Datenstaenden ladbar halten,
        damit Snapshots und Forks ohne Migrationslauf nicht mit
        ValidationError blockieren:

        - match_type statt mapping_justification (Stand vor v0.2).
        - source_relation (entfernt): ein offenes Paar mit
          source_relation="UNRESOLVED" bekommt predicate_id=None; das Feld
          selbst wird verworfen.
        """
        if not isinstance(data, dict):
            return data
        payload = dict(data)

        legacy_source_relation = payload.pop("source_relation", None)
        if (
            legacy_source_relation in ("UNRESOLVED", "unresolved")
            and payload.get("review_status") == "open"
        ):
            payload["predicate_id"] = None

        if "mapping_justification" not in payload and payload.get("match_type") is not None:
            legacy = payload.pop("match_type")
            if payload.get("mapping_source") == "manual":
                payload["mapping_justification"] = MappingJustification.MAPPING_REVIEW
            else:
                payload["mapping_justification"] = LEGACY_MATCH_TYPE_JUSTIFICATION.get(
                    str(legacy), MappingJustification.LLM_BASED_MATCHING
                )
        return payload


FrameworkType = Literal["competence_framework", "level_framework"]


class LevelMapping(BaseModel):
    """Eine normative Niveauzuordnung, materialisiert aus einer
    veroeffentlichten Crosswalk-Tabelle (Deutscher EQR-Zuordnungsbericht:
    DQR-Niveau <-> EQF-Niveau; e-CF 3.0 (CWA 16234-1:2014): e-CF-Proficiency-Stufe <->
    EQF-Niveau).

    Die Felder folgen SSSOM. Fuer die
    DQR<->EQF-Faelle wird eine ``LevelMapping`` als ``harm:LevelMapping``-
    Record serialisiert (ADR-23: Subjekt ``hrqde:DQR{n}``, Objekt die
    qf-eu-level-Autoritaets-URI). Auch e-CF-Dimension-3-zu-DQR wird als
    reguläres ``LevelMapping`` mit ``skos:closeMatch`` materialisiert.
    """

    subject_id: str  # Skelett-Niveauknoten oder e-CF-Kompetenz-URI
    subject_label: str
    proficiency_level: str | None = None  # z. B. "e-3" (nur e-CF-Crosswalk)
    object_id: str  # qf-eu-level-Autoritaets-URI oder Skelett-Niveauknoten
    object_label: str
    predicate_id: str = "skos:exactMatch"
    mapping_confidence: Decimal = Decimal("1.0")
    mapping_justification: MappingJustification = MappingJustification.MANUAL_MAPPING_CURATION
    mapping_tool: str = "Deutscher EQR-Zuordnungsbericht 2013"


class SSSOMRecord(BaseModel):
    """Eine Exportzeile im SSSOM-Format, Felder gemäß Tabelle 3.9."""

    subject_id: str
    subject_label: str
    object_id: str
    object_label: str
    predicate_id: str
    mapping_confidence: float
    mapping_tool: str
    mapping_justification: str
    comment: str | None = None
    mapping_source: str
    author_id: str | None = None

    @classmethod
    def from_mapping(cls, mapping: Mapping) -> "SSSOMRecord":
        # predicate_id ist ein MappingPredicate (str, Enum). Explizit .value,
        # damit die TSV-Zelle "skos:exactMatch" traegt und nicht die
        # str()/format()-Darstellung "MappingPredicate.EXACT_MATCH".
        return cls(
            subject_id=mapping.subject_id,
            subject_label=mapping.subject_label,
            object_id=mapping.object_id,
            object_label=mapping.object_label,
            predicate_id=mapping.predicate_id.value if mapping.predicate_id else "",
            mapping_confidence=mapping.mapping_confidence,
            mapping_tool=mapping.mapping_tool,
            mapping_justification=mapping.mapping_justification.value,
            comment=mapping.justification,
            mapping_source=mapping.mapping_source,
            author_id=mapping.author,
        )


class ClusterResult(BaseModel):
    """Ergebnis eines HDBSCAN-Clusters (FZ2.3, Abschnitt 4.4.1)."""

    cluster_id: int  # -1 = Noise/Ausreißer
    concept_uris: list[str]  # Concept.uri-Werte im Cluster
    auto_label: str  # häufigstes prefLabel (deterministisch)
    llm_label: str | None = None  # LLM-verfeinertes Label (zweistufig, VH1.6)
    centroid_uri: str | None = None  # Konzept mit kleinstem L2-Abstand zum Zentroid


class HarmonisedCluster(BaseModel):
    """Knoten im harmonisierten DAG (rdfs:subClassOf-Hierarchie, FZ2.3)."""

    cluster_uri: str  # http://hr-qde.org/harmonised/cluster/{id}
    label: str
    parent_cluster_uri: str | None = None
    member_uris: list[str]  # kanonische Konzept-URIs


class DisjointStrategy(str, Enum):
    """Zulässige Integrationsstrategien für disjunkte Konzepte (FZ3.3).

    Alle Werte sind mit Unterstrich geschrieben, nicht mit Bindestrich: die
    Werte landen als Literal im generierten Cypher der neosemantics-
    Materialisierung, wo ein Bindestrich als Subtraktionsoperator gelesen
    würde.
    """

    OWN_CLASS = "own_class"
    # Konzept wird als eigenständige harm:HarmonisedConcept-Klasse übernommen.
    ATTACH_TO_SKELETON = "attach_to_skeleton"
    # Konzept wird als rdfs:subClassOf eines Skelett-Knotens eingehängt
    # (z. B. hrqde:DQR1–DQR8); Zielklasse steht in anchor_class.
    MAP_TO_NEAREST = "map_to_nearest"
    # Konzept wird per skos:relatedMatch an das nächstgelegene Hub-Konzept
    # gehängt; der dabei entstehende Kontextverlust ist zu vermerken.
    OUT_OF_SCOPE = "out_of_scope"
    # Konzept gehört nicht zur harmonisierten Ontologie (begründungspflichtig).

    @classmethod
    def _missing_(cls, value: object) -> "DisjointStrategy | None":
        """Nimmt die Strategienamen vor v0.2 entgegen, damit bereits
        persistierte Entscheidungen ohne Migrationslauf ladbar bleiben.
        Unbekannte Werte (insbesondere "pending") bleiben ungültig."""
        return LEGACY_DISJOINT_STRATEGY.get(str(value))


# Strategienamen vor v0.2 -> aktuelle Werte. map_to_nearest hatte keine
# Entsprechung und kann daher nur neu entschieden werden.
LEGACY_DISJOINT_STRATEGY: dict[str, DisjointStrategy] = {
    "standalone_class": DisjointStrategy.OWN_CLASS,
    "anchor_to_root": DisjointStrategy.ATTACH_TO_SKELETON,
    "excluded": DisjointStrategy.OUT_OF_SCOPE,
}


class DisjointConceptDecision(BaseModel):
    """Dokumentierte Integrationsentscheidung für ein disjunktes Konzept (FA4)."""

    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    concept_id: str
    concept_label: str
    kqr_id: str
    strategy: DisjointStrategy
    anchor_class: str | None = None  # bei ATTACH_TO_SKELETON: Zielklassen-URI
    # bei MAP_TO_NEAREST verpflichtend: welcher Kontext beim Anhängen an das
    # nächstgelegene Hub-Konzept verloren geht.
    context_loss_note: str | None = None
    # KQR-Kombination, gegen die das Konzept zum Entscheidungszeitpunkt
    # geprüft wurde (sortierte project.kqr_ids). Default statt Pflichtfeld,
    # damit bereits persistierte Datensätze ohne diesen Wert weiter ladbar
    # bleiben. Der
    # Wert wird beim Schreiben sortiert (disjoint_service.decide), damit
    # Teilmengen-Vergleiche unabhängig von der Reihenfolge in
    # project.kqr_ids stabil sind.
    context_kqr_ids: list[str] = Field(default_factory=list)
    justification: str  # verpflichtend (Accountability-Prinzip)
    author: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PairResetEvent(BaseModel):
    """Protokolliert das Zuruecksetzen eines KQR-Paares (Loeschung aller
    Mappings und ClassificationResults dieses Paares, vgl.
    classification_service.reset_pair). Ein Reset ist selbst eine
    protokollpflichtige Kuratoren-Entscheidung (Accountability-Prinzip):
    justification und author sind Pflichtfelder, analog zu Mapping und
    DisjointConceptDecision. affected_disjoint_decisions zaehlt bereits
    getroffene Integrationsentscheidungen, die dieses Paar betreffen, ohne
    sie zu veraendern -- DisjointConceptDecision ist konzept-, nicht
    paarbezogen (vgl. disjoint_service.get_summary_for_pair) und soll durch
    einen Reset nicht stillschweigend verschwinden."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    kqr_a_id: str
    kqr_b_id: str
    removed_mappings: int
    removed_classification_results: int
    affected_disjoint_decisions: int
    justification: str
    author: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProjectStatus(str, Enum):
    """Zustand eines Projekts."""

    ACTIVE = "active"  # aktiv bearbeitbar
    SNAPSHOT = "snapshot"  # eingefroren (read-only), durch Snapshot erstellt


class Project(BaseModel):
    """Ein Harmonisierungsprojekt kapselt KQR-Auswahl und alle daraus
    resultierenden Artefakte (Mappings, Entscheidungen, Clustering)."""

    project_id: str
    name: str
    description: str | None = None
    kqr_ids: list[str]  # KQR-IDs aus dem globalen Registry
    # Scope je KQR fuer diesen Run (Vorfilter, prefilter.filter_by_scope):
    # kqr_id -> "all" | "container_only" | "leaf_only" | "level_only".
    # Fehlt ein Eintrag, gilt "all". LevelConcept-Knoten (RDF-Typ)
    # gehen unabhaengig vom Scope immer in die Skelett-Schicht.
    kqr_scopes: dict[str, str] = Field(default_factory=dict)
    hub_kqr_id: str | None = None  # welcher KQR ist der Hub in diesem Projekt
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: ProjectStatus = ProjectStatus.ACTIVE
    parent_project_id: str | None = None  # bei Snapshots/Forks
    version_label: str | None = None  # z.B. "v0.3", "Snapshot 2026-07-30"


class KQRPairStatus(BaseModel):
    """Pipeline-Status für ein einzelnes KQR-Paar innerhalb eines Projekts."""

    kqr_a_id: str
    kqr_a_name: str
    kqr_b_id: str
    kqr_b_name: str
    job_status: str | None = None  # null | running | completed | failed | interrupted | paused
    job_id: str | None = None
    # Nur bei job_status="failed" gesetzt (str(exc) aus classification_service._run_job);
    # ein "interrupted" Job hat keine Ausnahme, sondern nur einen Prozess-Neustart erlebt.
    error: str | None = None
    total_pairs: int = 0
    classified_pairs: int = 0
    mappings_count: int = 0
    pending_review_count: int = 0  # confidence < threshold oder ohne Mehrheitsentscheid
    unresolved_count: int = 0  # offene Paare ohne LLM-Mehrheitsentscheid (predicate_id=None)
    disjoint_total: int = 0  # disjunkte Konzepte bezogen auf genau dieses Paar
    disjoint_decided: int = 0
    disjoint_open: int = 0


class ProjectPipelineStatus(BaseModel):
    """Vollständiger Pipeline-Status eines Projekts für die Projekt-Status-Seite."""

    project: Project
    kqr_pairs: list[KQRPairStatus]
    disjoint_total: int = 0
    disjoint_decided: int = 0
    disjoint_open: int = 0
    clustering_done: bool = False
    export_ready: bool = False  # True wenn alle offenen Einträge = 0
