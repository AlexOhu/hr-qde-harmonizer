/**
 * Nicht zugeordnete Konzepte und Integrationsentscheidungen
 * (Backend-Routen unter `/disjoint`).
 *
 * In der UI heissen diese Konzepte "nicht zugeordnet"; fachlich sind es die
 * disjunkten Mengen D1 ∪ D2 des Modells.
 */

import { request } from "./client";
import type {
  Concept,
  DisjointSummary,
  IntegrationDecision,
  IntegrationStrategy,
  StrategySuggestion,
} from "./types";

export interface PairRef {
  frameworkAId: string;
  frameworkBId: string;
}

/**
 * Konzept-IDs sind vollstaendige URIs und stehen im Pfad (`{concept_id:path}`).
 * `encodeURIComponent` ist hier zwingend: eine unkodierte URI im Pfad wuerde
 * je nach Browser/Proxy an den doppelten Schraegstrichen normalisiert.
 * Starlette dekodiert den Pfad vor dem Routing wieder, das Backend sieht also
 * die Original-URI (gegen die laufende API verifiziert).
 */
function conceptPath(conceptId: string, suffix: string): string {
  return `/disjoint/concepts/${encodeURIComponent(conceptId)}/${suffix}`;
}

/**
 * Ohne Paar: projektweite Grundmenge (ein Konzept mit Mapping in irgendeinem
 * Paar gilt als zugeordnet). Mit Paar: nur Mappings genau dieses Paares
 * zaehlen — dieselbe Unterscheidung wie im Backend.
 */
export function listUnmappedConcepts(
  projectId: string,
  pair?: PairRef,
  signal?: AbortSignal,
): Promise<Concept[]> {
  return request<Concept[]>("/disjoint/concepts", {
    params: {
      project_id: projectId,
      kqr_a_id: pair?.frameworkAId,
      kqr_b_id: pair?.frameworkBId,
    },
    timeoutMs: 60_000,
    signal,
  });
}

/** Heuristischer Vorschlag ohne LLM-Aufruf; nicht bindend (Mixed Initiative). */
export function suggestStrategy(
  projectId: string,
  conceptId: string,
  signal?: AbortSignal,
): Promise<StrategySuggestion> {
  return request<StrategySuggestion>(conceptPath(conceptId, "suggest"), {
    params: { project_id: projectId },
    signal,
  });
}

export interface DecideInput {
  strategy: IntegrationStrategy;
  justification: string;
  author: string;
  /** Nur bei `attach_to_skeleton`: Zielklasse im HR-QDE-Skelett. */
  anchor_class?: string | null;
  /** Pflicht bei `map_to_nearest`; das Backend antwortet sonst mit 400. */
  context_loss_note?: string | null;
}

/**
 * Persistiert die Integrationsentscheidung. Sie gilt konzeptweit fuer die
 * Gesamtontologie, nicht nur fuer das Paar, in dem sie getroffen wurde — eine
 * bestehende Entscheidung fuer dasselbe Konzept wird ersetzt.
 */
export function decideConcept(
  projectId: string,
  conceptId: string,
  input: DecideInput,
): Promise<IntegrationDecision> {
  return request<IntegrationDecision>(conceptPath(conceptId, "decide"), {
    method: "POST",
    params: { project_id: projectId },
    json: input,
  });
}

export function listDecisions(
  projectId: string,
  signal?: AbortSignal,
): Promise<IntegrationDecision[]> {
  return request<IntegrationDecision[]>("/disjoint/decisions", {
    params: { project_id: projectId },
    signal,
  });
}

export function getDisjointSummary(
  projectId: string,
  pair?: PairRef,
  signal?: AbortSignal,
): Promise<DisjointSummary> {
  return request<DisjointSummary>("/disjoint/summary", {
    params: {
      project_id: projectId,
      kqr_a_id: pair?.frameworkAId,
      kqr_b_id: pair?.frameworkBId,
    },
    timeoutMs: 60_000,
    signal,
  });
}
