/**
 * TypeScript-Spiegel der Pydantic-Schemas aus `app/models/schemas.py` sowie
 * der Dict-Rueckgaben einzelner Routen, die kein `response_model` deklarieren.
 *
 * Regel: hier stehen ausschliesslich Felder, die das Backend tatsaechlich
 * liefert. Abgeleitete Anzeigebegriffe (z. B. der Lifecycle-Status eines
 * Framework-Paars) leben nicht hier, sondern in `src/features/pairs/status.ts`
 * und sind dort als Ableitung gekennzeichnet.
 */

// ── Frameworks (Backend: KQR) ────────────────────────────────────────────

/** `KQRStatus` — roh -> formalisiert -> bereit. */
export type FrameworkStatus = "roh" | "formalisiert" | "bereit";

/** `KQR` aus schemas.py. In der UI durchgehend "Framework"/"Rahmenwerk". */
export interface Framework {
  id: string;
  name: string;
  namespace_uri: string;
  source_format: string;
  status: FrameworkStatus;
  concept_count: number | null;
  is_hub: boolean;
}

/** `GET /kqr/{id}/status` */
export interface FrameworkStatusDetail {
  kqr: Framework;
  validation_errors: string[];
}

// ── Projekte ─────────────────────────────────────────────────────────────

export type ProjectStatus = "active" | "snapshot";

/** `Project` aus schemas.py. */
export interface Project {
  project_id: string;
  name: string;
  description: string | null;
  kqr_ids: string[];
  hub_kqr_id: string | null;
  created_at: string;
  updated_at: string;
  status: ProjectStatus;
  parent_project_id: string | null;
  version_label: string | null;
}

/**
 * `KQRPairStatus` aus schemas.py.
 *
 * Achtung: `get_pipeline_status()` erzeugt einen Eintrag pro Job, nicht pro
 * Paar. Ein Paar mit mehreren Laeufen erscheint daher mehrfach. Die Metriken
 * (mappings_count, disjoint_*, ...) sind ueber diese Duplikate identisch,
 * lediglich job_id/job_status/Fortschritt unterscheiden sich. Die
 * Zusammenfuehrung passiert in `features/pairs/status.ts`.
 */
export interface PairStatus {
  kqr_a_id: string;
  kqr_a_name: string;
  kqr_b_id: string;
  kqr_b_name: string;
  job_status: JobStatus | null;
  job_id: string | null;
  /** Nur bei job_status="failed" gesetzt; ein "interrupted" Job hat keine Ausnahme erlebt. */
  error: string | null;
  total_pairs: number;
  classified_pairs: number;
  mappings_count: number;
  pending_review_count: number;
  unresolved_count: number;
  disjoint_total: number;
  disjoint_decided: number;
  disjoint_open: number;
}

/** `ProjectPipelineStatus` aus schemas.py. */
export interface PipelineStatus {
  project: Project;
  kqr_pairs: PairStatus[];
  disjoint_total: number;
  disjoint_decided: number;
  disjoint_open: number;
  clustering_done: boolean;
  export_ready: boolean;
}

// ── Klassifikation ───────────────────────────────────────────────────────

export type JobStatus = "running" | "completed" | "failed" | "interrupted" | "paused";

/**
 * Rueckgabe von `GET /classification/` und `GET /classification/{id}/progress`.
 * `started_at`/`finished_at` wurden fuer die Run-Historie ergaenzt und sind
 * bei Jobs aus der Zeit davor `null`.
 */
export interface ClassificationJob {
  job_id: string;
  kqr_a_id: string;
  kqr_b_id: string;
  status: JobStatus;
  done_pairs: number;
  total_pairs: number;
  error: string | null;
  percent: number;
  started_at: string | null;
  finished_at: string | null;
}

/** `GET /classification/preconditions` */
export interface Preconditions {
  neo4j_reachable: boolean;
  llm_configured: boolean;
  llm_providers: string;
}

/**
 * Rueckgabe von `POST /classification/pair/reset`. Zaehlt, was der Reset
 * entfernt bzw. bereits vorgefunden hat -- keine der drei Zahlen ist vom
 * Frontend ableitbar, sie stammen ausschliesslich vom Server.
 */
export interface PairResetResult {
  removed_mappings: number;
  removed_classification_results: number;
  /** Betroffene, aber bewusst NICHT veraenderte Integrationsentscheidungen. */
  affected_disjoint_decisions: number;
}

/**
 * `PairResetEvent` aus schemas.py. Protokolliert einen Paar-Reset
 * (Accountability-Prinzip), analog zu `IntegrationDecision`.
 */
export interface PairResetEvent extends PairResetResult {
  event_id: string;
  kqr_a_id: string;
  kqr_b_id: string;
  justification: string;
  author: string;
  created_at: string;
}

/**
 * Rueckgabe von `DELETE /projects/{project_id}/kqr/{kqr_id}` (projekt-scoped
 * Entfernung, guenstig und reversibel). `was_hub` ist stets `false`, weil das
 * Entfernen des Hub-Frameworks serverseitig blockiert wird.
 */
export interface KqrRemovalResult {
  removed_pairs: number;
  was_hub: boolean;
}

// ── Mappings ─────────────────────────────────────────────────────────────

/**
 * `MappingJustification` aus schemas.py: SEMAPV-Verfahrensnachweis. Ersetzt
 * das entfernte Feld `match_type`. Ein Reviewer erkennt daran, ob ein Eintrag
 * algorithmisch erzeugt oder bereits menschlich bestaetigt wurde.
 */
