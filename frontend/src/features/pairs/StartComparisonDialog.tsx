/**
 * Vergleich zweier Frameworks starten.
 *
 * Die Klassifikation ist keine eigene Seite, sondern eine Aktion auf der
 * Projektuebersicht: Sie erzeugt ein Framework-Paar, das danach dort als
 * laufender Job erscheint.
 */

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Circle, XCircle } from "lucide-react";
import type { ReactNode } from "react";

import type { Framework, Project } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Field, Select } from "@/components/ui/field";
import { ErrorPanel } from "@/components/common/states";
import { useToast } from "@/components/ui/toast";
import { useStartClassification } from "@/hooks/useClassification";
import { useFrameworks, usePreconditions, isFrameworkReady } from "@/hooks/useFrameworks";

/** Eine Vorbedingung; `optional` markiert Hinweise, die den Start nicht blockieren. */
function Precondition({
  state,
  children,
}: {
  state: "ok" | "missing" | "optional";
  children: ReactNode;
}) {
  const icon = {
    ok: <CheckCircle2 className="size-3.5 shrink-0 text-success" aria-hidden="true" />,
    missing: <XCircle className="size-3.5 shrink-0 text-danger" aria-hidden="true" />,
    optional: <Circle className="size-3.5 shrink-0 text-fg-subtle" aria-hidden="true" />,
  }[state];

  const stateLabel = { ok: "erfüllt", missing: "nicht erfüllt", optional: "optional" }[state];

  return (
    <li className="flex items-start gap-2 text-xs text-fg-muted">
      {icon}
      <span>
        <span className="sr-only">{stateLabel}: </span>
        {children}
      </span>
    </li>
  );
}

export function StartComparisonDialog({
  project,
  open,
  onOpenChange,
  /** Vorbelegung, z. B. beim Wiederholen eines gescheiterten Laufs. */
  initialPair,
}: {
  project: Project;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialPair?: { frameworkAId: string; frameworkBId: string };
}) {
  const { toast } = useToast();
  const frameworksQuery = useFrameworks();
  const preconditionsQuery = usePreconditions();
  const startMutation = useStartClassification(project.project_id);

  const [frameworkAId, setFrameworkAId] = useState("");
  const [frameworkBId, setFrameworkBId] = useState("");

  /**
   * Waehlbar ist nur, was zum Projekt gehoert UND den Status `bereit` hat —
   * beides sind Vorbedingungen des Backends, keine UI-Erfindung.
   */
  const selectable = useMemo<Framework[]>(
    () =>
      (frameworksQuery.data ?? []).filter(
        (framework) => project.kqr_ids.includes(framework.id) && isFrameworkReady(framework),
      ),
    [frameworksQuery.data, project.kqr_ids],
  );

  useEffect(() => {
    if (!open) return;
    startMutation.reset();
    if (initialPair) {
      setFrameworkAId(initialPair.frameworkAId);
      setFrameworkBId(initialPair.frameworkBId);
      return;
    }
    setFrameworkAId(selectable[0]?.id ?? "");
    setFrameworkBId(selectable[1]?.id ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, selectable.length, initialPair?.frameworkAId, initialPair?.frameworkBId]);

  const preconditions = preconditionsQuery.data;
  const sameFramework = frameworkAId !== "" && frameworkAId === frameworkBId;
  const tooFewFrameworks = selectable.length < 2;
  const llmMissing = preconditions ? !preconditions.llm_configured : false;
  const canStart = !sameFramework && !tooFewFrameworks && frameworkAId !== "" && frameworkBId !== "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="Framework-Vergleich starten"
        description="Der Vergleich läuft als Hintergrundjob. Sie können die Anwendung währenddessen normal weiterverwenden."
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost">Abbrechen</Button>
            </DialogClose>
            <Button
              variant="primary"
              disabled={!canStart}
              loading={startMutation.isPending}
              onClick={() =>
                startMutation.mutate(
                  { frameworkAId, frameworkBId },
                  {
                    onSuccess: () => {
                      toast({
                        title: "Vergleich gestartet",
                        description: "Der Fortschritt erscheint in der Projektübersicht.",
                      });
                      onOpenChange(false);
                    },
                  },
                )
              }
            >
              Vergleich starten
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {tooFewFrameworks ? (
            <p className="rounded-md border border-warning/30 bg-warning-soft p-3 text-xs text-fg-muted">
              Dieses Projekt enthält weniger als zwei Frameworks mit dem Status „Bereit“. Ergänzen
              Sie die Framework-Bibliothek oder berechnen Sie dort fehlende Embeddings.
            </p>
          ) : null}

          <Field label="Framework A" required>
            {(props) => (
              <Select
                {...props}
                value={frameworkAId}
                onChange={(event) => setFrameworkAId(event.target.value)}
                disabled={tooFewFrameworks}
              >
                {selectable.map((framework) => (
                  <option key={framework.id} value={framework.id}>
                    {framework.name}
                    {framework.is_hub ? " (Hub)" : ""}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <Field
            label="Framework B"
            required
            error={sameFramework ? "Bitte zwei verschiedene Frameworks wählen." : null}
          >
            {(props) => (
              <Select
                {...props}
                value={frameworkBId}
                onChange={(event) => setFrameworkBId(event.target.value)}
                disabled={tooFewFrameworks}
              >
                {selectable.map((framework) => (
                  <option key={framework.id} value={framework.id}>
                    {framework.name}
                    {framework.is_hub ? " (Hub)" : ""}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <div>
            <h3 className="text-xs font-medium text-fg">Vorbedingungen</h3>
            {preconditionsQuery.isPending ? (
              <p className="mt-1.5 text-xs text-fg-subtle">Werden geprüft …</p>
            ) : preconditionsQuery.isError ? (
              <p className="mt-1.5 text-xs text-fg-muted">
                Vorbedingungen konnten nicht geprüft werden.
              </p>
            ) : preconditions ? (
              <ul className="mt-1.5 space-y-1.5">
                <Precondition state={preconditions.llm_configured ? "ok" : "missing"}>
                  LLM-Endpunkt konfiguriert
                  {preconditions.llm_providers ? ` (${preconditions.llm_providers})` : ""}
                </Precondition>
                <Precondition state={tooFewFrameworks ? "missing" : "ok"}>
                  Mindestens zwei Frameworks im Projekt sind eingebettet
                </Precondition>
                <Precondition state={preconditions.neo4j_reachable ? "ok" : "optional"}>
                  {preconditions.neo4j_reachable
                    ? "Neo4j erreichbar"
                    : "Neo4j nicht erreichbar — optional, der Vergleich läuft trotzdem"}
                </Precondition>
              </ul>
            ) : null}
          </div>

          {llmMissing ? (
            <p className="rounded-md border border-danger/25 bg-danger-soft p-3 text-xs text-fg-muted">
              Ohne konfigurierten LLM-Endpunkt schlägt der Lauf beim ersten Konzeptpaar fehl. Setzen
              Sie den API-Schlüssel in der <code className="font-mono">.env</code> des Backends.
            </p>
          ) : null}

          {startMutation.isError ? <ErrorPanel error={startMutation.error} /> : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
