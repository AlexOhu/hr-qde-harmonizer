/**
 * Pair-Workspace: der primaere Arbeitsort fuer alles, was ein Framework-Paar
 * betrifft.
 *
 * Kopfzeile mit Paarnamen und Status, darunter Tabs fuer Übersicht, Mappings,
 * nicht zugeordnete Konzepte und Laufhistorie. Die Tabs sind echte Routen,
 * damit jeder Bereich verlinkbar bleibt.
 */

import { ArrowLeft } from "lucide-react";
import { Link, NavLink, Outlet, useOutletContext, useParams } from "react-router-dom";

import type { ClassificationJob } from "@/api/types";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorPanel, SkeletonList } from "@/components/common/states";
import { PageBody } from "@/components/layout/AppShell";
import { useProjectContext, type ProjectContext } from "@/features/projects/ProjectLayout";
import { PairStatusBadge } from "./PairStatusBadge";
import { findPair, runsForPair, type FrameworkPair } from "./status";
import { cn, formatNumber } from "@/lib/utils";

export interface PairContext extends ProjectContext {
  pair: FrameworkPair;
  /** Alle Laeufe dieses Paares, neueste zuerst. */
  runs: ClassificationJob[];
  basePath: string;
}

export function usePairContext(): PairContext {
  return useOutletContext<PairContext>();
}

export function PairLayout() {
  const projectContext = useProjectContext();
  const { frameworkAId = "", frameworkBId = "" } = useParams();

  const {
    projectId,
    pairs,
    jobs,
    isPipelineStatusPending,
    pipelineStatusError,
    refetchPipelineStatus,
  } = projectContext;

  const pair = findPair(pairs, frameworkAId, frameworkBId);
  const basePath = `/projects/${encodeURIComponent(projectId)}/pairs/${encodeURIComponent(
    frameworkAId,
  )}/${encodeURIComponent(frameworkBId)}`;

  if (isPipelineStatusPending) {
    return (
      <PageBody>
        <SkeletonList rows={4} />
      </PageBody>
    );
  }

  if (pipelineStatusError) {
    return (
      <PageBody>
        <ErrorPanel error={pipelineStatusError} onRetry={refetchPipelineStatus} />
      </PageBody>
    );
  }

  if (!pair) {
    return (
      <PageBody>
        <EmptyState
          title="Framework-Paar nicht gefunden"
          description={`Für ${frameworkAId} ↔ ${frameworkBId} gibt es in diesem Projekt keinen Vergleichslauf.`}
          action={
            <Button asChild variant="secondary">
              <Link to={`/projects/${encodeURIComponent(projectId)}`}>
                <ArrowLeft aria-hidden="true" />
                Zur Projektübersicht
              </Link>
            </Button>
          }
        />
      </PageBody>
    );
  }

  const runs = runsForPair(jobs, pair.frameworkAId, pair.frameworkBId);
  const context: PairContext = { ...projectContext, pair, runs, basePath };
  const openReview = pair.pendingReviewCount + pair.unresolvedCount;

  return (
    <div className="flex min-h-full flex-col">
      <div className="shrink-0 border-b border-border-subtle bg-surface">
        <div className="px-6 pt-4">
          <Link
            to={`/projects/${encodeURIComponent(projectId)}`}
            className="inline-flex items-center gap-1.5 text-xs text-fg-muted hover:text-fg"
          >
            <ArrowLeft className="size-3.5" aria-hidden="true" />
            Projektübersicht
          </Link>

          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="text-lg font-semibold text-fg">{pair.label}</h1>
            <PairStatusBadge lifecycle={pair.lifecycle} />
          </div>
        </div>

        <nav aria-label="Bereiche des Framework-Paars" className="mt-3 flex gap-1 px-6">
          <PairTab to={basePath} label="Übersicht" end />
          <PairTab to={`${basePath}/mappings`} label="Mappings" count={pair.mappingsCount} />
          <PairTab
            to={`${basePath}/unmapped`}
            label="Nicht zugeordnet"
            count={pair.disjointTotal}
            openCount={pair.disjointOpen}
          />
          <PairTab to={`${basePath}/runs`} label="Laufhistorie" count={runs.length} />
        </nav>
        {openReview > 0 ? <span className="sr-only">{openReview} Reviews offen</span> : null}
      </div>

      <div className="flex min-h-0 flex-1 flex-col">
        <Outlet context={context} />
      </div>
    </div>
  );
}

function PairTab({
  to,
  label,
  count,
  openCount,
  end,
}: {
  to: string;
  label: string;
  count?: number;
  /** Offene Punkte; hervorgehoben, damit Arbeit sichtbar bleibt. */
  openCount?: number;
  end?: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }: { isActive: boolean }) =>
        cn(
          "-mb-px border-b-2 px-3 py-2 text-xs font-medium transition-colors",
          isActive
            ? "border-accent text-accent"
            : "border-transparent text-fg-muted hover:text-fg",
        )
      }
    >
      {label}
      {count !== undefined ? (
        <span className="ml-1.5 tabular-nums text-fg-subtle">{formatNumber(count)}</span>
      ) : null}
      {openCount !== undefined && openCount > 0 ? (
        <span className="ml-1.5 rounded-full bg-warning-soft px-1.5 text-[0.6875rem] font-semibold tabular-nums text-warning">
          {formatNumber(openCount)}
        </span>
      ) : null}
    </NavLink>
  );
}
