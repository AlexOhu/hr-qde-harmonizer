/** Übersicht eines Framework-Paars: Stand, Kennzahlen und offene Arbeit. */

import { ArrowRight, Pause, Play, RotateCw } from "lucide-react";
import { Link } from "react-router-dom";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardHeader, Metric } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { PageBody } from "@/components/layout/AppShell";
import { PAIR_LIFECYCLE_PRESENTATION } from "@/features/pairs/PairStatusBadge";
import { StartComparisonDialog } from "@/features/pairs/StartComparisonDialog";
import { usePairContext } from "@/features/pairs/PairLayout";
import { usePauseJob, useResumeJob } from "@/hooks/useClassification";
import { useToast } from "@/components/ui/toast";
import { ErrorPanel } from "@/components/common/states";
import { formatDateTime, formatNumber } from "@/lib/utils";

export function PairOverviewPage() {
  const { pair, runs, project, projectId, isReadOnly, basePath } = usePairContext();
  const { toast } = useToast();
  const [startDialogOpen, setStartDialogOpen] = useState(false);

  const pauseMutation = usePauseJob(projectId);
  const resumeMutation = useResumeJob(projectId);

  const latestRun = runs[0];
  const presentation = PAIR_LIFECYCLE_PRESENTATION[pair.lifecycle];
  const isRunning = pair.lifecycle === "running";
  const isResumable = pair.lifecycle === "paused" || pair.lifecycle === "interrupted";
  const canRetry = pair.lifecycle === "failed" || pair.lifecycle === "interrupted";
  // Nur was die Mapping-Ansicht auch anzeigen kann; UNRESOLVED steht als
  // eigene Kennzahl daneben (siehe countActionableReviews).
  const openReview = pair.pendingReviewCount;

  return (
    <PageBody>
      <div className="space-y-5">
        <Card>
          <CardHeader
            title="Stand des Vergleichs"
            description={presentation.hint}
            action={
              isReadOnly ? null : (
                <div className="flex items-center gap-2">
                  {isRunning && latestRun ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={pauseMutation.isPending}
                      onClick={() =>
                        pauseMutation.mutate(latestRun.job_id, {
                          onSuccess: () =>
                            toast({
                              title: "Pause angefordert",
                              description:
                                "Der Lauf hält vor dem nächsten Konzeptpaar an, nicht mitten im laufenden Aufruf.",
                            }),
                          onError: (error) =>
                            toast({
                              title: "Pausieren nicht möglich",
                              description: error instanceof Error ? error.message : undefined,
                              tone: "error",
                            }),
                        })
                      }
                    >
                      <Pause aria-hidden="true" />
                      Pausieren
                    </Button>
                  ) : null}

                  {isResumable && latestRun ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={resumeMutation.isPending}
                      onClick={() =>
                        resumeMutation.mutate(latestRun.job_id, {
                          onSuccess: () => toast({ title: "Lauf wird fortgesetzt" }),
                          onError: (error) =>
                            toast({
                              title: "Fortsetzen nicht möglich",
                              description: error instanceof Error ? error.message : undefined,
                              tone: "error",
                            }),
                        })
                      }
                    >
                      <Play aria-hidden="true" />
                      Fortsetzen
                    </Button>
                  ) : null}

                  {canRetry ? (
                    <Button variant="primary" size="sm" onClick={() => setStartDialogOpen(true)}>
                      <RotateCw aria-hidden="true" />
                      Neu starten
                    </Button>
                  ) : null}
                </div>
              )
            }
          />

          <div className="space-y-4 px-4 py-4">
            {pair.totalPairs > 0 ? (
              <div>
                <div className="mb-1.5 flex items-center justify-between text-xs">
                  <span className="text-fg-muted">Klassifizierte Konzeptpaare</span>
                  <span className="tabular-nums text-fg">
                    {formatNumber(pair.classifiedPairs)} / {formatNumber(pair.totalPairs)} (
                    {pair.percent} %)
                  </span>
                </div>
                <Progress
                  value={pair.percent}
                  tone={pair.lifecycle === "failed" ? "danger" : isRunning ? "info" : "success"}
                  label={`Klassifikationsfortschritt: ${pair.percent} Prozent`}
                />
              </div>
            ) : null}

            {latestRun?.error ? (
              <ErrorPanel
                title="Letzter Lauf ist gescheitert"
                error={new Error(latestRun.error)}
              />
            ) : null}

            <dl className="grid grid-cols-2 gap-4 text-xs sm:grid-cols-4">
              <div>
                <dt className="text-fg-muted">Framework A</dt>
                <dd className="mt-0.5 font-medium text-fg">{pair.frameworkAName}</dd>
              </div>
              <div>
                <dt className="text-fg-muted">Framework B</dt>
                <dd className="mt-0.5 font-medium text-fg">{pair.frameworkBName}</dd>
              </div>
              <div>
                <dt className="text-fg-muted">Letzter Lauf</dt>
                <dd className="mt-0.5 font-medium text-fg">
                  {formatDateTime(latestRun?.finished_at ?? latestRun?.started_at)}
                </dd>
              </div>
              <div>
                <dt className="text-fg-muted">Läufe insgesamt</dt>
                <dd className="mt-0.5 font-medium tabular-nums text-fg">
                  {formatNumber(runs.length)}
                </dd>
              </div>
            </dl>
          </div>
        </Card>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <div className="px-4 py-4">
              <Metric label="Mappings" value={formatNumber(pair.mappingsCount)} />
            </div>
          </Card>
          <Card>
            <div className="px-4 py-4">
              <Metric
                label="Review offen"
                value={formatNumber(pair.pendingReviewCount)}
                tone={pair.pendingReviewCount > 0 ? "warning" : "success"}
              />
            </div>
          </Card>
          <Card>
            <div className="px-4 py-4">
              <Metric
                label="UNRESOLVED"
                value={formatNumber(pair.unresolvedCount)}
                hint="Klassifikationen ohne Mehrheitsentscheid"
                tone={pair.unresolvedCount > 0 ? "warning" : "success"}
              />
            </div>
          </Card>
          <Card>
            <div className="px-4 py-4">
              <Metric
                label="Nicht zugeordnet"
                value={`${formatNumber(pair.disjointDecided)} / ${formatNumber(pair.disjointTotal)}`}
                hint={
                  pair.disjointOpen > 0
                    ? `${formatNumber(pair.disjointOpen)} ohne Entscheidung`
                    : "vollständig entschieden"
                }
                tone={pair.disjointOpen > 0 ? "warning" : "success"}
              />
            </div>
          </Card>
        </div>

        <Card>
          <CardHeader title="Offene Arbeit" description="Direkt zu den betroffenen Einträgen." />
          <ul className="divide-y divide-border-subtle">
            <li className="flex items-center justify-between gap-4 px-4 py-3">
              <span className="text-xs text-fg-muted">
                {openReview > 0 ? (
                  <>
                    <strong className="text-fg">{formatNumber(openReview)}</strong> Mappings warten
                    auf eine manuelle Entscheidung.
                  </>
                ) : (
                  "Alle Mappings dieses Paares sind entschieden oder automatisch akzeptiert."
                )}
              </span>
              <Button asChild variant={openReview > 0 ? "primary" : "secondary"} size="sm">
                <Link to={openReview > 0 ? `${basePath}/mappings?status=review` : `${basePath}/mappings`}>
                  Mappings
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </li>
            <li className="flex items-center justify-between gap-4 px-4 py-3">
              <span className="text-xs text-fg-muted">
                {pair.disjointOpen > 0 ? (
                  <>
                    <strong className="text-fg">{formatNumber(pair.disjointOpen)}</strong> Konzepte
                    brauchen eine Integrationsstrategie.
                  </>
                ) : (
                  "Alle nicht zugeordneten Konzepte dieses Paares sind entschieden."
                )}
              </span>
              <Button asChild variant={pair.disjointOpen > 0 ? "primary" : "secondary"} size="sm">
                <Link
                  to={
                    pair.disjointOpen > 0 ? `${basePath}/unmapped?status=open` : `${basePath}/unmapped`
                  }
                >
                  Nicht zugeordnet
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </li>
          </ul>
        </Card>
      </div>

      {startDialogOpen ? (
        <StartComparisonDialog
          project={project}
          open
          onOpenChange={setStartDialogOpen}
          initialPair={{ frameworkAId: pair.frameworkAId, frameworkBId: pair.frameworkBId }}
        />
      ) : null}
    </PageBody>
  );
}
