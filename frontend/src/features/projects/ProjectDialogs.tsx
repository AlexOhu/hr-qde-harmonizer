/**
 * Projektaktionen als Dialoge.
 *
 * Anlegen, Umbenennen, Snapshot, Fork und Loeschen sind Aktionen auf einem
 * Projekt, keine Navigationsziele — sie duerfen die Arbeitsflaeche nicht
 * belegen, sondern erscheinen auf Anforderung.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import type { Framework, Project } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Checkbox, Field, Input, Select, Textarea } from "@/components/ui/field";
import { ErrorPanel } from "@/components/common/states";
import { useToast } from "@/components/ui/toast";
import {
  useCreateProject,
  useCreateSnapshot,
  useDeleteProject,
  useForkProject,
  useUpdateProject,
} from "@/hooks/useProjects";
import { useFrameworks, isFrameworkReady } from "@/hooks/useFrameworks";

/** Auswahlliste der Frameworks, die ein Projekt referenzieren darf. */
function FrameworkPicker({
  frameworks,
  selectedIds,
  onToggle,
  emptyHint,
}: {
  frameworks: Framework[];
  selectedIds: string[];
  onToggle: (frameworkId: string) => void;
  emptyHint: string;
}) {
  if (frameworks.length === 0) {
    return <p className="text-xs text-fg-muted">{emptyHint}</p>;
  }
  return (
    <div className="max-h-48 space-y-1.5 overflow-y-auto rounded-md border border-border-subtle p-2.5">
      {frameworks.map((framework) => (
        <Checkbox
          key={framework.id}
          checked={selectedIds.includes(framework.id)}
          onChange={() => onToggle(framework.id)}
          label={
            <span>
              {framework.name}
              {framework.is_hub ? (
                <span className="ml-1.5 text-fg-subtle">· Hub</span>
              ) : null}
              <span className="ml-1.5 font-mono text-[0.6875rem] text-fg-subtle">
                {framework.id}
              </span>
            </span>
          }
        />
      ))}
    </div>
  );
}

