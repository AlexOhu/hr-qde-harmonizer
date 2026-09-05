/** Mappings und SSSOM-Vorschau (Backend-Routen unter `/mappings`). */

import { request } from "./client";
import type {
  IntegrationStrategy,
  Mapping,
  MappingConfig,
  MappingPredicate,
  ReviewStatus,
  SssomPreview,
} from "./types";

/**
 * Serverseitig unterstuetzte Filter.
 *
 * API-Gap: Volltextsuche, Sortierung und Paginierung kennt `GET /mappings/`
 * nicht. Freitextsuche laeuft daher clientseitig auf der bereits geladenen
 * Paarmenge (siehe `features/mappings/useMappingList.ts`).
 */
export interface MappingFilters {
  onlyManualReview?: boolean;
  minConfidence?: number;
  frameworkAId?: string;
  frameworkBId?: string;
  reviewStatus?: ReviewStatus;
}

export function listMappings(
  projectId: string,
  filters: MappingFilters = {},
  signal?: AbortSignal,
): Promise<Mapping[]> {
  return request<Mapping[]>("/mappings/", {
    params: {
      project_id: projectId,
      only_manual_review: filters.onlyManualReview ?? false,
      min_confidence: filters.minConfidence,
      kqr_a_id: filters.frameworkAId,
      kqr_b_id: filters.frameworkBId,
      review_status: filters.reviewStatus,
    },
    timeoutMs: 60_000,
    signal,
  });
}

/** Auto-Accept-Schwelle (VH1.7). Kommt vom Server, wird nie lokal gesetzt. */
export function getMappingConfig(signal?: AbortSignal): Promise<MappingConfig> {
  return request<MappingConfig>("/mappings/config", { signal });
}

export interface UpdateMappingInput {
  /** MappingPredicate-CURIE. Alle fuenf sind waehlbar. */
  predicate: MappingPredicate;
  justification: string;
  author: string;
}

/**
 * Manuelle Korrektur eines bereits entschiedenen oder schwach belegten
 * Mappings. Das Backend setzt dabei `mapping_source` auf `manual` und
 * `mapping_confidence` auf 1.0 — eine bestaetigte menschliche Entscheidung
 * gilt als maximal sicher — und schliesst den Review ab (`conjunct`), auch
 * bei `skos:relatedMatch`.
 */
export function updateMapping(
  projectId: string,
  mappingId: string,
  input: UpdateMappingInput,
): Promise<Mapping> {
  return request<Mapping>(`/mappings/${encodeURIComponent(mappingId)}`, {
    method: "PUT",
    params: { project_id: projectId },
    json: input,
  });
}

/**
 * Nutzlast der Konjunkt/Disjunkt-Weiche. Die beiden Zweige sind ein
 * diskriminiertes Union, damit der Compiler eine Disjunkt-Entscheidung ohne
 * Strategie gar nicht erst zulaesst.
 */
export type ReviewInput =
  | {
      decision: "conjunct";
      predicate: MappingPredicate;
      confidence?: number;
      justification?: string;
      author?: string;
    }
  | {
      decision: "disjunct";
      strategy: IntegrationStrategy;
      /** Pflicht bei `map_to_nearest`; das Backend antwortet sonst mit 400. */
      context_loss_note?: string;
      justification?: string;
      author?: string;
    };

/**
 * Entscheidet ein offenes Paar (RELATED oder ohne LLM-Mehrheitsentscheid).
 *
 * Konjunkt finalisiert das Mapping mit dem gewaehlten Praedikat; disjunkt
 * gibt dem Subjektkonzept eine Integrationsstrategie. Beide Wege setzen
 * `mapping_justification` serverseitig auf `semapv:MappingReview` — die
 * Oberflaeche leitet das nicht selbst ab.
 */
export function reviewMapping(
  projectId: string,
  mappingId: string,
  input: ReviewInput,
): Promise<Mapping> {
  return request<Mapping>(`/mappings/${encodeURIComponent(mappingId)}/review`, {
    method: "PUT",
    params: { project_id: projectId },
    json: input,
  });
}

export function getSssomPreview(
  projectId: string,
  limit = 5,
  signal?: AbortSignal,
): Promise<SssomPreview> {
  return request<SssomPreview>("/mappings/sssom-preview", {
    params: { project_id: projectId, limit },
    signal,
  });
}
