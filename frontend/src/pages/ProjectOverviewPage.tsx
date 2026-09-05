/**
 * Projektuebersicht — das Dashboard eines Projekts.
 *
 * Beantwortet drei Fragen: Wo steht das Projekt? Welche Arbeit ist offen?
 * Was ist als Naechstes zu tun?
 */

import { useState } from "react";
import { Archive, GitCompare, Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { AppShell, PageBody, PageHeader } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, Metric } from "@/components/ui/card";
import { EmptyState, ErrorPanel, SkeletonList } from "@/components/common/states";
import { PairTable } from "@/features/pairs/PairTable";
import { ResetPairDialog } from "@/features/pairs/ResetPairDialog";
import { StartComparisonDialog } from "@/features/pairs/StartComparisonDialog";
import { ProjectFrameworksList } from "@/features/projects/ProjectFrameworksList";
import { useProjectContext } from "@/features/projects/ProjectLayout";
import { countActionableReviews, countUnresolved, type FrameworkPair } from "@/features/pairs/status";
import { formatNumber, pluralize } from "@/lib/utils";

export function ProjectOverviewPage() {
  const {
    projectId,
    project,
    pipelineStatus,
    pipelineStatusError,
    isPipelineStatusPending,
    refetchPipelineStatus,
    pairs,
    isReadOnly,
  } = useProjectContext();

  const [startDialog, setStartDialog] = useState<{
    open: boolean;
    initialPair?: { frameworkAId: string; frameworkBId: string };
  }>({ open: false });
  const [resetDialogPair, setResetDialogPair] = useState<FrameworkPair | null>(null);

  function retryPair(pair: FrameworkPair) {
    setStartDialog({
      open: true,
      initialPair: { frameworkAId: pair.frameworkAId, frameworkBId: pair.frameworkBId },
    });
  }

  const runningCount = pairs.filter((pair) => pair.lifecycle === "running").length;
  const openReviews = countActionableReviews(pairs);
  const unresolved = countUnresolved(pairs);
  const openIntegrations = pipelineStatus?.disjoint_open ?? 0;

  return (
    <>
      <PageHeader
        title={project.name}
        description={project.description ?? undefined}
        meta={
          <>
            {isReadOnly ? (
              <Badge tone="neutral" icon={<Archive aria-hidden="true" />}>
                Snapshot · schreibgeschützt
              </Badge>
            ) : (
              <Badge tone="success">Aktiv</Badge>
            )}
            <span className="text-xs text-fg-muted">
              {project.kqr_ids.length}{" "}
              {pluralize(project.kqr_ids.length, "Framework", "Frameworks")} · {pairs.length}{" "}
              {pluralize(pairs.length, "Vergleich", "Vergleiche")}
            </span>
            {project.version_label ? (
              <span className="text-xs text-fg-subtle">{project.version_label}</span>
            ) : null}
          </>
        }
      />

      <PageBody>
        {isReadOnly ? (
          <div
            role="status"
            className="mb-4 flex items-start gap-2.5 rounded-lg border border-border-subtle bg-surface-muted p-3"
          >
            <Archive className="mt-0.5 size-4 shrink-0 text-fg-muted" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-fg">Schreibgeschützter Snapshot</p>
              <p className="mt-1 text-xs text-fg-muted">
                Dieser Snapshot dokumentiert einen eingefrorenen Projektstand. Reviews, Vergleiche
                und Clustering sind nicht änderbar; Exporte bleiben möglich. Um daran
                weiterzuarbeiten, leiten Sie den Snapshot in der Projektübersicht ab (Fork).
              </p>
            </div>
          </div>
        ) : null}

        {pipelineStatusError ? (
          <ErrorPanel
            error={pipelineStatusError}
            onRetry={refetchPipelineStatus}
            className="mb-4"
          />
        ) : null}

        <section aria-labelledby="overall-progress" className="mb-5">
          <h2 id="overall-progress" className="sr-only">
            Operative Situation
          </h2>
          <Card>
            <div className="grid grid-cols-1 gap-6 px-4 py-4 sm:grid-cols-3">
              <Metric label="Laufende Vergleiche" value={formatNumber(runningCount)} />
              <Metric
                label="Offene Reviews"
                value={formatNumber(openReviews)}
                hint={
                  unresolved > 0
                    ? `zusätzlich ${formatNumber(unresolved)} nicht auflösbare Fälle (UNRESOLVED) nur im Prüfbericht`
                    : undefined
                }
                tone={openReviews > 0 ? "default" : "success"}
              />
              <Metric
                label="Offene Integrationsentscheidungen"
                value={formatNumber(openIntegrations)}
                hint={
                  pipelineStatus
                    ? `${formatNumber(pipelineStatus.disjoint_decided)} von ${formatNumber(pipelineStatus.disjoint_total)} entschieden`
                    : undefined
                }
                tone={openIntegrations > 0 ? "default" : "success"}
              />
            </div>
          </Card>
        </section>

        <section aria-labelledby="project-frameworks-heading" className="mb-5">
          <h2 id="project-frameworks-heading" className="sr-only">
            Frameworks in diesem Projekt
          </h2>
          <ProjectFrameworksList project={project} isReadOnly={isReadOnly} />
        </section>

        <section aria-labelledby="pairs-heading">
          <div className="mb-2.5 flex items-start justify-between gap-4">
            <div>
              <h2 id="pairs-heading" className="text-sm font-semibold text-fg">
                Framework-Vergleiche
              </h2>
              <p className="mt-0.5 text-xs text-fg-muted">
                Vergleichsstatus und offene Arbeit zwischen den Frameworks dieses Projekts.
              </p>
            </div>
            {isReadOnly ? null : (
              <Button variant="primary" onClick={() => setStartDialog({ open: true })}>
                <Plus aria-hidden="true" />
                Vergleich hinzufügen
              </Button>
            )}
          </div>

          {isPipelineStatusPending ? <SkeletonList rows={3} /> : null}

          {!isPipelineStatusPending && pairs.length === 0 ? (
            <EmptyState
              icon={<GitCompare />}
              title="Noch keine Frameworks verglichen"
              description={
                isReadOnly
                  ? "Dieser Snapshot enthält keine Vergleichsläufe."
                  : "Starten Sie einen Vergleich zwischen zwei Frameworks dieses Projekts. Der Vergleich erscheint danach hier mit seinem Fortschritt."
              }
              action={
                isReadOnly ? null : (
                  <Button variant="primary" onClick={() => setStartDialog({ open: true })}>
                    <Plus aria-hidden="true" />
                    Vergleich hinzufügen
                  </Button>
                )
              }
            />
          ) : null}

          {pairs.length > 0 ? (
            <PairTable
              projectId={projectId}
              pairs={pairs}
              onRetry={retryPair}
              onReset={setResetDialogPair}
              isReadOnly={isReadOnly}
            />
          ) : null}
        </section>

        {openReviews > 0 || openIntegrations > 0 ? (
          <section aria-labelledby="next-steps" className="mt-5">
            <Card>
              <CardHeader
                title="Nächste Schritte"
                description="Offene Arbeit über alle Framework-Vergleiche hinweg."
              />
              <ul className="divide-y divide-border-subtle">
                {openReviews > 0 ? (
                  <li className="flex items-center justify-between gap-4 px-4 py-3">
                    <span className="text-xs text-fg-muted">
                      <strong className="text-fg">{formatNumber(openReviews)}</strong>{" "}
                      {pluralize(openReviews, "Mapping benötigt", "Mappings benötigen")} eine
                      manuelle Entscheidung.
                    </span>
                    <Button asChild variant="secondary" size="sm">
                      <Link to={`/projects/${encodeURIComponent(projectId)}/mappings?status=review`}>
                        Mappings prüfen
                      </Link>
                    </Button>
                  </li>
                ) : null}
                {openIntegrations > 0 ? (
                  <li className="flex items-center justify-between gap-4 px-4 py-3">
                    <span className="text-xs text-fg-muted">
                      <strong className="text-fg">{formatNumber(openIntegrations)}</strong>{" "}
                      {pluralize(openIntegrations, "Konzept braucht", "Konzepte brauchen")} eine
                      Integrationsentscheidung.
                    </span>
                    <Button asChild variant="secondary" size="sm">
                      <Link
                        to={`/projects/${encodeURIComponent(projectId)}/integration?status=open`}
                      >
                        Konzepte klären
                      </Link>
                    </Button>
                  </li>
                ) : null}
              </ul>
            </Card>
          </section>
        ) : null}
      </PageBody>

      {startDialog.open ? (
        <StartComparisonDialog
          project={project}
          open
          onOpenChange={(open) => setStartDialog((current) => ({ ...current, open }))}
          initialPair={startDialog.initialPair}
        />
      ) : null}

      {resetDialogPair ? (
        <ResetPairDialog
          projectId={projectId}
          pair={resetDialogPair}
          open
          onOpenChange={(open) => {
            if (!open) setResetDialogPair(null);
          }}
        />
      ) : null}
    </>
  );
}

/** Fallback, falls die Uebersicht ausserhalb des Projektkontexts landet. */
export function ProjectOverviewFallback() {
  return (
    <AppShell>
      <PageBody>
        <EmptyState title="Kein Projektkontext" />
      </PageBody>
    </AppShell>
  );
}
