/**
 * Projektuebersicht — der globale Einstiegspunkt.
 *
 * Primaere Aktion je Zeile ist „Öffnen“. Alles Weitere (Umbenennen,
 * Snapshot, Fork, Löschen) sitzt im Kontextmenue der jeweiligen Zeile, damit
 * die Liste lesbar bleibt.
 */

import { useState } from "react";
import { Archive, Camera, FolderKanban, GitFork, MoreHorizontal, Pencil, Plus, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";

import type { Project } from "@/api/types";
import { AppShell, PageBody, PageHeader } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState, ErrorPanel, SkeletonList } from "@/components/common/states";
import {
  CreateProjectDialog,
  DeleteProjectDialog,
  ForkProjectDialog,
  RenameProjectDialog,
  SnapshotDialog,
} from "@/features/projects/ProjectDialogs";
import { useProjects } from "@/hooks/useProjects";
import { formatDate, pluralize } from "@/lib/utils";

type DialogKind = "rename" | "snapshot" | "fork" | "delete";

export function ProjectsPage() {
  const projectsQuery = useProjects();
  const [createOpen, setCreateOpen] = useState(false);
  const [activeDialog, setActiveDialog] = useState<{ kind: DialogKind; project: Project } | null>(
    null,
  );

  const projects = projectsQuery.data ?? [];

  return (
    <AppShell>
      <PageHeader
        title="Projekte"
        description="Ein Projekt ist der Arbeitskontext: es referenziert Frameworks und enthält alle daraus entstehenden Mappings, Entscheidungen und Exporte."
        actions={
          <Button variant="primary" onClick={() => setCreateOpen(true)}>
            <Plus aria-hidden="true" />
            Neues Projekt
          </Button>
        }
      />

      <PageBody>
        {projectsQuery.isPending ? <SkeletonList rows={4} /> : null}

        {projectsQuery.isError ? (
          <ErrorPanel error={projectsQuery.error} onRetry={() => void projectsQuery.refetch()} />
        ) : null}

        {projectsQuery.isSuccess && projects.length === 0 ? (
          <EmptyState
            icon={<FolderKanban />}
            title="Noch kein Projekt vorhanden"
            description="Legen Sie ein Projekt an und wählen Sie die Frameworks aus, die miteinander harmonisiert werden sollen."
            action={
              <Button variant="primary" onClick={() => setCreateOpen(true)}>
                <Plus aria-hidden="true" />
                Neues Projekt
              </Button>
            }
          />
        ) : null}

        {projects.length > 0 ? (
          <ul className="space-y-2">
            {projects.map((project) => (
              <li key={project.project_id}>
                <ProjectRow
                  project={project}
                  onAction={(kind) => setActiveDialog({ kind, project })}
                />
              </li>
            ))}
          </ul>
        ) : null}
      </PageBody>

      {createOpen ? <CreateProjectDialog open onOpenChange={setCreateOpen} /> : null}

      {activeDialog?.kind === "rename" ? (
        <RenameProjectDialog
          project={activeDialog.project}
          open
          onOpenChange={(open) => !open && setActiveDialog(null)}
        />
      ) : null}
      {activeDialog?.kind === "snapshot" ? (
        <SnapshotDialog
          project={activeDialog.project}
          open
          onOpenChange={(open) => !open && setActiveDialog(null)}
        />
      ) : null}
      {activeDialog?.kind === "fork" ? (
        <ForkProjectDialog
          project={activeDialog.project}
          open
          onOpenChange={(open) => !open && setActiveDialog(null)}
        />
      ) : null}
      {activeDialog?.kind === "delete" ? (
        <DeleteProjectDialog
          project={activeDialog.project}
          open
          onOpenChange={(open) => !open && setActiveDialog(null)}
        />
      ) : null}
    </AppShell>
  );
}

function ProjectRow({
  project,
  onAction,
}: {
  project: Project;
  onAction: (kind: DialogKind) => void;
}) {
  const isSnapshot = project.status === "snapshot";
  const frameworkCount = project.kqr_ids.length;

  return (
    <Card className="flex flex-wrap items-center gap-4 px-4 py-3 transition-colors hover:border-border-strong">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={`/projects/${encodeURIComponent(project.project_id)}`}
            className="truncate text-sm font-semibold text-fg hover:text-accent hover:underline"
          >
            {project.name}
          </Link>
          {isSnapshot ? (
            <Badge tone="neutral" icon={<Archive aria-hidden="true" />}>
              Snapshot{project.version_label ? ` · ${project.version_label}` : ""}
            </Badge>
          ) : (
            <Badge tone="success">Aktiv</Badge>
          )}
        </div>

        {project.description ? (
          <p className="mt-1 line-clamp-2 max-w-2xl text-xs text-fg-muted">{project.description}</p>
        ) : null}

        <dl className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-subtle">
          <div className="flex gap-1">
            <dt className="sr-only">Frameworks</dt>
            <dd>
              {frameworkCount} {pluralize(frameworkCount, "Framework", "Frameworks")}
            </dd>
          </div>
          <div className="flex gap-1">
            <dt>Zuletzt bearbeitet:</dt>
            <dd>{formatDate(project.updated_at)}</dd>
          </div>
          <div className="flex gap-1">
            <dt>Angelegt:</dt>
            <dd>{formatDate(project.created_at)}</dd>
          </div>
        </dl>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Button asChild variant="primary" size="sm">
          <Link to={`/projects/${encodeURIComponent(project.project_id)}`}>Öffnen</Link>
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label={`Weitere Aktionen für ${project.name}`}>
              <MoreHorizontal aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem disabled={isSnapshot} onSelect={() => onAction("rename")}>
              <Pencil aria-hidden="true" />
              Umbenennen
            </DropdownMenuItem>
            <DropdownMenuItem disabled={isSnapshot} onSelect={() => onAction("snapshot")}>
              <Camera aria-hidden="true" />
              Snapshot erstellen
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => onAction("fork")}>
              <GitFork aria-hidden="true" />
              Ableiten (Fork)
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem destructive onSelect={() => onAction("delete")}>
              <Trash2 aria-hidden="true" />
              Löschen
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </Card>
  );
}
