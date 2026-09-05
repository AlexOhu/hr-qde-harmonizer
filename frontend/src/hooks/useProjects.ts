/**
 * Query- und Mutation-Hooks rund um Projekte.
 *
 * Nach jeder Mutation werden gezielt die betroffenen Queries invalidiert;
 * ein vollstaendiger Reload findet nie statt.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createProject,
  createSnapshot,
  deleteProject,
  forkProject,
  getPipelineStatus,
  getProject,
  listProjects,
  removeKqrFromProject,
  updateProject,
  type CreateProjectInput,
  type RemoveKqrFromProjectInput,
  type UpdateProjectInput,
} from "@/api/projects";
import { listJobs } from "@/api/classification";
import { queryKeys } from "@/api/queryKeys";
import type { ClassificationJob, PipelineStatus, Project } from "@/api/types";

export function useProjects() {
  return useQuery({
    queryKey: queryKeys.projects.list(),
    queryFn: ({ signal }) => listProjects(signal),
  });
}

export function useProject(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.project.detail(projectId ?? ""),
    queryFn: ({ signal }) => getProject(projectId!, signal),
    enabled: Boolean(projectId),
  });
}

/**
 * Solange ein Job laeuft, wird der Pipelinestatus regelmaessig nachgeladen.
 *
 * Polling ist bewusst die erste Ausbaustufe. Der Wechsel auf SSE oder
 * WebSockets berührt nur diesen Hook und `useClassificationJobs`: die
 * Komponenten lesen ausschliesslich das Query-Ergebnis und wissen nicht, wie
 * es aktuell gehalten wird.
 */
export function usePipelineStatus(projectId: string | undefined) {
  return useQuery<PipelineStatus>({
    queryKey: queryKeys.project.pipelineStatus(projectId ?? ""),
    queryFn: ({ signal }) => getPipelineStatus(projectId!, signal),
    enabled: Boolean(projectId),
    refetchInterval: (query) => {
      const hasRunningJob = query.state.data?.kqr_pairs.some(
        (pair) => pair.job_status === "running",
      );
      return hasRunningJob ? 4000 : false;
    },
    // Die Aggregation ist teuer; ein kurzer Frischezeitraum verhindert, dass
    // jeder Seitenwechsel sofort neu rechnet.
    staleTime: 2000,
  });
}

export function useClassificationJobs(projectId: string | undefined) {
  return useQuery<ClassificationJob[]>({
    queryKey: queryKeys.project.jobs(projectId ?? ""),
    queryFn: ({ signal }) => listJobs(projectId!, signal),
    enabled: Boolean(projectId),
    refetchInterval: (query) =>
      query.state.data?.some((job) => job.status === "running") ? 2000 : false,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateProjectInput) => createProject(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() });
    },
  });
}

export function useUpdateProject(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateProjectInput) => updateProject(projectId, input),
    onSuccess: (project: Project) => {
      queryClient.setQueryData(queryKeys.project.detail(projectId), project);
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.pipelineStatus(projectId) });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) => deleteProject(projectId),
    onSuccess: (_result, projectId) => {
      queryClient.removeQueries({ queryKey: queryKeys.project.all(projectId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() });
    },
  });
}

export function useCreateSnapshot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, versionLabel }: { projectId: string; versionLabel: string }) =>
      createSnapshot(projectId, versionLabel),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() });
    },
  });
}

/**
 * Entfernt ein Framework projekt-scoped. Setzt betroffene Framework-Paare
 * zurueck (vgl. useResetPair) -- invalidiert deshalb dieselben Queries,
 * zusaetzlich das Projekt selbst (kqr_ids aendert sich).
 */
export function useRemoveKqrFromProject(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ kqrId, input }: { kqrId: string; input: RemoveKqrFromProjectInput }) =>
      removeKqrFromProject(projectId, kqrId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.project.all(projectId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() });
    },
  });
}

export function useForkProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      newName,
      newKqrIds,
    }: {
      projectId: string;
      newName: string;
      newKqrIds: string[];
    }) => forkProject(projectId, newName, newKqrIds),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects.list() });
    },
  });
}
