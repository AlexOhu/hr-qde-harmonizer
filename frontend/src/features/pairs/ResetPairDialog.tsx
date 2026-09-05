/**
 * Ein bereits klassifiziertes Framework-Paar vollstaendig zuruecksetzen.
 *
 * Anders als "Erneut versuchen" (Resume eines gescheiterten/unterbrochenen
 * Laufs, siehe StartComparisonDialog) ist dies eine bewusst destruktive
 * Aktion: alle Mappings UND die zugrunde liegenden Klassifikationsergebnisse
 * dieses Paares werden geloescht, damit ein erneuter Vergleich jedes
 * Konzeptpaar wieder klassifiziert statt es zu ueberspringen. Job-Historie
 * und Integrationsentscheidungen bleiben unangetastet (nur die betroffenen
 * Integrationsentscheidungen werden gezaehlt und angezeigt).
 *
 * Der Reset selbst ist eine protokollpflichtige Kuratoren-Entscheidung
 * (Accountability-Prinzip): Begruendung und Autor sind Pflichtfelder, analog
 * zur Konjunkt/Disjunkt-Weiche in MappingReviewForm.
 */

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Field, Input, Textarea } from "@/components/ui/field";
import { ErrorPanel } from "@/components/common/states";
import { useToast } from "@/components/ui/toast";
import { useResetPair } from "@/hooks/useClassification";
import type { FrameworkPair } from "./status";

export function ResetPairDialog({
  projectId,
  pair,
  open,
  onOpenChange,
}: {
  projectId: string;
  pair: FrameworkPair;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { toast } = useToast();
  const resetMutation = useResetPair(projectId);

  const [justification, setJustification] = useState("");
  const [author, setAuthor] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // Beim Oeffnen fuer ein (moeglicherweise anderes) Paar darf kein Text aus
  // einem vorherigen Versuch stehen bleiben.
  useEffect(() => {
    if (!open) return;
    setJustification("");
    setAuthor("");
    setFormError(null);
    resetMutation.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, pair.key]);

  function submit() {
    if (!justification.trim()) {
      setFormError("Bitte begründen Sie den Reset.");
      return;
    }
    if (!author.trim()) {
      setFormError("Bitte tragen Sie ein, wer diesen Reset veranlasst.");
      return;
    }
    setFormError(null);

    resetMutation.mutate(
      {
        frameworkAId: pair.frameworkAId,
        frameworkBId: pair.frameworkBId,
        input: { justification: justification.trim(), author: author.trim() },
      },
      {
        onSuccess: (result) => {
          toast({
            title: "Paar zurückgesetzt",
            description: `${result.removed_mappings} Mappings und ${result.removed_classification_results} Klassifikationsergebnisse entfernt.`,
          });
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="Vergleich zurücksetzen"
        description={`${pair.frameworkAName} ↔ ${pair.frameworkBName}`}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost">Abbrechen</Button>
            </DialogClose>
            <Button variant="danger" loading={resetMutation.isPending} onClick={submit}>
              Endgültig zurücksetzen
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
              Entfernt unwiderruflich alle {pair.mappingsCount} Mappings und die zugrunde
              liegenden Klassifikationsergebnisse dieses Paares. Die Job-Historie bleibt als
              Nachweis erhalten, und bereits getroffene Integrationsentscheidungen werden nicht
              verändert. Ein erneuter Vergleich klassifiziert danach jedes Konzeptpaar neu.
            </p>
          </div>

          <Field label="Begründung" required>
            {(props) => (
              <Textarea
                {...props}
                value={justification}
                onChange={(event) => setJustification(event.target.value)}
                placeholder="Warum muss dieses Paar neu klassifiziert werden?"
              />
            )}
          </Field>

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

          {resetMutation.isError ? <ErrorPanel error={resetMutation.error} /> : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
