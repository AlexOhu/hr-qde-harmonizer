/**
 * SSSOM-Vorschau als Dialog im Exportbereich.
 *
 * Die Vorschau war bisher ein eigener Hauptnavigationspunkt, obwohl sie nur
 * einen Blick auf das Exportformat wirft. Sie gehoert dorthin, wo exportiert
 * wird.
 */

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { ErrorPanel, SkeletonList } from "@/components/common/states";
import { useSssomPreview } from "@/hooks/useMappings";
import { JUSTIFICATION_LABELS } from "@/features/mappings/mappingPresentation";
import type { MappingJustification } from "@/api/types";
import { MAPPING_JUSTIFICATIONS } from "@/api/types";
import { formatNumber } from "@/lib/utils";

const PREVIEW_LIMIT = 10;

export function SssomPreviewDialog({
  projectId,
  open,
  onOpenChange,
  onDownload,
  isDownloading,
}: {
  projectId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDownload: () => void;
  isDownloading: boolean;
}) {
  const previewQuery = useSssomPreview(projectId, PREVIEW_LIMIT, open);
  const preview = previewQuery.data;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-[min(64rem,calc(100vw-2rem))]"
        title="SSSOM-Vorschau"
        description="Struktur der Exportdatei und die ersten Einträge. Der Export enthält alle entschiedenen Mappings oberhalb der Konfidenzschwelle; Paare mit offenem Review bleiben bis zur Entscheidung außen vor."
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost">Schließen</Button>
            </DialogClose>
            <Button variant="primary" onClick={onDownload} loading={isDownloading}>
              TSV herunterladen
            </Button>
          </>
        }
      >
        {previewQuery.isPending ? <SkeletonList rows={5} /> : null}

        {previewQuery.isError ? (
          <ErrorPanel error={previewQuery.error} onRetry={() => void previewQuery.refetch()} />
        ) : null}

        {preview ? (
          <div className="space-y-4">
            <p className="text-xs text-fg-muted">
              {formatNumber(preview.total_count)} Mappings insgesamt. Vorschau der ersten{" "}
              {preview.sample.length}.
            </p>

            {/* Herkunft benennen statt nur die CURIE zu zeigen: an
                mapping_justification erkennt eine Reviewerin, ob eine Zeile
                algorithmisch entstand oder im Review bestaetigt wurde. */}
            <div>
              <h3 className="mb-1.5 text-xs font-medium text-fg">
                Herkunft (<code className="font-mono">mapping_justification</code>)
              </h3>
              <dl className="grid gap-1 sm:grid-cols-3">
                {MAPPING_JUSTIFICATIONS.map((value) => (
                  <div key={value} className="rounded border border-border-subtle px-2 py-1.5">
                    <dt className="font-mono text-[0.6875rem] text-fg-muted">{value}</dt>
                    <dd className="text-xs text-fg">{JUSTIFICATION_LABELS[value]}</dd>
                  </div>
                ))}
              </dl>
            </div>

            <div>
              <h3 className="mb-1.5 text-xs font-medium text-fg">Felder</h3>
              <div className="flex flex-wrap gap-1.5">
                {preview.fields.map((field) => (
                  <code
                    key={field}
                    className="rounded border border-border-subtle bg-surface-muted px-1.5 py-0.5 font-mono text-[0.6875rem] text-fg-muted"
                  >
                    {field}
                  </code>
                ))}
              </div>
            </div>

            {preview.sample.length > 0 ? (
              <div className="overflow-x-auto rounded-md border border-border-subtle">
                <table className="w-full border-collapse text-left text-xs">
                  <caption className="sr-only">Beispielhafte SSSOM-Zeilen</caption>
                  <thead>
                    <tr className="border-b border-border-subtle bg-surface-muted">
                      {preview.fields.map((field) => (
                        <th
                          key={field}
                          scope="col"
                          className="px-2.5 py-1.5 font-mono text-[0.6875rem] font-medium whitespace-nowrap text-fg-muted"
                        >
                          {field}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.sample.map((row, index) => (
                      <tr key={index} className="border-b border-border-subtle last:border-0">
                        {preview.fields.map((field) => (
                          <td
                            key={field}
                            className="max-w-56 truncate px-2.5 py-1.5 text-fg"
                            title={String(row[field] ?? "")}
                          >
                            {row[field] === null || row[field] === undefined
                              ? "—"
                              : field === "mapping_justification"
                                ? (JUSTIFICATION_LABELS[row[field] as MappingJustification] ??
                                  String(row[field]))
                                : String(row[field])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-fg-muted">
                Noch keine Mappings vorhanden. Führen Sie zuerst einen Framework-Vergleich aus.
              </p>
            )}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