export const MAPPING_JUSTIFICATIONS = [
  "semapv:StructuralMatching",
  "semapv:LLMBasedMatching",
  "semapv:MappingReview",
] as const;

export type MappingJustification = (typeof MAPPING_JUSTIFICATIONS)[number];

export type MappingSource = "algorithmic" | "manual";

/**
 * `ReviewStatus` aus schemas.py. `open` sind Paare, die auf eine manuelle
 * Entscheidung warten (RELATED oder ohne LLM-Mehrheitsentscheid); `conjunct`
 * und `disjunct` sind die beiden Ausgaenge der Review-Weiche.
 */
export type ReviewStatus = "open" | "conjunct" | "disjunct";

/**
 * `MappingPredicate` aus schemas.py: das eine Mapping-Relationsvokabular
 * (SKOS-Mapping-Praedikate als CURIE). `skos:closeMatch` erzeugt die
 * LLM-Klassifikation nie, ein Reviewer kann es aber vergeben.
 */
export const MAPPING_PREDICATES = [
  "skos:exactMatch",
  "skos:closeMatch",
  "skos:broadMatch",
  "skos:narrowMatch",
  "skos:relatedMatch",
] as const;

export type MappingPredicate = (typeof MAPPING_PREDICATES)[number];

/** `Mapping` aus schemas.py. */
export interface Mapping {
  mapping_id: string;
  subject_id: string;
  subject_label: string;
  subject_kqr_id: string | null;
  object_id: string;
  object_label: string;
  object_kqr_id: string | null;
  /**
   * `null` genau bei einem offenen Paar ohne LLM-Mehrheitsentscheid: es
   * bekommt erst im Review ein Praedikat. Ein offenes RELATED traegt
   * `skos:relatedMatch`.
   */
  predicate_id: MappingPredicate | null;
  mapping_confidence: number;
  mapping_tool: string;
  mapping_justification: MappingJustification;
  mapping_source: MappingSource;
  author: string | null;
  created_at: string;
  justification: string | null;
  review_status: ReviewStatus;
  context_loss_note: string | null;
}

/** `GET /mappings/config` — serverseitige Auto-Accept-Schwelle (VH1.7). */
export interface MappingConfig {
  mapping_confidence_threshold: number;
}

/** `GET /mappings/sssom-preview` */
export interface SssomPreview {
  total_count: number;
  fields: string[];
  sample: Record<string, string | number | null>[];
}

// ── Disjunkte / nicht zugeordnete Konzepte ───────────────────────────────

/** `Concept` aus schemas.py. */
export interface Concept {
  uri: string;
  kqr_id: string;
  pref_label: string;
  definition: string | null;
  broader: string[];
  narrower: string[];
}

export const INTEGRATION_STRATEGIES = [
  "own_class",
  "attach_to_skeleton",
  "map_to_nearest",
  "out_of_scope",
] as const;

export type IntegrationStrategy = (typeof INTEGRATION_STRATEGIES)[number];

/** `DisjointConceptDecision` aus schemas.py. */
export interface IntegrationDecision {
  decision_id: string;
  concept_id: string;
  concept_label: string;
  kqr_id: string;
  strategy: IntegrationStrategy;
  anchor_class: string | null;
  context_loss_note: string | null;
  justification: string;
  author: string;
  created_at: string;
}

/** `GET /disjoint/summary` (projektweit oder paarbezogen). */
export interface DisjointSummary {
  total_disjoint: number;
  decided: number;
  open: number;
  /** Zaehler je Strategiewert; Schluessel sind die Werte aus INTEGRATION_STRATEGIES. */
  by_strategy: Record<IntegrationStrategy, number>;
}

/** `GET /disjoint/concepts/{id}/suggest` */
export interface StrategySuggestion {
  concept_id: string;
  suggested_strategy: IntegrationStrategy;
}

// ── Export ───────────────────────────────────────────────────────────────

/**
 * `GET /export/summary` — Gatekeeping-Zaehler und Coverage-Bilanz vor dem
 * Export.
 *
 * Der Nenner `coverage_total` ist K vereinigt C_conf und enthaelt
 * ausdruecklich die noch offenen Reviews. `open_review_count` ist die
 * Differenz zu `coverage_resolved`, vom Backend redundant mitgeliefert, damit
 * die Oberflaeche "wie viel ist offen" nicht aus zwei Zahlen ableiten muss.
 */
export interface ExportSummary {
  /** Offene Paare ohne LLM-Mehrheitsentscheid (`predicate_id = null`). */
  no_consensus_pairs: number;
  related_pairs: number;
  low_confidence_mappings: number;
  total_open: number;
  disjoint_open: number;
  coverage_resolved: number;
  coverage_total: number;
  coverage_ratio: number;
  open_review_count: number;
}

/** `ClusterResult` aus schemas.py. `cluster_id === -1` ist Noise. */
export interface ClusterResult {
  cluster_id: number;
  concept_uris: string[];
  auto_label: string;
  llm_label: string | null;
  centroid_uri: string | null;
}

export type OntologyFormat = "turtle" | "xml" | "json-ld";

/** Ergebnis eines Datei-Downloads ueber den API-Client. */
export interface DownloadedFile {
  blob: Blob;
  filename: string;
}
