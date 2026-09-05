/**
 * Framework hinzufuegen.
 *
 * Bewusst ein Dialog und nicht ein Formular im Projekt-Dashboard: Frameworks
 * sind globale Ressourcen, die Bibliothek ist ihr Ort.
 */

import { useRef, useState } from "react";

import type { Framework } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Checkbox, Field, Input, Select } from "@/components/ui/field";
import { ErrorPanel } from "@/components/common/states";
import { useToast } from "@/components/ui/toast";
import { useUploadFramework } from "@/hooks/useFrameworks";

/**
 * `rdf`/`turtle` importiert das Backend direkt (Validierung, Parsen,
 * Embedding in einem Schritt). Die uebrigen Formate landen im Status `roh`
 * und brauchen den separaten, hier nicht automatisierten
 * Formalisierungsschritt.
 */
const SOURCE_FORMATS = [
  { value: "turtle", label: "Turtle (.ttl) — Direktimport" },
  { value: "rdf", label: "RDF/XML — Direktimport" },
  { value: "pdf", label: "PDF — Formalisierung erforderlich" },
  { value: "xml", label: "XML — Formalisierung erforderlich" },
  { value: "csv", label: "CSV — Formalisierung erforderlich" },
] as const;

export function AddFrameworkDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { toast } = useToast();
  const uploadMutation = useUploadFramework();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [name, setName] = useState("");
  const [sourceFormat, setSourceFormat] = useState<string>("turtle");
  const [isHub, setIsHub] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  function describeOutcome(framework: Framework): { title: string; description: string } {
    switch (framework.status) {
      case "bereit":
        return {
          title: "Framework ist bereit",
          description: `${framework.name}: ${framework.concept_count ?? "?"} Konzepte eingelesen und eingebettet.`,
        };
      case "formalisiert":
        return {
          title: "Framework eingelesen",
          description: `${framework.name}: ${framework.concept_count ?? "?"} Konzepte. Embeddings müssen noch berechnet werden.`,
        };
      default:
        return {
          title: "Validierung fehlgeschlagen",
          description: `${framework.name} wurde gespeichert, erfüllt das SKOS-Minimalschema aber noch nicht.`,
        };
    }
  }

  function submit() {
    if (!name.trim()) {
      setValidationError("Ein Name ist erforderlich.");
      return;
    }
    if (!file) {
      setValidationError("Eine Datei ist erforderlich.");
      return;
    }
    setValidationError(null);

    uploadMutation.mutate(
      { name: name.trim(), sourceFormat, isHub, file },
      {
        onSuccess: (framework) => {
          const outcome = describeOutcome(framework);
          toast({
            ...outcome,
            tone: framework.status === "roh" ? "error" : "success",
          });
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="Framework hinzufügen"
        description="Turtle- und RDF-Dateien werden sofort validiert, eingelesen und eingebettet. Andere Formate erfordern einen vorgelagerten Formalisierungsschritt."
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost">Abbrechen</Button>
            </DialogClose>
            <Button variant="primary" onClick={submit} loading={uploadMutation.isPending}>
              Hinzufügen
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Name" required error={validationError}>
            {(props) => (
              <Input
                {...props}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="z. B. e-CF, EQF, O*NET"
                autoFocus
              />
            )}
          </Field>

          <Field label="Ausgangsformat" required>
            {(props) => (
              <Select
                {...props}
                value={sourceFormat}
                onChange={(event) => setSourceFormat(event.target.value)}
              >
                {SOURCE_FORMATS.map((format) => (
                  <option key={format.value} value={format.value}>
                    {format.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <Field label="Datei" required>
            {(props) => (
              <input
                {...props}
                ref={fileInputRef}
                type="file"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                className="w-full text-xs text-fg-muted file:mr-3 file:rounded-md file:border file:border-border-strong file:bg-surface file:px-2.5 file:py-1 file:text-xs file:font-medium file:text-fg hover:file:bg-surface-muted"
              />
            )}
          </Field>

          <Checkbox
            checked={isHub}
            onChange={(event) => setIsHub(event.target.checked)}
            label="Hub-Framework (Ankerpunkt aller Vergleiche, z. B. ESCO)"
          />

          {uploadMutation.isPending ? (
            <p className="text-xs text-fg-muted">
              Große Dumps werden serverseitig validiert, geparst und eingebettet. Das kann einige
              Minuten dauern.
            </p>
          ) : null}

          {uploadMutation.isError ? <ErrorPanel error={uploadMutation.error} /> : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
