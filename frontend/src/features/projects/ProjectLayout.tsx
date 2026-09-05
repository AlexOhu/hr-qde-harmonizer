/**
 * Projektkontext.
 *
 * Laedt Projekt, Pipelinestatus und Jobliste einmal und stellt sie allen
 * Unterseiten ueber den Outlet-Kontext bereit. Die `projectId` stammt
 * ausschliesslich aus der URL; es gibt keinen globalen Anwendungszustand
 * fuer das aktive Projekt.
 */

import { useMemo } from "react";
import { Outlet, useOutletContext, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import type { ClassificationJob, PipelineStatus, Project } from "@/api/types";
import { AppShell, PageBody } from "@/components/layout/AppShell";
import { ErrorPanel, SkeletonList } from "@/components/common/states";
import { countActionableReviews, derivePairs, type FrameworkPair } from "@/features/pairs/status";
import { useClassificationJobs, usePipelineStatus, useProject } from "@/hooks/useProjects";

export interface ProjectContext {
  projectId: string;
  project: Project;
  pipelineStatus: PipelineStatus | undefined;
  pipelineStatusError: unknown;
  isPipelineStatusPending: boolean;
  refetchPipelineStatus: () => void;
  jobs: ClassificationJob[];
  pairs: FrameworkPair[];
  /** Snapshots sind schreibgeschuetzt: keine Mutation darf angeboten werden. */
  isReadOnly: boolean;
}

export function useProjectContext(): ProjectContext {
  return useOutletContext<ProjectContext>();
}

export function ProjectLayout() {
  const { projectId = "" } = useParams();

  const projectQuery = useProject(projectId);
  const pipelineQuery = usePipelineStatus(projectId);
  const jobsQuery = useClassificationJobs(projectId);

  const jobs = useMemo(() => jobsQuery.data ?? [], [jobsQuery.data]);
  const pairs = useMemo(
    () => derivePairs(pipelineQuery.data?.kqr_pairs ?? [], jobs),
    [pipelineQuery.data?.kqr_pairs, jobs],
  );

  const project = projectQuery.data;

  const openReviews = countActionableReviews(pairs);
  const openIntegrations = pipelineQuery.data?.disjoint_open ?? 0;

  if (projectQuery.isPending) {
    return (
      <AppShell>
        <PageBody>
          <SkeletonList rows={5} />
        </PageBody>
      </AppShell>
    );
  }

  if (projectQuery.isError || !project) {
    const notFound = projectQuery.error instanceof ApiError && projectQuery.error.status === 404;
    return (
      <AppShell>
        <PageBody>
          <ErrorPanel
            title={notFound ? "Projekt nicht gefunden" : undefined}
            error={
              notFound
                ? new Error(`Es gibt kein Projekt mit der ID „${projectId}“.`)
                : projectQuery.error
            }
            onRetry={notFound ? undefined : () => void projectQuery.refetch()}
          />
        </PageBody>
      </AppShell>
    );
  }

  const context: ProjectContext = {
    projectId,
    project,
    pipelineStatus: pipelineQuery.data,
    pipelineStatusError: pipelineQuery.error,
    isPipelineStatusPending: pipelineQuery.isPending,
    refetchPipelineStatus: () => void pipelineQuery.refetch(),
    jobs,
    pairs,
    isReadOnly: project.status === "snapshot",
  };

  return (
    <AppShell project={project} openReviews={openReviews} openIntegrations={openIntegrations}>
      <Outlet context={context} />
    </AppShell>
  );
}
