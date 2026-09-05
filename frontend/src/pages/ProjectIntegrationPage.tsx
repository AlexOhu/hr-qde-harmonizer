/**
 * Projektweite Integrationsentscheidungen.
 *
 * Aggregiert nicht zugeordnete Konzepte über alle Framework-Paare hinweg,
 * damit offene Entscheidungen nicht Paar für Paar gesucht werden müssen.
 */

import { Info } from "lucide-react";

import { IntegrationWorkspace } from "@/features/integration/IntegrationWorkspace";
import { UNMAPPED_EXPLANATION } from "@/features/integration/integrationPresentation";
import { useProjectContext } from "@/features/projects/ProjectLayout";
import { PageHeader } from "@/components/layout/AppShell";
import { Tooltip } from "@/components/ui/tooltip";
import { formatNumber } from "@/lib/utils";

export function ProjectIntegrationPage() {
  const { projectId, pairs, pipelineStatus, isReadOnly } = useProjectContext();

  const pairOptions = pairs.map((pair) => ({
    key: pair.key,
    label: pair.label,
    frameworkAId: pair.frameworkAId,
    frameworkBId: pair.frameworkBId,
  }));

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        title="Integration"
        description="Konzepte ohne Zuordnung brauchen eine Entscheidung, wie sie in die harmonisierte Ontologie eingehen. Eine Entscheidung gilt konzeptweit, auch über Framework-Paare hinweg."
        meta={
          <>
            {pipelineStatus ? (
              <span className="text-xs text-fg-muted">
                {formatNumber(pipelineStatus.disjoint_decided)} von{" "}
                {formatNumber(pipelineStatus.disjoint_total)} entschieden ·{" "}
                {formatNumber(pipelineStatus.disjoint_open)} offen
              </span>
            ) : null}
            <Tooltip content={UNMAPPED_EXPLANATION}>
              <button
                type="button"
                className="inline-flex items-center gap-1 rounded text-xs text-fg-subtle hover:text-fg"
              >
                <Info className="size-3.5" aria-hidden="true" />
                Was heißt „nicht zugeordnet“?
              </button>
            </Tooltip>
          </>
        }
      />
      <IntegrationWorkspace
        projectId={projectId}
        isReadOnly={isReadOnly}
        pairOptions={pairOptions}
      />
    </div>
  );
}
