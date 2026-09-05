/**
 * Konjunkt/Disjunkt-Weiche fuer ein offenes Paar (RELATED oder ohne
 * LLM-Mehrheitsentscheid, FZ3.2).
 *
 * Die Weiche steht ganz oben: erst entscheidet die Reviewerin, ob das Paar
 * ueberhaupt ein Mapping ist, danach erst erscheinen die Felder des jeweiligen
 * Zweigs. Ein Formular, das alle Felder beider Zweige gleichzeitig zeigt,
 * verlangt eine Entscheidung, die die Oberflaeche noch gar nicht gestellt hat.
 *
 * Die Pflichtfelder spiegeln die Serverregeln aus
 * `PUT /mappings/{id}/review`; sie werden hier vorweggenommen, damit ein
 * unvollstaendiges Formular nicht erst als HTTP 400 zurueckkommt. Massgeblich
 * bleibt der Server.
 */

import { useEffect, useState } from "react";
import { GitMerge, Split } from "lucide-react";

import type { IntegrationStrategy, Mapping, MappingPredicate } from "@/api/types";
import { INTEGRATION_STRATEGIES, MAPPING_PREDICATES } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { ErrorPanel } from "@/components/common/states";
import { useToast } from "@/components/ui/toast";
import { useReviewMapping } from "@/hooks/useMappings";
import { STRATEGY_PRESENTATION } from "@/features/integration/integrationPresentation";
import { PREDICATE_DESCRIPTIONS, PREDICATE_LABELS, predicateLabel } from "./mappingPresentation";
import { cn } from "@/lib/utils";

type Branch = "conjunct" | "disjunct";

export function MappingReviewForm({
  mapping,
  projectId,
}: {
  mapping: Mapping;
  projectId: string;
}) {
  const { toast } = useToast();
  const reviewMutation = useReviewMapping(projectId);

  const [branch, setBranch] = useState<Branch>("conjunct");
  const [predicate, setPredicate] = useState<MappingPredicate>("skos:relatedMatch");
  const [strategy, setStrategy] = useState<IntegrationStrategy>("own_class");
  const [contextLossNote, setContextLossNote] = useState("");
  const [justification, setJustification] = useState("");
  const [author, setAuthor] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // Beim Wechsel des ausgewaehlten Paares darf kein Text des vorigen Formulars
  // stehen bleiben, sonst wird versehentlich die falsche Begruendung
  // gespeichert.
  useEffect(() => {
    setBranch("conjunct");
    setPredicate("skos:relatedMatch");
    setStrategy("own_class");
    setContextLossNote("");
    setJustification("");
    setAuthor("");
    setFormError(null);
    reviewMutation.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapping.mapping_id]);

  const needsContextLossNote = branch === "disjunct" && strategy === "map_to_nearest";

  function submit() {
    if (!author.trim()) {
      setFormError("Bitte tragen Sie ein, wer diese Entscheidung trifft.");
      return;
    }
    if (needsContextLossNote && !contextLossNote.trim()) {
      setFormError(
        "Für „An nächstliegendes Konzept anhängen“ ist ein Vermerk zum Kontextverlust erforderlich.",
      );
      return;
    }
    setFormError(null);

    const input =
      branch === "conjunct"
        ? {
            decision: "conjunct" as const,
            predicate,
            confidence: 1.0,
            justification: justification.trim() || undefined,
            author: author.trim(),
          }
        : {
            decision: "disjunct" as const,
            strategy,
            context_loss_note: needsContextLossNote ? contextLossNote.trim() : undefined,
            justification: justification.trim() || undefined,
            author: author.trim(),
          };

    reviewMutation.mutate(
      { mappingId: mapping.mapping_id, input },
      {
        onSuccess: () => {
          toast({
            title: "Entscheidung gespeichert",
            description:
              branch === "conjunct"
                ? `${mapping.subject_label} → ${PREDICATE_LABELS[predicate]}`
                : `${mapping.subject_label}: ${STRATEGY_PRESENTATION[strategy].label}`,
          });
        },
      },
    );
  }

  return (
    <form
      className="mt-4 rounded-lg border border-warning/30 bg-surface"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <div className="border-b border-border-subtle px-4 py-3">
        <h3 className="text-sm font-semibold text-fg">Offene Entscheidung</h3>
        <p className="mt-0.5 text-xs text-fg-muted">
          Die Klassifikation kam zu {predicateLabel(mapping.predicate_id)} und hat damit keine
          Zuordnung getroffen. Entscheiden Sie, ob die beiden Konzepte ein Mapping bilden oder ob
          das Ausgangskonzept eigenständig in die Ontologie eingeht.
        </p>
      </div>

      <div className="space-y-4 px-4 py-4">
        <fieldset>
          <legend className="mb-2 text-xs font-medium text-fg">
            Entscheidung
            <span className="ml-1 text-danger" aria-hidden="true">
              *
            </span>
          </legend>
          <div className="grid gap-2 sm:grid-cols-2">
            <BranchOption
              selected={branch === "conjunct"}
              onSelect={() => setBranch("conjunct")}
              icon={<GitMerge className="size-3.5" aria-hidden="true" />}
              label="Konjunkt: die Konzepte gehören zusammen"
              description="Erzeugt ein Mapping mit dem gewählten SKOS-Prädikat."
            />
            <BranchOption
              selected={branch === "disjunct"}
              onSelect={() => setBranch("disjunct")}
              icon={<Split className="size-3.5" aria-hidden="true" />}
              label="Disjunkt: kein Mapping"
              description="Das Ausgangskonzept bekommt eine eigene Integrationsstrategie."
            />
          </div>
        </fieldset>

        {branch === "conjunct" ? (
          <Field label="Prädikat" required hint={PREDICATE_DESCRIPTIONS[predicate]}>
            {(props) => (
              <Select
                {...props}
                value={predicate}
                onChange={(event) => setPredicate(event.target.value as MappingPredicate)}
              >
                {MAPPING_PREDICATES.map((option) => (
                  <option key={option} value={option}>
                    {PREDICATE_LABELS[option]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        ) : (
          <>
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

            {needsContextLossNote ? (
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
          </>
        )}

        <Field label="Begründung" hint="Wird im Prüfbericht als Provenance dokumentiert.">
          {(props) => (
            <Textarea
              {...props}
              value={justification}
              onChange={(event) => setJustification(event.target.value)}
              placeholder="Warum ist diese Entscheidung zutreffend?"
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

        {reviewMutation.isError ? <ErrorPanel error={reviewMutation.error} /> : null}
      </div>

      <div className="flex justify-end border-t border-border-subtle px-4 py-3">
        <Button type="submit" variant="primary" loading={reviewMutation.isPending}>
          Entscheidung speichern
        </Button>
      </div>
    </form>
  );
}

function BranchOption({
  selected,
  onSelect,
  icon,
  label,
  description,
}: {
  selected: boolean;
  onSelect: () => void;
  icon: React.ReactNode;
  label: string;
  description: string;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "rounded-md border px-3 py-2.5 text-left transition-colors",
        selected
          ? "border-accent bg-accent-soft"
          : "border-border-subtle bg-surface hover:bg-surface-muted",
      )}
    >
      <span className="flex items-center gap-1.5 text-xs font-medium text-fg">
        {icon}
        {label}
      </span>
      <span className="mt-0.5 block text-xs text-fg-muted">{description}</span>
    </button>
  );
}
