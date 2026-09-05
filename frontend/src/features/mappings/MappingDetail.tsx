/**
 * Detailspalte des Mapping-Reviews.
 *
 * Drei Zustaende, in dieser Reihenfolge geprueft:
 * 1. Offener Review (RELATED oder ohne Mehrheitsentscheid): die
 *    Konjunkt/Disjunkt-Weiche aus FZ3.2, siehe `MappingReviewForm`.
 * 2. Konfidenz unterhalb der Schwelle: das bestehende Korrekturformular.
 * 3. Sonst nur Ansicht — automatisch akzeptierte Mappings bekommen kein
 *    Bearbeitungsformular.
 *
 * Begruendung und Autor sind Pflichtfelder (FA4).
 */

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, UserPen } from "lucide-react";

import type { Mapping, MappingPredicate } from "@/api/types";
import { MAPPING_PREDICATES } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { DetailField, DetailPanel } from "@/components/common/MasterDetail";
import { ErrorPanel } from "@/components/common/states";
import { useToast } from "@/components/ui/toast";
import { useUpdateMapping } from "@/hooks/useMappings";
import {
  JUSTIFICATION_DESCRIPTIONS,
  JUSTIFICATION_LABELS,
  PREDICATE_LABELS,
  isAwaitingReview,
  predicateDescription,
  predicateLabel,
} from "./mappingPresentation";
import { MappingReviewForm } from "./MappingReviewForm";
import { formatConfidence, formatDateTime } from "@/lib/utils";

