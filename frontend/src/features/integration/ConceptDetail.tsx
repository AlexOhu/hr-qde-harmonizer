/**
 * Detailspalte fuer ein nicht zugeordnetes Konzept.
 *
 * Das System schlaegt eine Strategie vor, entschieden wird verbindlich durch
 * die Nutzerin (Mixed Initiative). Begruendung und Autor sind Pflichtfelder.
 * Eine bestehende Entscheidung ist sichtbar und ueberschreibbar.
 */

import { useEffect, useState } from "react";
import { Lightbulb, UserPen } from "lucide-react";

import type { Concept, IntegrationDecision, IntegrationStrategy } from "@/api/types";
import { INTEGRATION_STRATEGIES } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { DetailField, DetailPanel } from "@/components/common/MasterDetail";
import { ErrorPanel } from "@/components/common/states";
import { useToast } from "@/components/ui/toast";
import { useDecideConcept, useStrategySuggestion } from "@/hooks/useIntegration";
import {
  STRATEGY_PRESENTATION,
  STRATEGY_REQUIRES_ANCHOR,
  STRATEGY_REQUIRES_CONTEXT_LOSS_NOTE,
} from "./integrationPresentation";
import { formatDateTime } from "@/lib/utils";

export function ConceptDetail({
  concept,
  decision,
  projectId,
  isReadOnly,
  /** Herkunftspaar, falls die Entscheidung aus einem anderen Paar stammt. */
  currentPairFrameworkIds,
}: {
  concept: Concept;
  decision: IntegrationDecision | undefined;
  projectId: string;
  isReadOnly: boolean;
  currentPairFrameworkIds?: string[];
}) {
  const { toast } = useToast();
  const decideMutation = useDecideConcept(projectId);
  // Der Vorschlag kostet einen Request pro Konzept; nur laden, solange noch
  // nicht entschieden ist.
  const suggestionQuery = useStrategySuggestion(projectId, concept.uri, !decision);

  const [strategy, setStrategy] = useState<IntegrationStrategy>("own_class");
  const [anchorClass, setAnchorClass] = useState("");
  const [contextLossNote, setContextLossNote] = useState("");
  const [justification, setJustification] = useState("");
  const [author, setAuthor] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    setStrategy(decision?.strategy ?? "own_class");
    setAnchorClass(decision?.anchor_class ?? "");
    setContextLossNote(decision?.context_loss_note ?? "");
    setJustification("");
    setAuthor("");
    setFormError(null);
    setIsEditing(false);
    decideMutation.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [concept.uri]);

  const suggested = suggestionQuery.data?.suggested_strategy;

  // Vorschlag nur uebernehmen, solange die Nutzerin noch nichts angefasst hat.
  useEffect(() => {
    if (!decision && suggested) setStrategy(suggested);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggested, concept.uri]);

  const showForm = !isReadOnly && (!decision || isEditing);
  const decidedElsewhere =
    decision && currentPairFrameworkIds && !currentPairFrameworkIds.includes(decision.kqr_id);

  function submit() {
    if (!justification.trim()) {
      setFormError("Eine Begründung ist verpflichtend zu dokumentieren.");
      return;
    }
    if (!author.trim()) {
      setFormError("Bitte tragen Sie ein, wer diese Entscheidung trifft.");
      return;
    }
    if (strategy === STRATEGY_REQUIRES_ANCHOR && !anchorClass.trim()) {
      setFormError("Für „An Skelett anhängen“ ist eine Zielklasse erforderlich.");
      return;
    }
    if (strategy === STRATEGY_REQUIRES_CONTEXT_LOSS_NOTE && !contextLossNote.trim()) {
      setFormError(
        "Für „An nächstliegendes Konzept anhängen“ ist ein Vermerk zum Kontextverlust erforderlich.",
      );
      return;
    }
    setFormError(null);

    decideMutation.mutate(
      {
        conceptId: concept.uri,
        input: {
          strategy,
          justification: justification.trim(),
          author: author.trim(),
          anchor_class: strategy === STRATEGY_REQUIRES_ANCHOR ? anchorClass.trim() : null,
          context_loss_note:
            strategy === STRATEGY_REQUIRES_CONTEXT_LOSS_NOTE ? contextLossNote.trim() : null,
        },
      },
      {
        onSuccess: () => {
          toast({
            title: "Entscheidung gespeichert",
            description: `${concept.pref_label}: ${STRATEGY_PRESENTATION[strategy].label}`,
          });
          setIsEditing(false);
        },
      },
    );
  }

  return (
    <DetailPanel>
      <div className="rounded-lg border border-border-subtle bg-surface">
        <div className="border-b border-border-subtle px-4 py-4">
          <div className="flex items-start justify-between gap-3">
            <h2 className="text-sm font-semibold text-fg">{concept.pref_label}</h2>
            <Badge tone="neutral" className="font-mono">
              {concept.kqr_id}
            </Badge>
          </div>
          <p className="mt-1 font-mono text-[0.6875rem] break-all text-fg-subtle">{concept.uri}</p>
          {concept.definition ? (
            <p className="mt-2.5 text-xs text-fg-muted">{concept.definition}</p>
          ) : null}
        </div>

        <dl className="grid grid-cols-2 gap-4 px-4 py-4">
          <DetailField label="Status">
            {decision ? (
              <Badge tone="success">Entschieden</Badge>
            ) : (
              <Badge tone="warning">Offen</Badge>
            )}
          </DetailField>
          <DetailField label="Systemvorschlag">
            {decision ? (
              <span className="text-fg-subtle">—</span>
            ) : suggestionQuery.isPending ? (
              "Wird ermittelt …"
            ) : suggested ? (
              <span className="inline-flex items-center gap-1.5">
                <Lightbulb className="size-3.5 text-info" aria-hidden="true" />
                {STRATEGY_PRESENTATION[suggested].label}
              </span>
            ) : (
              <span className="text-fg-subtle">nicht verfügbar</span>
            )}
          </DetailField>
          {concept.broader.length > 0 ? (
            <DetailField label="Oberbegriffe" mono>
              {concept.broader.join(", ")}
            </DetailField>
          ) : null}
          {concept.narrower.length > 0 ? (
            <DetailField label="Unterbegriffe" mono>
              {concept.narrower.join(", ")}
            </DetailField>
          ) : null}
        </dl>

        {decision ? (
          <div className="border-t border-border-subtle bg-success-soft/40 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <UserPen className="size-3.5 text-success" aria-hidden="true" />
              <span className="text-xs font-medium text-fg">
                {STRATEGY_PRESENTATION[decision.strategy].label}
              </span>
              <span className="text-xs text-fg-muted">
                · {decision.author} · {formatDateTime(decision.created_at)}
              </span>
            </div>
            {decision.context_loss_note ? (
              <p className="mt-1.5 text-xs text-fg-muted">
                Kontextverlust: {decision.context_loss_note}
              </p>
            ) : null}
            {decision.anchor_class ? (
              <p className="mt-1.5 font-mono text-[0.6875rem] break-all text-fg-muted">
                Ankerklasse: {decision.anchor_class}
              </p>
            ) : null}
            <p className="mt-1.5 text-xs text-fg-muted">{decision.justification}</p>

            {decidedElsewhere ? (
              <p className="mt-2 text-xs text-fg-subtle">
                Diese Entscheidung wurde im Kontext eines anderen Framework-Paars getroffen. Sie
                gilt konzeptweit für die gesamte harmonisierte Ontologie.
              </p>
            ) : null}

            {!isReadOnly && !isEditing ? (
              <Button
                variant="secondary"
                size="sm"
                className="mt-3"
                onClick={() => setIsEditing(true)}
              >
                Entscheidung ändern
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>

      {showForm ? (
        <form
          className="mt-4 rounded-lg border border-border-subtle bg-surface"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <div className="border-b border-border-subtle px-4 py-3">
            <h3 className="text-sm font-semibold text-fg">
              {decision ? "Entscheidung überschreiben" : "Integrationsstrategie festlegen"}
            </h3>
            <p className="mt-0.5 text-xs text-fg-muted">
              Die Entscheidung gilt konzeptweit für die harmonisierte Ontologie, auch in anderen
              Framework-Paaren.
            </p>
          </div>

          <div className="space-y-4 px-4 py-4">
            <Field label="Strategie" required hint={STRATEGY_PRESENTATION[strategy].description}>
              {(props) => (
                <Select
                  {...props}
                  value={strategy}
                  onChange={(event) => setStrategy(event.target.value as IntegrationStrategy)}
                >
                  {INTEGRATION_STRATEGIES.map((option) => (
                    <option key={option} value={option}>
                      {STRATEGY_PRESENTATION[option].label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>

            {strategy === STRATEGY_REQUIRES_ANCHOR ? (
              <Field
                label="Zielklasse im Skelett"
                required
                hint="Knoten des HR-QDE-Skeletts, z. B. hrqde:DQR5."
              >
                {(props) => (
                  <Input
                    {...props}
                    value={anchorClass}
                    onChange={(event) => setAnchorClass(event.target.value)}
                    placeholder="hrqde:DQR5"
                    className="font-mono"
                  />
                )}
              </Field>
            ) : null}

            {strategy === STRATEGY_REQUIRES_CONTEXT_LOSS_NOTE ? (
              <Field
                label="Vermerk zum Kontextverlust"
                required
                hint="Welche Bedeutung geht verloren, wenn das Konzept an das nächstgelegene angehängt wird?"
              >
                {(props) => (
                  <Textarea
                    {...props}
                    value={contextLossNote}
                    onChange={(event) => setContextLossNote(event.target.value)}
                    placeholder="z. B. Niveaubezug des Ausgangskonzepts entfällt."
                  />
                )}
              </Field>
            ) : null}

            <Field label="Begründung" required error={formError}>
              {(props) => (
                <Textarea
                  {...props}
                  value={justification}
                  onChange={(event) => setJustification(event.target.value)}
                  placeholder="Warum ist diese Strategie angemessen?"
                />
              )}
            </Field>

            <Field label="Autor/Autorin" required>
              {(props) => (
                <Input
                  {...props}
                  value={author}
                  onChange={(event) => setAuthor(event.target.value)}
                  placeholder="Name oder Kürzel"
                />
              )}
            </Field>

            {decideMutation.isError ? <ErrorPanel error={decideMutation.error} /> : null}
          </div>

          <div className="flex justify-end gap-2 border-t border-border-subtle px-4 py-3">
            {isEditing ? (
              <Button variant="ghost" type="button" onClick={() => setIsEditing(false)}>
                Abbrechen
              </Button>
            ) : null}
            <Button type="submit" variant="primary" loading={decideMutation.isPending}>
              Entscheidung speichern
            </Button>
          </div>
        </form>
      ) : null}

      {isReadOnly && !decision ? (
        <p className="mt-4 rounded-lg border border-border-subtle bg-surface-muted p-3 text-xs text-fg-muted">
          Dieses Konzept braucht eine Integrationsentscheidung. In einem Snapshot ist es
          schreibgeschützt — leiten Sie das Projekt ab (Fork), um daran weiterzuarbeiten.
        </p>
      ) : null}
    </DetailPanel>
  );
}