export function CreateProjectDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const { toast } = useToast();
  const frameworksQuery = useFrameworks();
  const createMutation = useCreateProject();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [hubId, setHubId] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  // Nur vergleichsfaehige Frameworks sind waehlbar (Action Constraint).
  const readyFrameworks = (frameworksQuery.data ?? []).filter(isFrameworkReady);
  const selectedFrameworks = readyFrameworks.filter((f) => selectedIds.includes(f.id));

  function toggle(frameworkId: string) {
    setSelectedIds((current) =>
      current.includes(frameworkId)
        ? current.filter((id) => id !== frameworkId)
        : [...current, frameworkId],
    );
    setHubId((current) => (current === frameworkId ? "" : current));
  }

  function submit() {
    if (!name.trim()) {
      setValidationError("Ein Projektname ist erforderlich.");
      return;
    }
    if (selectedIds.length === 0) {
      setValidationError("Mindestens ein Framework auswählen.");
      return;
    }
    setValidationError(null);
    createMutation.mutate(
      {
        name: name.trim(),
        kqr_ids: selectedIds,
        description: description.trim() || null,
        hub_kqr_id: hubId || null,
      },
      {
        onSuccess: (project) => {
          toast({ title: "Projekt angelegt", description: project.name });
          onOpenChange(false);
          navigate(`/projects/${encodeURIComponent(project.project_id)}`);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="Neues Projekt"
        description="Ein Projekt bündelt eine Auswahl an Frameworks und alle daraus entstehenden Mappings, Entscheidungen und Exporte."
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost">Abbrechen</Button>
            </DialogClose>
            <Button variant="primary" onClick={submit} loading={createMutation.isPending}>
              Projekt anlegen
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
                placeholder="z. B. IT-Harmonisierung 2026"
                autoFocus
              />
            )}
          </Field>

          <Field label="Beschreibung">
            {(props) => (
              <Textarea
                {...props}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Optional: Zweck und Umfang des Projekts"
              />
            )}
          </Field>

          <div className="space-y-1.5">
            <div className="text-xs font-medium text-fg">
              Frameworks <span className="text-danger">*</span>
            </div>
            <FrameworkPicker
              frameworks={readyFrameworks}
              selectedIds={selectedIds}
              onToggle={toggle}
              emptyHint="Kein Framework hat den Status „Bereit“. Zuerst in der Framework-Bibliothek hochladen und Embeddings berechnen."
            />
            <p className="text-xs text-fg-subtle">
              Nur Frameworks mit dem Status „Bereit“ können verglichen werden.
            </p>
          </div>

          <Field
            label="Hub-Framework"
            hint="Ankerpunkt aller Vergleiche, üblicherweise ESCO. Optional."
          >
            {(props) => (
              <Select
                {...props}
                value={hubId}
                onChange={(event) => setHubId(event.target.value)}
                disabled={selectedFrameworks.length === 0}
              >
                <option value="">— kein Hub —</option>
                {selectedFrameworks.map((framework) => (
                  <option key={framework.id} value={framework.id}>
                    {framework.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          {createMutation.isError ? <ErrorPanel error={createMutation.error} /> : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function RenameProjectDialog({
  project,
  open,
  onOpenChange,
}: {
  project: Project;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { toast } = useToast();
  const updateMutation = useUpdateProject(project.project_id);
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description ?? "");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="Projekt umbenennen"
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost">Abbrechen</Button>
            </DialogClose>
            <Button
              variant="primary"
              loading={updateMutation.isPending}
              onClick={() =>
                updateMutation.mutate(
                  { name: name.trim(), description: description.trim() },
                  {
                    onSuccess: () => {
                      toast({ title: "Projekt aktualisiert" });
                      onOpenChange(false);
                    },
                  },
                )
              }
              disabled={!name.trim()}
            >
              Speichern
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Name" required>
            {(props) => (
              <Input {...props} value={name} onChange={(event) => setName(event.target.value)} />
            )}
          </Field>
          <Field label="Beschreibung">
            {(props) => (
              <Textarea
                {...props}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            )}
          </Field>
          {updateMutation.isError ? <ErrorPanel error={updateMutation.error} /> : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function SnapshotDialog({
  project,
  open,
  onOpenChange,
}: {
  project: Project;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { toast } = useToast();
  const snapshotMutation = useCreateSnapshot();
  // Der Dialog montiert beim Öffnen neu, daher genügt der Initialwert.
  const [label, setLabel] = useState(() => `Stand ${new Date().toISOString().slice(0, 10)}`);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="Snapshot erstellen"
        description="Ein Snapshot friert den aktuellen Projektstand als schreibgeschützte Kopie ein. Das Originalprojekt bleibt unverändert bearbeitbar."
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost">Abbrechen</Button>
            </DialogClose>
            <Button
              variant="primary"
              loading={snapshotMutation.isPending}
              disabled={!label.trim()}
              onClick={() =>
                snapshotMutation.mutate(
                  { projectId: project.project_id, versionLabel: label.trim() },
                  {
                    onSuccess: (snapshot) => {
                      toast({ title: "Snapshot erstellt", description: snapshot.name });
                      onOpenChange(false);
                    },
                  },
                )
              }
            >
              Snapshot erstellen
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Versionsbezeichnung" required>
            {(props) => (
              <Input
                {...props}
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                placeholder="z. B. v0.3 oder Stand vor Review"
                autoFocus
              />
            )}
          </Field>
          {snapshotMutation.isError ? <ErrorPanel error={snapshotMutation.error} /> : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function ForkProjectDialog({
  project,
  open,
  onOpenChange,
}: {
  project: Project;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const { toast } = useToast();
  const frameworksQuery = useFrameworks();
  const forkMutation = useForkProject();

  const [name, setName] = useState(`${project.name} (Fork)`);
  const [selectedIds, setSelectedIds] = useState<string[]>(project.kqr_ids);

  const readyFrameworks = (frameworksQuery.data ?? []).filter(isFrameworkReady);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="Projekt ableiten"
        description="Ein Fork startet leer mit einer neuen Framework-Auswahl. Mappings und Entscheidungen werden nicht übernommen; die Herkunft bleibt dokumentiert."
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost">Abbrechen</Button>
            </DialogClose>
            <Button
              variant="primary"
              loading={forkMutation.isPending}
              disabled={!name.trim() || selectedIds.length === 0}
              onClick={() =>
                forkMutation.mutate(
                  {
                    projectId: project.project_id,
                    newName: name.trim(),
                    newKqrIds: selectedIds,
                  },
                  {
                    onSuccess: (forked) => {
                      toast({ title: "Projekt abgeleitet", description: forked.name });
                      onOpenChange(false);
                      navigate(`/projects/${encodeURIComponent(forked.project_id)}`);
                    },
                  },
                )
              }
            >
              Fork erstellen
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Name des neuen Projekts" required>
            {(props) => (
              <Input {...props} value={name} onChange={(event) => setName(event.target.value)} />
            )}
          </Field>
          <div className="space-y-1.5">
            <div className="text-xs font-medium text-fg">
              Frameworks <span className="text-danger">*</span>
            </div>
            <FrameworkPicker
              frameworks={readyFrameworks}
              selectedIds={selectedIds}
              onToggle={(id) =>
                setSelectedIds((current) =>
                  current.includes(id) ? current.filter((x) => x !== id) : [...current, id],
                )
              }
              emptyHint="Kein Framework hat den Status „Bereit“."
            />
          </div>
          {forkMutation.isError ? <ErrorPanel error={forkMutation.error} /> : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function DeleteProjectDialog({
  project,
  open,
  onOpenChange,
}: {
  project: Project;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { toast } = useToast();
  const deleteMutation = useDeleteProject();
  const [confirmed, setConfirmed] = useState(false);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="Projekt löschen"
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost">Abbrechen</Button>
            </DialogClose>
            <Button
              variant="danger"
              disabled={!confirmed}
              loading={deleteMutation.isPending}
              onClick={() =>
                deleteMutation.mutate(project.project_id, {
                  onSuccess: () => {
                    toast({ title: "Projekt gelöscht", description: project.name });
                    onOpenChange(false);
                  },
                })
              }
            >
              Endgültig löschen
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <p className="text-xs text-fg-muted">
            Das Projekt <strong className="text-fg">{project.name}</strong> und alle zugehörigen
            Daten (Mappings, Integrationsentscheidungen, Clustering, Exporte) werden unwiderruflich
            gelöscht.
          </p>
          <Checkbox
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
            label="Ja, dieses Projekt endgültig löschen"
          />
          {deleteMutation.isError ? <ErrorPanel error={deleteMutation.error} /> : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
