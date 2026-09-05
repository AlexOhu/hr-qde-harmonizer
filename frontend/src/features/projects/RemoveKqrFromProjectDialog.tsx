/**
 * Ein Framework projekt-scoped aus diesem Projekt entfernen.
 *
 * Guenstig und reversibel: das Framework bleibt in der globalen Bibliothek
 * erhalten und kann diesem oder einem anderen Projekt spaeter erneut
 * hinzugefuegt werden. Anders als das globale Loeschen (Framework-
 * Bibliothek) betrifft dies nur die Referenz dieses einen Projekts. Setzt
 * dabei alle betroffenen Framework-Paare dieses Projekts zurueck (vgl.
 * ResetPairDialog) -- Begruendung ist deshalb optional, Autor/Autorin
 * verpflichtend (Accountability-Prinzip).
 */

import { useEffect, useState } from "react";
import { AlertTriangle, Unlink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Field, Input, Textarea } from "@/components/ui/field";
import { ErrorPanel } from "@/components/common/states";
import { useToast } from "@/components/ui/toast";
import { useRemoveKqrFromProject } from "@/hooks/useProjects";

export function RemoveKqrFromProjectDialog({
  projectId,
  kqrId,
  kqrName,
  open,
  onOpenChange,
}: {
  projectId: string;
  kqrId: string;
  kqrName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { toast } = useToast();
  const removeMutation = useRemoveKqrFromProject(projectId);

  const [author, setAuthor] = useState("");
  const [justification, setJustification] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // Beim Oeffnen fuer ein (moeglicherweise anderes) Framework darf kein Text
  // aus einem vorherigen Versuch stehen bleiben.
  useEffect(() => {
    if (!open) return;
    setAuthor("");
    setJustification("");
    setFormError(null);
    removeMutation.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, kqrId]);

  function submit() {
    if (!author.trim()) {
      setFormError("Bitte tragen Sie ein, wer diese Entfernung veranlasst.");
      return;
    }
    setFormError(null);

    removeMutation.mutate(
      {
        kqrId,
        input: { author: author.trim(), justification: justification.trim() || undefined },
      },
      {
        onSuccess: (result) => {
          toast({
            title: "Aus Projekt entfernt",
            description:
              result.removed_pairs > 0
                ? `${kqrName} entfernt, ${result.removed_pairs} betroffene ${
                    result.removed_pairs === 1 ? "Vergleich" : "Vergleiche"
                  } zurückgesetzt.`
                : `${kqrName} entfernt.`,
          });
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="Aus Projekt entfernen"
        description={kqrName}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost">Abbrechen</Button>
            </DialogClose>
            <Button variant="danger" loading={removeMutation.isPending} onClick={submit}>
              <Unlink aria-hidden="true" />
              Entfernen
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="flex items-start gap-2.5 rounded-md border border-danger/25 bg-danger-soft p-3">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden="true" />
            <p className="text-xs text-fg-muted">
              <strong className="font-medium text-fg">
                Diese Aktion kann nicht rückgängig gemacht werden.
              </strong>{" "}
              Entfernt {kqrName} aus diesem Projekt und setzt unwiderruflich alle Vergleiche
              zurück, an denen es beteiligt ist: Mappings und Klassifikationsergebnisse dieser
              Paare werden gelöscht, die Job-Historie bleibt als Nachweis erhalten. Nur das
              Framework selbst bleibt in der Framework-Bibliothek erhalten und kann diesem oder
              einem anderen Projekt später erneut hinzugefügt werden — die gelöschten Vergleiche
              müssen dann komplett neu klassifiziert werden.
            </p>
          </div>

          <Field label="Autor/Autorin" required error={formError}>
            {(props) => (
              <Input
                {...props}
                value={author}
                onChange={(event) => setAuthor(event.target.value)}
                placeholder="Name oder Kürzel"
              />
            )}
          </Field>

          <Field label="Begründung (optional)">
            {(props) => (
              <Textarea
                {...props}
                value={justification}
                onChange={(event) => setJustification(event.target.value)}
                placeholder="Warum wird dieses Framework aus dem Projekt entfernt?"
              />
            )}
          </Field>

          {removeMutation.isError ? <ErrorPanel error={removeMutation.error} /> : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
