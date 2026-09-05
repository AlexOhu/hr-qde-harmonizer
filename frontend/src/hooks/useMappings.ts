/** Query- und Mutation-Hooks fuer Mappings und die SSSOM-Vorschau. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getMappingConfig,
  getSssomPreview,
  listMappings,
  reviewMapping,
  updateMapping,
  type MappingFilters,
  type ReviewInput,
  type UpdateMappingInput,
} from "@/api/mappings";
import { queryKeys } from "@/api/queryKeys";
import type { Mapping } from "@/api/types";

/** Auto-Accept-Schwelle (VH1.7). Immer vom Server, nie lokal gesetzt. */
export function useMappingConfig() {
  return useQuery({
    queryKey: queryKeys.mappingConfig(),
    queryFn: ({ signal }) => getMappingConfig(signal),
    staleTime: Infinity,
  });
}

export function useMappings(projectId: string | undefined, filters: MappingFilters = {}) {
  return useQuery<Mapping[]>({
    queryKey: queryKeys.project.mappings(projectId ?? "", filters),
    queryFn: ({ signal }) => listMappings(projectId!, filters, signal),
    enabled: Boolean(projectId),
    staleTime: 5_000,
  });
}

export function useUpdateMapping(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ mappingId, input }: { mappingId: string; input: UpdateMappingInput }) =>
      updateMapping(projectId, mappingId, input),
    onSuccess: () => {
      // Eine manuelle Entscheidung veraendert Konfidenz und Praedikat und
      // damit auch die Zaehler in Pipelinestatus und Exportzusammenfassung.
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.all(projectId) });
    },
  });
}

/**
 * Konjunkt/Disjunkt-Weiche fuer ein offenes Paar.
 *
 * Invalidiert denselben Projekt-Praefix wie `useUpdateMapping`: eine
 * Entscheidung veraendert Mapping-Liste, Pipelinestatus, Coverage-Bilanz und
 * — im Disjunkt-Zweig — auch die Integrationsentscheidungen.
 */
export function useReviewMapping(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ mappingId, input }: { mappingId: string; input: ReviewInput }) =>
      reviewMapping(projectId, mappingId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.all(projectId) });
    },
  });
}

export function useSssomPreview(projectId: string | undefined, limit = 10, enabled = true) {
  return useQuery({
    queryKey: queryKeys.project.sssomPreview(projectId ?? "", limit),
    queryFn: ({ signal }) => getSssomPreview(projectId!, limit, signal),
    enabled: Boolean(projectId) && enabled,
  });
}

/**
 * Ein Eintrag verlangt eine manuelle Entscheidung, wenn er noch offen ist
 * (RELATED/UNRESOLVED) oder die Konfidenzschwelle nicht erreicht. Spiegelt
 * `mapping_service.needs_review()` — die Regel selbst kommt aus dem Backend,
 * hier steht nur die Anzeigeentscheidung.
 */
export function requiresReview(mapping: Mapping, threshold: number): boolean {
  if (mapping.review_status === "open") return true;
  return mapping.mapping_source !== "manual" && mapping.mapping_confidence < threshold;
}
