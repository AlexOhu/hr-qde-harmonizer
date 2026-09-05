/** Framework-Bibliothek (Backend-Routen unter `/kqr`). Global, projektunabhaengig. */

import { request } from "./client";
import type { Framework, FrameworkStatusDetail } from "./types";

export function listFrameworks(signal?: AbortSignal): Promise<Framework[]> {
  return request<Framework[]>("/kqr/", { signal });
}

export function getFrameworkStatus(
  frameworkId: string,
  signal?: AbortSignal,
): Promise<FrameworkStatusDetail> {
  return request<FrameworkStatusDetail>(`/kqr/${encodeURIComponent(frameworkId)}/status`, {
    signal,
  });
}

export interface UploadFrameworkInput {
  name: string;
  sourceFormat: string;
  isHub: boolean;
  file: File;
}

/**
 * `POST /kqr/` erwartet Multipart-Form-Daten (`Form(...)` + `UploadFile`),
 * kein JSON. Der Content-Type darf hier NICHT gesetzt werden, damit der
 * Browser die Multipart-Boundary selbst ergaenzt.
 */
export function uploadFramework({
  name,
  sourceFormat,
  isHub,
  file,
}: UploadFrameworkInput): Promise<Framework> {
  const form = new FormData();
  form.set("name", name);
  form.set("source_format", sourceFormat);
  form.set("is_hub", String(isHub));
  form.set("file", file, file.name);
  // Grosse Turtle-Dumps werden serverseitig direkt validiert, geparst und
  // eingebettet — das dauert deutlich laenger als ein normaler Request.
  return request<Framework>("/kqr/", { method: "POST", body: form, timeoutMs: 600_000 });
}

/** Berechnet Embeddings und hebt den Status von `formalisiert` auf `bereit`. */
export function embedFramework(frameworkId: string): Promise<Framework> {
  return request<Framework>(`/kqr/${encodeURIComponent(frameworkId)}/embed`, {
    method: "POST",
    timeoutMs: 600_000,
  });
}

/**
 * Loescht ein Framework endgueltig aus der globalen Bibliothek (destruktiv).
 * Das Backend blockiert mit 409, solange irgendein Projekt das Framework
 * noch referenziert -- es muss zuerst dort entfernt werden
 * (`removeKqrFromProject`).
 */
export function deleteKqrGlobally(frameworkId: string): Promise<void> {
  return request<void>(`/kqr/${encodeURIComponent(frameworkId)}`, { method: "DELETE" });
}
