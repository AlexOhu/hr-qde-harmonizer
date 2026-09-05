/**
 * Projektweites Mapping-Review.
 *
 * Dieselbe Arbeitsflaeche wie im Pair-Workspace, nur ohne feste Paar-
 * Eingrenzung: offene Reviews lassen sich hier über alle Framework-Paare
 * hinweg abarbeiten.
 */

import { MappingWorkspace } from "@/features/mappings/MappingWorkspace";
import { useProjectContext } from "@/features/projects/ProjectLayout";
import { countActionableReviews, countUnresolved } from "@/features/pairs/status";
import { PageHeader } from "@/components/layout/AppShell";
import { formatNumber } from "@/lib/utils";

export function ProjectMappingsPage() {
  const { projectId, pairs, isReadOnly } = useProjectContext();

  const openReviews = countActionableReviews(pairs);
  const unresolved = countUnresolved(pairs);

  const pairOptions = pairs.map((pair) => ({
    key: pair.key,
    label: pair.label,
    frameworkAId: pair.frameworkAId,
    frameworkBId: pair.frameworkBId,
  }));

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        title="Mappings"
        description="Alle erzeugten Zuordnungen des Projekts. Einträge unterhalb der Konfidenzschwelle verlangen eine manuelle Entscheidung mit Begründung und Autor."
        meta={
          <span className="text-xs text-fg-muted">
            {openReviews > 0
              ? `${formatNumber(openReviews)} offene Reviews`
              : "Keine offenen Reviews"}
            {unresolved > 0
              ? ` · ${formatNumber(unresolved)} UNRESOLVED nur im Prüfbericht`
              : ""}
          </span>
        }
      />
      <MappingWorkspace
        projectId={projectId}
        isReadOnly={isReadOnly}
        pairOptions={pairOptions}
      />
    </div>
  );
}
