/**
 * Laufhistorie eines Framework-Paars.
 *
 * Ein Paar kann mehrfach klassifiziert worden sein (Wiederholung nach
 * Abbruch, Fortsetzung nach Neustart). Hier stehen alle Laeufe mit Ausgang
 * und Fehlermeldung, neueste zuerst.
 */

import { History, Play, RotateCw } from "lucide-react";
import { useState } from "react";

import type { ClassificationJob } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { PageBody } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/common/states";
import { JobStatusBadge } from "@/features/pairs/PairStatusBadge";
import { StartComparisonDialog } from "@/features/pairs/StartComparisonDialog";
import { usePairContext } from "@/features/pairs/PairLayout";
import { useResumeJob } from "@/hooks/useClassification";
import { useToast } from "@/components/ui/toast";
import { formatDateTime, formatNumber } from "@/lib/utils";

export function PairRunsPage() {
  const { runs, pair, project, projectId, isReadOnly } = usePairContext();
  const [startDialogOpen, setStartDialogOpen] = useState(false);

  return (
    <PageBody>
      <div className="mb-3 flex items-center justify-between gap-4">
        <p className="text-xs text-fg-muted">
          {runs.length === 0
            ? "Für dieses Paar sind keine Läufe verzeichnet."
            : `${formatNumber(runs.length)} Läufe, neueste zuerst. Ein erneuter Start klassifiziert nur die noch offenen Konzeptpaare.`}
        </p>
        {isReadOnly ? null : (
          <Button variant="secondary" size="sm" onClick={() => setStartDialogOpen(true)}>
            <RotateCw aria-hidden="true" />
            Erneut starten
          </Button>
        )}
      </div>

      {runs.length === 0 ? (
        <EmptyState icon={<History />} title="Keine Läufe vorhanden" />
      ) : (
        <ul className="space-y-2">
          {runs.map((run) => (
            <li key={run.job_id}>
              <RunRow run={run} projectId={projectId} isReadOnly={isReadOnly} />
            </li>
          ))}
        </ul>
      )}

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

function RunRow({
  run,
  projectId,
  isReadOnly,
}: {
  run: ClassificationJob;
  projectId: string;
  isReadOnly: boolean;
}) {
  const { toast } = useToast();
  const resumeMutation = useResumeJob(projectId);
  const isResumable = run.status === "paused" || run.status === "interrupted";

  return (
    <Card className="px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <JobStatusBadge status={run.status} />
            <span className="font-mono text-[0.6875rem] text-fg-subtle">{run.job_id}</span>
          </div>
          <dl className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-fg-muted">
            <div className="flex gap-1">
              <dt>Gestartet:</dt>
              <dd>{formatDateTime(run.started_at)}</dd>
            </div>
            <div className="flex gap-1">
              <dt>Beendet:</dt>
              <dd>{formatDateTime(run.finished_at)}</dd>
            </div>
            <div className="flex gap-1">
              <dt>Fortschritt:</dt>
              <dd className="tabular-nums">
                {formatNumber(run.done_pairs)} / {formatNumber(run.total_pairs)} ({run.percent} %)
              </dd>
            </div>
          </dl>
        </div>

        {isResumable && !isReadOnly ? (
          <Button
            variant="secondary"
            size="sm"
            loading={resumeMutation.isPending}
            onClick={() =>
              resumeMutation.mutate(run.job_id, {
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
      </div>

      {run.total_pairs > 0 ? (
        <Progress
          className="mt-2.5"
          value={run.percent}
          tone={run.status === "failed" ? "danger" : run.status === "completed" ? "success" : "info"}
          label={`Lauf ${run.job_id}: ${run.percent} Prozent`}
        />
      ) : null}

      {run.error ? (
        <p className="mt-2.5 rounded-md border border-danger/25 bg-danger-soft p-2.5 text-xs break-words text-fg-muted">
          {run.error}
        </p>
      ) : null}
    </Card>
  );
}
