/**
 * Exportbereich.
 *
 * Zwei klar getrennte Teile: Readiness (was fehlt noch?) und Artefakte (was
 * laesst sich herunterladen?). Die frühere eigenständige SSSOM-Vorschau ist
 * hier als Dialog eingebettet.
 */

import { useMemo, useState } from "react";
import { Camera, Download, Eye, FileText, Layers, Network, Table2 } from "lucide-react";

import type { OntologyFormat } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/field";
import { PageBody, PageHeader } from "@/components/layout/AppShell";
import { ErrorPanel } from "@/components/common/states";
import { useToast } from "@/components/ui/toast";
import { ExportReadiness, buildReadinessChecks } from "@/features/export/ExportReadiness";
import { SssomPreviewDialog } from "@/features/export/SssomPreviewDialog";
import { SnapshotDialog } from "@/features/projects/ProjectDialogs";
import { useProjectContext } from "@/features/projects/ProjectLayout";
import {
  useClusters,
  useExportAuditReport,
  useExportOntology,
  useExportSssom,
  useExportSummary,
  useRunClustering,
} from "@/hooks/useExports";
import { formatNumber } from "@/lib/utils";

const ONTOLOGY_FORMATS: { value: OntologyFormat; label: string }[] = [
  { value: "turtle", label: "Turtle (.ttl)" },
  { value: "xml", label: "RDF/XML (.rdf)" },
  { value: "json-ld", label: "JSON-LD (.jsonld)" },
];

