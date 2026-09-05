/** Query- und Mutation-Hooks der globalen Framework-Bibliothek. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteKqrGlobally,
  embedFramework,
  getFrameworkStatus,
  listFrameworks,
  uploadFramework,
  type UploadFrameworkInput,
} from "@/api/frameworks";
import { checkPreconditions } from "@/api/classification";
import { queryKeys } from "@/api/queryKeys";
import type { Framework } from "@/api/types";

export function useFrameworks() {
  return useQuery({
    queryKey: queryKeys.frameworks.list(),
    queryFn: ({ signal }) => listFrameworks(signal),
    staleTime: 10_000,
  });
}

/**
 * Detailstatus inklusive Validierungsfehlern.
 *
 * API-Gap: `validation_errors` haelt das Backend nur im Prozessspeicher
 * (`kqr_service._validation_errors`). Nach einem API-Neustart ist die Liste
 * leer, obwohl der Framework-Status weiterhin `roh` lautet. Die UI zeigt in
 * dem Fall den Status ohne Detailfehler.
 */
export function useFrameworkStatus(frameworkId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.frameworks.detail(frameworkId ?? ""),
    queryFn: ({ signal }) => getFrameworkStatus(frameworkId!, signal),
    enabled: Boolean(frameworkId) && enabled,
  });
}

export function usePreconditions() {
  return useQuery({
    queryKey: queryKeys.preconditions(),
    queryFn: ({ signal }) => checkPreconditions(signal),
    staleTime: 30_000,
  });
}

export function useUploadFramework() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UploadFrameworkInput) => uploadFramework(input),
    onSuccess: (framework: Framework) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.frameworks.list() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.frameworks.detail(framework.id) });
    },
  });
}

export function useEmbedFramework() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (frameworkId: string) => embedFramework(frameworkId),
    onSuccess: (framework: Framework) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.frameworks.list() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.frameworks.detail(framework.id) });
    },
  });
}

/**
 * Loescht ein Framework global (destruktiv). Das Backend blockiert mit 409,
 * solange irgendein Projekt es noch referenziert -- der Fehler landet
 * unveraendert bei der aufrufenden Komponente (ApiError.isConflict).
 */
export function useDeleteFrameworkGlobally() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (frameworkId: string) => deleteKqrGlobally(frameworkId),
    onSuccess: (_result, frameworkId) => {
      queryClient.removeQueries({ queryKey: queryKeys.frameworks.detail(frameworkId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.frameworks.list() });
    },
  });
}

/** Nur Frameworks mit Status `bereit` sind vergleichbar. */
export function isFrameworkReady(framework: Framework): boolean {
  return framework.status === "bereit";
}
