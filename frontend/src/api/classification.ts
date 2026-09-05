/** Klassifikationsjobs (Backend-Routen unter `/classification`). */

import { request } from "./client";
import type { ClassificationJob, PairResetEvent, PairResetResult, Preconditions } from "./types";

export function checkPreconditions(signal?: AbortSignal): Promise<Preconditions> {
  // Prueft u. a. die Neo4j-Verbindung; ein Verbindungs-Timeout dort kann
  // den Request merklich verzoegern.
  return request<Preconditions>("/classification/preconditions", { timeoutMs: 60_000, signal });
}

export function listJobs(projectId: string, signal?: AbortSignal): Promise<ClassificationJob[]> {
  return request<ClassificationJob[]>("/classification/", {
    params: { project_id: projectId },
    signal,
  });
}

export function getJobProgress(
  projectId: string,
  jobId: string,
  signal?: AbortSignal,
): Promise<ClassificationJob> {
  return request<ClassificationJob>(`/classification/${encodeURIComponent(jobId)}/progress`, {
    params: { project_id: projectId },
    signal,
  });
}

/**
 * Startet Schritt 2 (Vorfilter/ANN) plus Schritt 3 (LLM-Klassifikation) als
 * Hintergrundjob. Die Framework-IDs sind Query-Parameter, kein Request-Body
 * — so ist die Route im Backend definiert.
 *
 * Ein erneuter Start fuer dasselbe Paar ist der vom Backend vorgesehene Weg,
 * einen fehlgeschlagenen oder unterbrochenen Lauf fortzusetzen: bereits
 * klassifizierte Paare werden uebersprungen und kosten keine LLM-Aufrufe.
 */
export function startClassification(
  projectId: string,
  frameworkAId: string,
  frameworkBId: string,
): Promise<{ job_id: string }> {
  return request<{ job_id: string }>("/classification/start", {
    method: "POST",
    params: { project_id: projectId, kqr_a_id: frameworkAId, kqr_b_id: frameworkBId },
  });
}

/** Wirkt erst vor dem naechsten Konzeptpaar, nicht mitten im LLM-Aufruf. */
export function pauseJob(projectId: string, jobId: string): Promise<{ job_id: string }> {
  return request<{ job_id: string }>(`/classification/${encodeURIComponent(jobId)}/pause`, {
    method: "POST",
    params: { project_id: projectId },
  });
}

/** Setzt einen pausierten oder unterbrochenen Job unter derselben Job-ID fort. */
export function resumeJob(
  projectId: string,
  jobId: string,
): Promise<{ job_id: string; status: string }> {
  return request<{ job_id: string; status: string }>(
    `/classification/${encodeURIComponent(jobId)}/resume`,
    { method: "POST", params: { project_id: projectId } },
  );
}

export interface ResetPairInput {
  justification: string;
  author: string;
}

/**
 * Setzt ein bereits klassifiziertes Framework-Paar vollstaendig zurueck:
 * entfernt alle Mappings und die zugrunde liegenden Klassifikationsergebnisse,
 * damit ein erneuter Lauf jedes Konzeptpaar wieder klassifiziert statt es als
 * bereits erledigt zu ueberspringen. Anders als `startClassification` (Start/
 * Wiederholung) ist dies eine bewusst destruktive Aktion und verlangt deshalb
 * Begruendung und Autor (Accountability-Prinzip).
 */
export function resetPair(
  projectId: string,
  frameworkAId: string,
  frameworkBId: string,
  input: ResetPairInput,
): Promise<PairResetResult> {
  return request<PairResetResult>("/classification/pair/reset", {
    method: "POST",
    params: { project_id: projectId, kqr_a_id: frameworkAId, kqr_b_id: frameworkBId },
    json: input,
  });
}

/** Protokollierte Paar-Resets eines Projekts, neueste zuerst. */
export function listPairResetEvents(
  projectId: string,
  signal?: AbortSignal,
): Promise<PairResetEvent[]> {
  return request<PairResetEvent[]>("/classification/pair/reset-events", {
    params: { project_id: projectId },
    signal,
  });
}