export function MappingDetail({
  mapping,
  projectId,
  threshold,
  isReadOnly,
}: {
  mapping: Mapping;
  projectId: string;
  threshold: number;
  isReadOnly: boolean;
}) {
  const { toast } = useToast();
  const updateMutation = useUpdateMapping(projectId);

  const awaitsReview = isAwaitingReview(mapping);
  const isManual = mapping.mapping_source === "manual";
  const needsReview = !awaitsReview && !isManual && mapping.mapping_confidence < threshold;

  // Ein Mapping im Korrekturformular ist entschieden und trägt daher ein
  // Prädikat; der Fallback greift nie, hält aber den Typ non-null.
  const [predicate, setPredicate] = useState<MappingPredicate>(
    mapping.predicate_id ?? "skos:relatedMatch",
  );
  const [justification, setJustification] = useState("");
  const [author, setAuthor] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // Beim Wechsel des ausgewaehlten Mappings darf kein Text des vorigen
  // Formulars stehen bleiben — sonst wird versehentlich die falsche
  // Begruendung gespeichert.
  useEffect(() => {
    setPredicate(mapping.predicate_id ?? "skos:relatedMatch");
    setJustification("");
    setAuthor("");
    setFormError(null);
    updateMutation.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapping.mapping_id]);

  function submit() {
    if (!justification.trim()) {
      setFormError("Eine Begründung ist verpflichtend zu dokumentieren.");
      return;
    }
    if (!author.trim()) {
      setFormError("Bitte tragen Sie ein, wer diese Entscheidung trifft.");
      return;
    }
    setFormError(null);
    updateMutation.mutate(
      {
        mappingId: mapping.mapping_id,
        input: { predicate, justification: justification.trim(), author: author.trim() },
      },
      {
        onSuccess: () => {
          toast({
            title: "Entscheidung gespeichert",
            description: `${mapping.subject_label} → ${PREDICATE_LABELS[predicate]}`,
          });
        },
      },
    );
  }

  return (
    <DetailPanel>
      <div className="rounded-lg border border-border-subtle bg-surface">
        <div className="border-b border-border-subtle px-4 py-4">
          <ConceptSide
            label="Subjekt"
            conceptLabel={mapping.subject_label}
            uri={mapping.subject_id}
            frameworkId={mapping.subject_kqr_id}
          />
          <div className="my-3 flex items-center gap-3">
            <div className="h-px flex-1 bg-border-subtle" />
            <Badge tone="neutral" className="font-mono">
              {mapping.predicate_id ?? "—"}
            </Badge>
            <div className="h-px flex-1 bg-border-subtle" />
          </div>
          <ConceptSide
            label="Objekt"
            conceptLabel={mapping.object_label}
            uri={mapping.object_id}
            frameworkId={mapping.object_kqr_id}
          />
        </div>

        <dl className="grid grid-cols-2 gap-4 px-4 py-4 sm:grid-cols-3">
          <DetailField label="Konfidenz">
            <span className="tabular-nums">{formatConfidence(mapping.mapping_confidence)}</span>
            <span className="ml-1.5 text-fg-subtle">
              (Schwelle {formatConfidence(threshold)})
            </span>
          </DetailField>
          <DetailField label="Aktuelle Relation">
            {predicateLabel(mapping.predicate_id)}
          </DetailField>
          {/* Herkunft sichtbar machen: an mapping_justification erkennt eine
              Reviewerin, ob ein relatedMatch bereits im Review bestaetigt
              wurde oder noch algorithmisch unbestaetigt ist. */}
          <DetailField label="Verfahren">
            <span title={JUSTIFICATION_DESCRIPTIONS[mapping.mapping_justification]}>
              {JUSTIFICATION_LABELS[mapping.mapping_justification] ??
                mapping.mapping_justification}
            </span>
            <span className="ml-1.5 font-mono text-[0.6875rem] text-fg-subtle">
              {mapping.mapping_justification}
            </span>
          </DetailField>
          <DetailField label="Herkunft">
            {isManual ? "Manuell entschieden" : "Automatisch erzeugt"}
          </DetailField>
          <DetailField label="Werkzeug" mono>
            {mapping.mapping_tool}
          </DetailField>
          <DetailField label="Erstellt">{formatDateTime(mapping.created_at)}</DetailField>
        </dl>

        {isManual ? (
          <div className="border-t border-border-subtle bg-success-soft/40 px-4 py-3">
            <div className="flex items-center gap-2">
              <UserPen className="size-3.5 text-success" aria-hidden="true" />
              <span className="text-xs font-medium text-fg">
                Manuell entschieden von {mapping.author ?? "unbekannt"}
              </span>
            </div>
            {mapping.justification ? (
              <p className="mt-1.5 text-xs text-fg-muted">{mapping.justification}</p>
            ) : null}
          </div>
        ) : null}
      </div>

      {awaitsReview ? (
        <p className="mt-4 flex items-start gap-2 rounded-lg border border-warning/30 bg-warning-soft p-3 text-xs text-fg-muted">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden="true" />
          <span>
            Wartet auf manuelle Entscheidung: Die Klassifikation kam zu{" "}
            {predicateLabel(mapping.predicate_id)} und hat damit keine Zuordnung getroffen.
          </span>
        </p>
      ) : null}

      {awaitsReview && !isReadOnly ? (
        <MappingReviewForm mapping={mapping} projectId={projectId} />
      ) : null}

      {awaitsReview && isReadOnly ? (
        <p className="mt-4 rounded-lg border border-border-subtle bg-surface-muted p-3 text-xs text-fg-muted">
          In einem Snapshot ist dieses Paar schreibgeschützt — leiten Sie das Projekt ab (Fork), um
          die Entscheidung zu treffen.
        </p>
      ) : null}

      {needsReview && !isReadOnly ? (
        <form
          className="mt-4 rounded-lg border border-border-subtle bg-surface"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <div className="border-b border-border-subtle px-4 py-3">
            <h3 className="text-sm font-semibold text-fg">Manuelle Entscheidung</h3>
            <p className="mt-0.5 text-xs text-fg-muted">
              Die Konfidenz liegt unter der Schwelle. Ihre Entscheidung wird mit Begründung und
              Autor dokumentiert und ersetzt die automatische Einschätzung.
            </p>
          </div>

          <div className="space-y-4 px-4 py-4">
            <Field label="Relation" required hint={predicateDescription(predicate)}>
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

            <Field label="Begründung" required error={formError}>
              {(props) => (
                <Textarea
                  {...props}
                  value={justification}
                  onChange={(event) => setJustification(event.target.value)}
                  placeholder="Warum ist diese Relation zutreffend?"
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

            {updateMutation.isError ? <ErrorPanel error={updateMutation.error} /> : null}
          </div>

          <div className="flex justify-end border-t border-border-subtle px-4 py-3">
            <Button type="submit" variant="primary" loading={updateMutation.isPending}>
              Entscheidung speichern
            </Button>
          </div>
        </form>
      ) : null}

      {needsReview && isReadOnly ? (
        <p className="mt-4 rounded-lg border border-border-subtle bg-surface-muted p-3 text-xs text-fg-muted">
          Dieses Mapping wartet auf eine manuelle Entscheidung. In einem Snapshot ist es
          schreibgeschützt — leiten Sie das Projekt ab (Fork), um daran weiterzuarbeiten.
        </p>
      ) : null}

      {!needsReview && !awaitsReview && !isManual ? (
        <p className="mt-4 flex items-start gap-2 rounded-lg border border-success/25 bg-success-soft p-3 text-xs text-fg-muted">
          <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-success" aria-hidden="true" />
          <span>
            Automatisch akzeptiert: Die Konfidenz erreicht die Schwelle von{" "}
            {formatConfidence(threshold)}. Es ist keine manuelle Entscheidung nötig.
          </span>
        </p>
      ) : null}
    </DetailPanel>
  );
}

function ConceptSide({
  label,
  conceptLabel,
  uri,
  frameworkId,
}: {
  label: string;
  conceptLabel: string;
  uri: string;
  frameworkId: string | null;
}) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-2">
        <span className="text-[0.6875rem] font-medium tracking-wide text-fg-subtle uppercase">
          {label}
        </span>
        {frameworkId ? (
          <Badge tone="neutral" className="font-mono">
            {frameworkId}
          </Badge>
        ) : null}
      </div>
      <p className="mt-1 text-sm font-medium text-fg">{conceptLabel}</p>
      <p className="mt-0.5 font-mono text-[0.6875rem] break-all text-fg-subtle">{uri}</p>
    </div>
  );
}
