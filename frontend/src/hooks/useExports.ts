/** Query- und Mutation-Hooks fuer Clustering und Exportartefakte. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { saveFile } from "@/api/client";
import {
  exportAuditReport,
  exportOntology,
  exportSssom,
  getClusters,
  getExportSummary,
  runClustering,
} from "@/api/exports";
import { queryKeys } from "@/api/queryKeys";
import type { OntologyFormat } from "@/api/types";

export function useExportSummary(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.project.exportSummary(projectId ?? ""),
    queryFn: ({ signal }) => getExportSummary(projectId!, signal),
    enabled: Boolean(projectId),
  });
}

export function useClusters(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.project.clusters(projectId ?? ""),
    queryFn: ({ signal }) => getClusters(projectId!, signal),
    enabled: Boolean(projectId),
  });
}

/**
 * HDBSCAN laeuft synchron im Request, nicht als Hintergrundjob — der Aufruf
 * kann bei grossen Embedding-Raeumen mehrere Minuten dauern. Die uebrige UI
 * bleibt waehrenddessen bedienbar, weil nur diese Mutation blockiert.
 */
export function useRunClustering(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (frameworkIds: string[]) => runClustering(projectId, frameworkIds),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.clusters(projectId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.pipelineStatus(projectId) });
    },
  });
}

/** Laedt die Ontologie herunter; blockiert serverseitig ohne Clustering (409). */
export function useExportOntology(projectId: string) {
  return useMutation({
    mutationFn: async (format: OntologyFormat) => {
      saveFile(await exportOntology(projectId, format));
    },
  });
}

export function useExportSssom(projectId: string) {
  return useMutation({
    mutationFn: async () => {
      saveFile(await exportSssom(projectId));
    },
  });
}

export function useExportAuditReport(projectId: string) {
  return useMutation({
    mutationFn: async () => {
      saveFile(await exportAuditReport(projectId));
    },
  });
}
