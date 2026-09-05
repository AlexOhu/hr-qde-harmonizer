/**
 * Framework endgueltig aus der globalen Bibliothek loeschen.
 *
 * Destruktiv und ohne Undo: anders als das projekt-scoped Entfernen
 * (Projektuebersicht, RemoveKqrFromProjectDialog) betrifft dies alle
 * Projekte gleichzeitig. Das Backend blockiert mit 409, solange irgendein
 * Projekt das Framework noch referenziert -- die Fehlermeldung nennt die
 * betroffenen Projekte und bleibt im Dialog sichtbar, statt ihn
 * stillschweigend zu schliessen (Transparency-Prinzip).
 */

import { useEffect } from "react";
import { AlertTriangle, Trash2 } from "lucide-react";

import { ApiError } from "@/api/client";
import type { Framework } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { ErrorPanel } from "@/components/common/states";
import { useToast } from "@/components/ui/toast";
import { useDeleteFrameworkGlobally } from "@/hooks/useFrameworks";

export function DeleteFrameworkDialog({
  framework,
  open,
  onOpenChange,
}: {
  framework: Framework;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { toast } = useToast();
  const deleteMutation = useDeleteFrameworkGlobally();

  useEffect(() => {
    if (!open) return;
    deleteMutation.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, framework.id]);

  function submit() {
    deleteMutation.mutate(framework.id, {
      onSuccess: () => {
        toast({ title: "Framework gelöscht", description: `${framework.name} wurde entfernt.` });
        onOpenChange(false);
      },
    });
  }

  const conflict =
    deleteMutation.error instanceof ApiError && deleteMutation.error.isConflict
      ? deleteMutation.error
      : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="Framework endgültig löschen"
        description={framework.name}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost">Abbrechen</Button>
            </DialogClose>
            <Button variant="danger" loading={deleteMutation.isPending} onClick={submit}>
              <Trash2 aria-hidden="true" />
              Endgültig löschen
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="flex items-start gap-2.5 rounded-md border border-danger/25 bg-danger-soft p-3">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden="true" />
            <p className="text-xs text-fg-muted">
              Entfernt {framework.name} unwiderruflich aus der Framework-Bibliothek: Registry-
              Eintrag, formalisierte Daten und Embeddings. Referenziert noch ein Projekt dieses
              Framework, ist das Löschen gesperrt — entfernen Sie es dort zuerst über „Aus
              Projekt entfernen“.
            </p>
          </div>

          {conflict ? (
            <div className="rounded-md border border-danger/25 bg-danger-soft p-3">
              <p className="text-xs font-medium text-danger">Löschen gesperrt</p>
              <p className="mt-1 text-xs text-fg-muted">
                {conflict.detail ?? conflict.message}
              </p>
            </div>
          ) : deleteMutation.isError ? (
            <ErrorPanel error={deleteMutation.error} />
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
