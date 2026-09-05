/** Mutation-Hooks zum Steuern von Klassifikationslaeufen. */

import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  pauseJob,
  resetPair,
  resumeJob,
  startClassification,
  type ResetPairInput,
} from "@/api/classification";
import { queryKeys } from "@/api/queryKeys";

/**
 * Startet einen Vergleich. Derselbe Aufruf dient als Wiederholung eines
 * fehlgeschlagenen Laufs: das Backend ueberspringt bereits klassifizierte
 * Konzeptpaare, ein Neustart kostet also nur die verbliebene Arbeit.
 */
export function useStartClassification(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      frameworkAId,
      frameworkBId,
    }: {
      frameworkAId: string;
      frameworkBId: string;
    }) => startClassification(projectId, frameworkAId, frameworkBId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.jobs(projectId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.pipelineStatus(projectId) });
    },
  });
}

export function usePauseJob(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => pauseJob(projectId, jobId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.jobs(projectId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.pipelineStatus(projectId) });
    },
  });
}

/** Setzt einen pausierten oder unterbrochenen Lauf unter derselben Job-ID fort. */
export function useResumeJob(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => resumeJob(projectId, jobId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.jobs(projectId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.pipelineStatus(projectId) });
    },
  });
}

/**
 * Setzt ein Framework-Paar vollstaendig zurueck (Loeschung aller Mappings und
 * Klassifikationsergebnisse dieses Paares). Invalidiert wie
 * `useStartClassification` Jobs und Pipelinestatus, zusaetzlich die
 * Reset-Historie -- alle drei aendern sich durch einen Reset.
 */
export function useResetPair(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      frameworkAId,
      frameworkBId,
      input,
    }: {
      frameworkAId: string;
      frameworkBId: string;
      input: ResetPairInput;
    }) => resetPair(projectId, frameworkAId, frameworkBId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.jobs(projectId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.pipelineStatus(projectId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.pairResetEvents(projectId) });
    },
  });
}
