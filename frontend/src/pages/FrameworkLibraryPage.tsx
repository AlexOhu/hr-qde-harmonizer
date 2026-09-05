/**
 * Framework-Bibliothek.
 *
 * Frameworks sind globale Ressourcen und nicht an ein Projekt gebunden.
 * Diese Seite zeigt sie mit Status, notwendiger Folgeaktion und
 * Validierungsfehlern.
 */

import { useState } from "react";
import { Anchor, Library, Plus, Sigma, Trash2 } from "lucide-react";

import type { Framework } from "@/api/types";
import { AppShell, PageBody, PageHeader } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorPanel, SkeletonList } from "@/components/common/states";
import { useToast } from "@/components/ui/toast";
import { AddFrameworkDialog } from "@/features/frameworks/AddFrameworkDialog";
import { DeleteFrameworkDialog } from "@/features/frameworks/DeleteFrameworkDialog";
import {
  FRAMEWORK_STATUS_PRESENTATION,
  FrameworkStatusBadge,
} from "@/features/frameworks/frameworkStatus";
import { useEmbedFramework, useFrameworkStatus, useFrameworks } from "@/hooks/useFrameworks";
import { formatNumber } from "@/lib/utils";

export function FrameworkLibraryPage() {
  const frameworksQuery = useFrameworks();
  const [addOpen, setAddOpen] = useState(false);

  const frameworks = frameworksQuery.data ?? [];
  const readyCount = frameworks.filter((framework) => framework.status === "bereit").length;

  return (
    <AppShell>
      <PageHeader
        title="Framework-Bibliothek"
        description="Kompetenz-, Qualifikations- und Berufsrahmenwerke stehen projektübergreifend zur Verfügung. Nur Frameworks mit dem Status „Bereit“ können verglichen werden."
        meta={
          frameworks.length > 0 ? (
            <span className="text-xs text-fg-muted">
              {frameworks.length} Frameworks · {readyCount} bereit
            </span>
          ) : null
        }
        actions={
          <Button variant="primary" onClick={() => setAddOpen(true)}>
            <Plus aria-hidden="true" />
            Framework hinzufügen
          </Button>
        }
      />

      <PageBody>
        {frameworksQuery.isPending ? <SkeletonList rows={4} /> : null}

        {frameworksQuery.isError ? (
          <ErrorPanel
            error={frameworksQuery.error}
            onRetry={() => void frameworksQuery.refetch()}
          />
        ) : null}

        {frameworksQuery.isSuccess && frameworks.length === 0 ? (
          <EmptyState
            icon={<Library />}
            title="Noch kein Framework vorhanden"
            description="Laden Sie ein Rahmenwerk hoch. SKOS-konforme Turtle-Dateien werden direkt validiert, eingelesen und eingebettet."
            action={
              <Button variant="primary" onClick={() => setAddOpen(true)}>
                <Plus aria-hidden="true" />
                Framework hinzufügen
              </Button>
            }
          />
        ) : null}

        {frameworks.length > 0 ? (
          <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {frameworks.map((framework) => (
              <li key={framework.id}>
                <FrameworkCard framework={framework} />
              </li>
            ))}
          </ul>
        ) : null}
      </PageBody>

      {addOpen ? <AddFrameworkDialog open onOpenChange={setAddOpen} /> : null}
    </AppShell>
  );
}

function FrameworkCard({ framework }: { framework: Framework }) {
  const { toast } = useToast();
  const embedMutation = useEmbedFramework();
  const presentation = FRAMEWORK_STATUS_PRESENTATION[framework.status];
  const [deleteOpen, setDeleteOpen] = useState(false);

  // Fehlerdetails nur fuer nicht validierte Frameworks nachladen.
  const statusQuery = useFrameworkStatus(framework.id, framework.status === "roh");
  const validationErrors = statusQuery.data?.validation_errors ?? [];

  return (
    <Card className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-3 px-4 pt-3">
        <div className="min-w-0">
          <h2 className="truncate text-sm font-semibold text-fg" title={framework.name}>
            {framework.name}
          </h2>
          <p className="mt-0.5 truncate font-mono text-[0.6875rem] text-fg-subtle">
            {framework.id}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {framework.is_hub ? (
            <Badge tone="accent" icon={<Anchor aria-hidden="true" />}>
              Hub
            </Badge>
          ) : null}
          <Button
            variant="ghost"
            size="icon"
            aria-label={`${framework.name} endgültig löschen`}
            onClick={() => setDeleteOpen(true)}
          >
            <Trash2 aria-hidden="true" className="text-fg-subtle" />
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 px-4 py-3">
        <FrameworkStatusBadge status={framework.status} />
        <span className="text-xs text-fg-muted">
          {framework.concept_count !== null
            ? `${formatNumber(framework.concept_count)} Konzepte`
            : "Konzeptanzahl unbekannt"}
        </span>
        <span className="text-xs text-fg-subtle">· {framework.source_format}</span>
      </div>

      {presentation.nextAction ? (
        <p className="px-4 pb-3 text-xs text-fg-muted">{presentation.nextAction}</p>
      ) : null}

      {framework.status === "roh" ? (
        <div className="px-4 pb-3">
          {statusQuery.isPending ? (
            <p className="text-xs text-fg-subtle">Validierungsfehler werden geladen …</p>
          ) : validationErrors.length > 0 ? (
            <details className="rounded-md border border-danger/25 bg-danger-soft p-2.5">
              <summary className="cursor-pointer text-xs font-medium text-danger">
                {validationErrors.length}{" "}
                {validationErrors.length === 1 ? "Validierungsfehler" : "Validierungsfehler"}
              </summary>
              <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto">
                {validationErrors.slice(0, 20).map((error, index) => (
                  <li key={index} className="text-xs break-words text-fg-muted">
                    {error}
                  </li>
                ))}
              </ul>
              {validationErrors.length > 20 ? (
                <p className="mt-1.5 text-xs text-fg-subtle">
                  … und {validationErrors.length - 20} weitere.
                </p>
              ) : null}
            </details>
          ) : (
            // Das Backend haelt die Fehlerliste nur im Prozessspeicher; nach
            // einem API-Neustart ist sie leer, der Status bleibt aber `roh`.
            <p className="text-xs text-fg-subtle">
              Keine Fehlerdetails verfügbar. Sie werden nur bis zum nächsten Neustart des Backends
              vorgehalten — laden Sie die Datei erneut hoch, um sie zu sehen.
            </p>
          )}
        </div>
      ) : null}

      {framework.status === "formalisiert" ? (
        <div className="mt-auto border-t border-border-subtle px-4 py-2.5">
          <Button
            variant="secondary"
            size="sm"
            loading={embedMutation.isPending}
            onClick={() =>
              embedMutation.mutate(framework.id, {
                onSuccess: (updated) =>
                  toast({
                    title: "Embeddings berechnet",
                    description: `${updated.name} hat jetzt den Status „Bereit“.`,
                  }),
                onError: (error) =>
                  toast({
                    title: "Embedding fehlgeschlagen",
                    description: error instanceof Error ? error.message : undefined,
                    tone: "error",
                  }),
              })
            }
          >
            <Sigma aria-hidden="true" />
            Embeddings berechnen
          </Button>
        </div>
      ) : null}

      {deleteOpen ? (
        <DeleteFrameworkDialog framework={framework} open onOpenChange={setDeleteOpen} />
      ) : null}
    </Card>
  );
}
