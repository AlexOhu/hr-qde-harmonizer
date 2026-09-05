/**
 * Frameworks dieses Projekts.
 *
 * Zeigt die referenzierten Frameworks mit Status und erlaubt das
 * projekt-scoped Entfernen (guenstig, reversibel -- das Framework bleibt in
 * der globalen Bibliothek). Der Hub laesst sich hier nicht entfernen: das
 * Backend blockiert es ohnehin (project_service.remove_kqr_from_project),
 * die Aktion wird fuer ihn deshalb gar nicht erst angeboten.
 */

import { useState } from "react";
import { Anchor, Unlink } from "lucide-react";

import type { Project } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { FrameworkStatusBadge } from "@/features/frameworks/frameworkStatus";
import { useFrameworks } from "@/hooks/useFrameworks";
import { RemoveKqrFromProjectDialog } from "./RemoveKqrFromProjectDialog";

export function ProjectFrameworksList({
  project,
  isReadOnly,
}: {
  project: Project;
  isReadOnly: boolean;
}) {
  const frameworksQuery = useFrameworks();
  const [removeTarget, setRemoveTarget] = useState<{ id: string; name: string } | null>(null);

  if (project.kqr_ids.length === 0) return null;

  return (
    <>
      <Card>
        <CardHeader
          title="Frameworks in diesem Projekt"
          description="Aus dem Projekt entfernt bleibt ein Framework in der Framework-Bibliothek erhalten und lässt sich später erneut hinzufügen."
        />
        <ul className="divide-y divide-border-subtle">
          {project.kqr_ids.map((kqrId) => {
            const framework = frameworksQuery.data?.find((item) => item.id === kqrId);
            const isHub = kqrId === project.hub_kqr_id;
            return (
              <li key={kqrId} className="flex items-center justify-between gap-4 px-4 py-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate text-sm font-medium text-fg">
                      {framework?.name ?? kqrId}
                    </span>
                    {isHub ? (
                      <Badge tone="accent" icon={<Anchor aria-hidden="true" />}>
                        Hub
                      </Badge>
                    ) : null}
                    {framework ? <FrameworkStatusBadge status={framework.status} /> : null}
                  </div>
                  <p className="mt-0.5 truncate font-mono text-[0.6875rem] text-fg-subtle">
                    {kqrId}
                  </p>
                </div>
                {!isReadOnly && !isHub ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setRemoveTarget({ id: kqrId, name: framework?.name ?? kqrId })}
                  >
                    <Unlink aria-hidden="true" />
                    Aus Projekt entfernen
                  </Button>
                ) : null}
              </li>
            );
          })}
        </ul>
      </Card>

      {removeTarget ? (
        <RemoveKqrFromProjectDialog
          projectId={project.project_id}
          kqrId={removeTarget.id}
          kqrName={removeTarget.name}
          open
          onOpenChange={(open) => {
            if (!open) setRemoveTarget(null);
          }}
        />
      ) : null}
    </>
  );
}
