/** Projektverwaltung (Backend-Routen unter `/projects`). */

import { request } from "./client";
import type { KqrRemovalResult, PipelineStatus, Project } from "./types";

export function listProjects(signal?: AbortSignal): Promise<Project[]> {
  return request<Project[]>("/projects/", { signal });
}

export function getProject(projectId: string, signal?: AbortSignal): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}`, { signal });
}

export interface CreateProjectInput {
  name: string;
  kqr_ids: string[];
  description?: string | null;
  hub_kqr_id?: string | null;
}

export function createProject(input: CreateProjectInput): Promise<Project> {
  return request<Project>("/projects/", { method: "POST", json: input });
}

export interface UpdateProjectInput {
  name?: string | null;
  description?: string | null;
}

export function updateProject(projectId: string, input: UpdateProjectInput): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}`, {
    method: "PUT",
    json: input,
  });
}

export function deleteProject(projectId: string): Promise<void> {
  return request<void>(`/projects/${encodeURIComponent(projectId)}`, { method: "DELETE" });
}

/**
 * Aggregierter Pipelinezustand. Enthaelt pro Klassifikationsjob einen
 * `kqr_pairs`-Eintrag — die Zusammenfuehrung zu Framework-Paaren erledigt
 * `features/pairs/status.ts`.
 */
export function getPipelineStatus(
  projectId: string,
  signal?: AbortSignal,
): Promise<PipelineStatus> {
  return request<PipelineStatus>(`/projects/${encodeURIComponent(projectId)}/pipeline-status`, {
    // Der Endpunkt aggregiert ueber alle Mappings und disjunkten Konzepte
    // und ist bei grossen Projekten (mehrere Tausend Mappings) traege.
    timeoutMs: 120_000,
    signal,
  });
}

/** Friert das Projekt als schreibgeschuetzte Kopie ein (ADR-06). */
export function createSnapshot(projectId: string, versionLabel: string): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}/snapshot`, {
    method: "POST",
    json: { version_label: versionLabel },
    timeoutMs: 120_000,
  });
}

export interface RemoveKqrFromProjectInput {
  author: string;
  justification?: string | null;
}

/**
 * Entfernt ein Framework projekt-scoped (guenstig, reversibel): das
 * Framework bleibt in der globalen Bibliothek erhalten, nur dieses Projekt
 * verliert die Referenz. Setzt dabei alle betroffenen Framework-Paare
 * dieses Projekts zurueck (vgl. classification_service.reset_pair). 400 bei
 * Hub- oder Snapshot-Konflikt.
 */
export function removeKqrFromProject(
  projectId: string,
  kqrId: string,
  input: RemoveKqrFromProjectInput,
): Promise<KqrRemovalResult> {
  return request<KqrRemovalResult>(
    `/projects/${encodeURIComponent(projectId)}/kqr/${encodeURIComponent(kqrId)}`,
    { method: "DELETE", json: input },
  );
}

/** Leeres Folgeprojekt mit anderem Framework-Set; uebernimmt keine Daten. */
export function forkProject(
  projectId: string,
  newName: string,
  newKqrIds: string[],
): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}/fork`, {
    method: "POST",
    json: { new_name: newName, new_kqr_ids: newKqrIds },
  });
}
