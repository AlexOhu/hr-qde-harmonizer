/**
 * Query- und Mutation-Hooks fuer nicht zugeordnete Konzepte und
 * Integrationsentscheidungen.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  decideConcept,
  getDisjointSummary,
  listDecisions,
  listUnmappedConcepts,
  suggestStrategy,
  type DecideInput,
  type PairRef,
} from "@/api/disjoint";
import { queryKeys } from "@/api/queryKeys";
import type { Concept, IntegrationDecision } from "@/api/types";

function pairParam(pair?: PairRef) {
  return pair ? { a: pair.frameworkAId, b: pair.frameworkBId } : undefined;
}

export function useUnmappedConcepts(projectId: string | undefined, pair?: PairRef) {
  return useQuery<Concept[]>({
    queryKey: queryKeys.project.disjointConcepts(projectId ?? "", pairParam(pair)),
    queryFn: ({ signal }) => listUnmappedConcepts(projectId!, pair, signal),
    enabled: Boolean(projectId),
    staleTime: 5_000,
  });
}

export function useIntegrationDecisions(projectId: string | undefined) {
  return useQuery<IntegrationDecision[]>({
    queryKey: queryKeys.project.disjointDecisions(projectId ?? ""),
    queryFn: ({ signal }) => listDecisions(projectId!, signal),
    enabled: Boolean(projectId),
    staleTime: 5_000,
  });
}

export function useDisjointSummary(projectId: string | undefined, pair?: PairRef) {
  return useQuery({
    queryKey: queryKeys.project.disjointSummary(projectId ?? "", pairParam(pair)),
    queryFn: ({ signal }) => getDisjointSummary(projectId!, pair, signal),
    enabled: Boolean(projectId),
  });
}

/**
 * Heuristischer Strategievorschlag des Systems (Mixed Initiative). Wird nur
 * fuer das gerade ausgewaehlte Konzept geladen, nicht fuer die ganze Liste —
 * es ist ein Request pro Konzept.
 */
export function useStrategySuggestion(
  projectId: string | undefined,
  conceptId: string | undefined,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.project.strategySuggestion(projectId ?? "", conceptId ?? ""),
    queryFn: ({ signal }) => suggestStrategy(projectId!, conceptId!, signal),
    enabled: Boolean(projectId) && Boolean(conceptId) && enabled,
    staleTime: 60_000,
  });
}

export function useDecideConcept(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ conceptId, input }: { conceptId: string; input: DecideInput }) =>
      decideConcept(projectId, conceptId, input),
    onSuccess: () => {
      // Die Entscheidung gilt konzeptweit und veraendert damit auch die
      // Zaehler anderer Paare sowie die Export-Readiness.
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.all(projectId) });
    },
  });
}

/** Index concept_id -> Entscheidung, fuer die Master-Detail-Liste. */
export function indexDecisions(
  decisions: IntegrationDecision[] | undefined,
): Map<string, IntegrationDecision> {
  return new Map((decisions ?? []).map((decision) => [decision.concept_id, decision]));
}
