/** Clustering und Exportartefakte (Backend-Routen unter `/export`). */

import { download, request } from "./client";
import type { ClusterResult, DownloadedFile, ExportSummary, OntologyFormat } from "./types";

/** Gatekeeping-Zaehler, die vor dem Export angezeigt werden. */
export function getExportSummary(projectId: string, signal?: AbortSignal): Promise<ExportSummary> {
  return request<ExportSummary>("/export/summary", {
    params: { project_id: projectId },
    timeoutMs: 60_000,
    signal,
  });
}

export function getClusters(projectId: string, signal?: AbortSignal): Promise<ClusterResult[]> {
  return request<ClusterResult[]>("/export/clusters", {
    params: { project_id: projectId },
    signal,
  });
}

/**
 * Startet HDBSCAN (Schritt 2c, FZ2.3) synchron. Anders als die
 * Klassifikation gibt es dafuer keinen Hintergrundjob — der Request laeuft
 * bis zum Ergebnis durch, daher das grosszuegige Timeout.
 * `kqr_ids` erwartet das Backend als kommagetrennten Query-Parameter.
 */
export function runClustering(projectId: string, frameworkIds: string[]): Promise<ClusterResult[]> {
  return request<ClusterResult[]>("/export/clusters/run", {
    method: "POST",
    params: { project_id: projectId, kqr_ids: frameworkIds.join(",") },
    timeoutMs: 600_000,
  });
}

/** Blockiert mit HTTP 409, solange kein Clustering-Lauf vorliegt. */
export function exportOntology(
  projectId: string,
  format: OntologyFormat,
): Promise<DownloadedFile> {
  const extension = format === "turtle" ? "ttl" : format === "xml" ? "rdf" : "jsonld";
  return download(`/export/ontology`, `ontology.${extension}`, {
    method: "POST",
    params: { project_id: projectId, fmt: format },
  });
}

export function exportSssom(projectId: string): Promise<DownloadedFile> {
  return download("/export/sssom", "export.tsv", {
    method: "POST",
    params: { project_id: projectId },
  });
}

export function exportAuditReport(projectId: string): Promise<DownloadedFile> {
  return download("/export/audit-report", "audit.md", {
    method: "POST",
    params: { project_id: projectId },
  });
}