export function ProjectExportPage() {
  const { projectId, project, pairs, pipelineStatus, isReadOnly } = useProjectContext();
  const { toast } = useToast();

  const summaryQuery = useExportSummary(projectId);
  const clustersQuery = useClusters(projectId);
  const clusteringMutation = useRunClustering(projectId);

  const ontologyMutation = useExportOntology(projectId);
  const sssomMutation = useExportSssom(projectId);
  const auditMutation = useExportAuditReport(projectId);

  const [ontologyFormat, setOntologyFormat] = useState<OntologyFormat>("turtle");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [snapshotOpen, setSnapshotOpen] = useState(false);
  const [hasExported, setHasExported] = useState(false);

  const clusterCount = clustersQuery.data?.length;
  const clusteringDone = pipelineStatus?.clustering_done ?? (clusterCount ?? 0) > 0;

  /** Clustering laeuft ueber die Frameworks des Projekts. */
  const clusteringAction = isReadOnly ? (
    <span className="text-xs text-fg-subtle">Im Snapshot nicht ausführbar</span>
  ) : (
    <Button
      variant="secondary"
      size="sm"
      loading={clusteringMutation.isPending}
      onClick={() =>
        clusteringMutation.mutate(project.kqr_ids, {
          onSuccess: (clusters) =>
            toast({
              title: "Clustering abgeschlossen",
              description: `${formatNumber(clusters.length)} Cluster erzeugt.`,
            }),
          onError: (error) =>
            toast({
              title: "Clustering fehlgeschlagen",
              description: error instanceof Error ? error.message : undefined,
              tone: "error",
            }),
        })
      }
    >
      <Layers aria-hidden="true" />
      Clustering starten
    </Button>
  );

  const checks = useMemo(
    () =>
      buildReadinessChecks({
        projectId,
        pairs,
        pipelineStatus,
        exportSummary: summaryQuery.data,
        clusterCount,
        clusteringAction,
      }),
    // clusteringAction haengt an Mutationszustand und Projektdaten; die
    // Neuberechnung ist billig, daher bewusst ohne Memoisierung der Aktion.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      projectId,
      pairs,
      pipelineStatus,
      summaryQuery.data,
      clusterCount,
      clusteringMutation.isPending,
      isReadOnly,
    ],
  );

  const summary = summaryQuery.data;

  function handleExport(mutate: () => void, label: string) {
    mutate();
    setHasExported(true);
    toast({ title: `${label} wird erstellt`, description: "Der Download startet automatisch." });
  }

  return (
    <>
      <PageHeader
        title="Export"
        description="Die harmonisierte Ontologie, die vollständige Mapping-Tabelle und der Prüfbericht geben den aktuellen Projektstand wieder."
        meta={
          summary ? (
            <span className="text-xs text-fg-muted">
              Projektweit: {formatNumber(summary.no_consensus_pairs)} ohne Mehrheitsentscheid ·{" "}
              {formatNumber(summary.related_pairs)} „Verwandt“ ·{" "}
              {formatNumber(summary.low_confidence_mappings)} unter der Konfidenzschwelle
            </span>
          ) : null
        }
      />

      <PageBody>
        <div className="space-y-5">
          {summaryQuery.isError ? (
            <ErrorPanel error={summaryQuery.error} onRetry={() => void summaryQuery.refetch()} />
          ) : null}

          {clusteringMutation.isError ? (
            <ErrorPanel title="Clustering fehlgeschlagen" error={clusteringMutation.error} />
          ) : null}

          <section aria-labelledby="readiness-heading">
            <h2 id="readiness-heading" className="sr-only">
              Bereitschaft für den Export
            </h2>
            <ExportReadiness checks={checks} />
          </section>

          <section aria-labelledby="artifacts-heading">
            <h2 id="artifacts-heading" className="mb-2.5 text-sm font-semibold text-fg">
              Exportartefakte
            </h2>

            <div className="grid gap-3 lg:grid-cols-3">
              <ArtifactCard
                icon={<Network aria-hidden="true" />}
                title="Harmonisierte Ontologie"
                subtitle="OWL, aufgebaut auf der Clusterstruktur"
                badge={
                  clusteringDone ? (
                    <Badge tone="success">
                      {clusterCount !== undefined
                        ? `${formatNumber(clusterCount)} Cluster`
                        : "bereit"}
                    </Badge>
                  ) : (
                    <Badge tone="warning">Clustering nötig</Badge>
                  )
                }
                error={ontologyMutation.error}
                actions={
                  <div className="flex flex-wrap items-center gap-2">
                    <Select
                      value={ontologyFormat}
                      onChange={(event) =>
                        setOntologyFormat(event.target.value as OntologyFormat)
                      }
                      aria-label="Ontologie-Format"
                      className="w-auto"
                    >
                      {ONTOLOGY_FORMATS.map((format) => (
                        <option key={format.value} value={format.value}>
                          {format.label}
                        </option>
                      ))}
                    </Select>
                    <Button
                      variant="primary"
                      size="sm"
                      disabled={!clusteringDone}
                      loading={ontologyMutation.isPending}
                      aria-label="Harmonisierte Ontologie herunterladen"
                      onClick={() =>
                        handleExport(
                          () => ontologyMutation.mutate(ontologyFormat),
                          "Ontologie",
                        )
                      }
                    >
                      <Download aria-hidden="true" />
                      Herunterladen
                    </Button>
                  </div>
                }
              />

              <ArtifactCard
                icon={<Table2 aria-hidden="true" />}
                title="SSSOM-Mappings"
                subtitle="TSV mit allen Mappings oberhalb der Konfidenzschwelle"
                badge={
                  summary ? (
                    <Badge tone="neutral">
                      {formatNumber(pairs.reduce((sum, pair) => sum + pair.mappingsCount, 0))}{" "}
                      Mappings
                    </Badge>
                  ) : null
                }
                error={sssomMutation.error}
                actions={
                  <div className="flex flex-wrap items-center gap-2">
                    <Button variant="secondary" size="sm" onClick={() => setPreviewOpen(true)}>
                      <Eye aria-hidden="true" />
                      Vorschau
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      loading={sssomMutation.isPending}
                      aria-label="SSSOM-Mappings herunterladen"
                      onClick={() => handleExport(() => sssomMutation.mutate(), "SSSOM-TSV")}
                    >
                      <Download aria-hidden="true" />
                      Herunterladen
                    </Button>
                  </div>
                }
              />

              <ArtifactCard
                icon={<FileText aria-hidden="true" />}
                title="Prüfbericht"
                subtitle="Markdown mit allen offenen und ungelösten Fällen"
                badge={
                  summary && summary.total_open > 0 ? (
                    <Badge tone="warning">{formatNumber(summary.total_open)} offen</Badge>
                  ) : (
                    <Badge tone="success">Keine offenen Fälle</Badge>
                  )
                }
                error={auditMutation.error}
                actions={
                  <Button
                    variant="primary"
                    size="sm"
                    loading={auditMutation.isPending}
                    aria-label="Prüfbericht herunterladen"
                    onClick={() => handleExport(() => auditMutation.mutate(), "Prüfbericht")}
                  >
                    <Download aria-hidden="true" />
                    Herunterladen
                  </Button>
                }
              />
            </div>
          </section>

          {hasExported && !isReadOnly ? (
            <section aria-labelledby="snapshot-heading">
              <Card>
                <CardHeader
                  title="Ergebnis sichern"
                  description="Ein Snapshot friert den exportierten Stand als schreibgeschützte Kopie ein, damit er später nachvollziehbar bleibt."
                  action={
                    <Button variant="secondary" size="sm" onClick={() => setSnapshotOpen(true)}>
                      <Camera aria-hidden="true" />
                      Snapshot erstellen
                    </Button>
                  }
                />
              </Card>
            </section>
          ) : null}
        </div>
      </PageBody>

      <SssomPreviewDialog
        projectId={projectId}
        open={previewOpen}
        onOpenChange={setPreviewOpen}
        isDownloading={sssomMutation.isPending}
        onDownload={() => handleExport(() => sssomMutation.mutate(), "SSSOM-TSV")}
      />

      {snapshotOpen ? (
        <SnapshotDialog project={project} open onOpenChange={setSnapshotOpen} />
      ) : null}
    </>
  );
}

function ArtifactCard({
  icon,
  title,
  subtitle,
  badge,
  actions,
  error,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  badge?: React.ReactNode;
  actions: React.ReactNode;
  error: unknown;
}) {
  return (
    <Card className="flex h-full flex-col">
      <div className="flex items-start gap-3 px-4 pt-4">
        <div className="text-fg-muted [&_svg]:size-4">{icon}</div>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-fg">{title}</h3>
          <p className="mt-0.5 text-xs text-fg-muted">{subtitle}</p>
        </div>
      </div>

      {badge ? <div className="px-4 pt-2.5">{badge}</div> : null}

      {error ? (
        <div className="px-4 pt-3">
          <ErrorPanel error={error} />
        </div>
      ) : null}

      <div className="mt-auto px-4 py-3">{actions}</div>
    </Card>
  );
}
