/**
 * Framework-Paare als zentrale Arbeitseinheit.
 *
 * Das Backend kennt keinen Paar-Begriff: `GET /projects/{id}/pipeline-status`
 * liefert einen `kqr_pairs`-Eintrag pro Klassifikationsjob. Ein Paar mit
 * mehreren Laeufen erscheint dort mehrfach, wobei alle Duplikate dieselben
 * Metriken tragen und sich nur in Job-ID, Job-Status und Fortschritt
 * unterscheiden.
 *
 * Dieses Modul fuehrt die Eintraege zu einem Paar zusammen und leitet daraus
 * einen Lifecycle-Status ab. Es erfindet dabei keine Kennzahlen: alle Zahlen
 * stammen unveraendert aus der API, abgeleitet wird ausschliesslich die
 * Zuordnung "Zahlenlage -> Statusbegriff", also eine Anzeigefrage.
 */

import type { ClassificationJob, JobStatus, PairStatus } from "@/api/types";
import { pairKey, timestampValue } from "@/lib/utils";

/** Sichtbarer Lebenszyklus eines Framework-Paars. */
export type PairLifecycle =
  | "running"
  | "paused"
  | "failed"
  | "interrupted"
  | "review_required"
  | "integration_required"
  | "complete"
  | "not_started";

export interface FrameworkPair {
  /** Reihenfolgeunabhaengiger Schluessel, siehe `pairKey`. */
  key: string;
  frameworkAId: string;
  frameworkAName: string;
  frameworkBId: string;
  frameworkBName: string;
  label: string;
  /** Der fuer die Anzeige massgebliche Lauf (siehe `pickLeadingEntry`). */
  leadingJobId: string | null;
  leadingJobStatus: JobStatus | null;
  /** Fehlermeldung des massgeblichen Laufs; nur bei lifecycle "failed" gesetzt. */
  error: string | null;
  lifecycle: PairLifecycle;
  classifiedPairs: number;
  totalPairs: number;
  /** 0–100, aus classified/total des massgeblichen Laufs. */
  percent: number;
  mappingsCount: number;
  pendingReviewCount: number;
  unresolvedCount: number;
  disjointTotal: number;
  disjointDecided: number;
  disjointOpen: number;
  /** Anzahl aller Laeufe dieses Paares (Run-Historie). */
  runCount: number;
}

/**
 * Rangfolge fuer die Auswahl des massgeblichen Laufs eines Paares.
 * Ein laufender Job ist immer die interessanteste Information; ein
 * abgeschlossener Lauf schlaegt einen frueher gescheiterten, weil das Paar
 * dann fachlich fertig klassifiziert ist.
 */
const JOB_STATUS_RANK: Record<JobStatus, number> = {
  running: 5,
  paused: 4,
  completed: 3,
  interrupted: 2,
  failed: 1,
};

function pickLeadingEntry(entries: PairStatus[]): PairStatus {
  return entries.reduce((best, candidate) => {
    const bestRank = best.job_status ? JOB_STATUS_RANK[best.job_status] : 0;
    const candidateRank = candidate.job_status ? JOB_STATUS_RANK[candidate.job_status] : 0;
    if (candidateRank !== bestRank) return candidateRank > bestRank ? candidate : best;
    // Gleicher Rang: der weiter fortgeschrittene Lauf gewinnt.
    return candidate.classified_pairs > best.classified_pairs ? candidate : best;
  });
}

/**
 * Leitet den Lifecycle allein aus Backend-Werten ab.
 *
 * Reihenfolge der Pruefung: Job-Zustaende zuerst (ein laufender oder
 * gescheiterter Lauf ist die dringendste Information), danach die offene
 * Arbeit in der Reihenfolge des Arbeitsablaufs — erst Mapping-Review, dann
 * Integrationsentscheidungen.
 */
export function derivePairLifecycle(entry: PairStatus): PairLifecycle {
  switch (entry.job_status) {
    case "running":
      return "running";
    case "paused":
      return "paused";
    case "failed":
      return "failed";
    case "interrupted":
      return "interrupted";
    case null:
    case undefined:
      return "not_started";
    case "completed":
      break;
  }

  if (entry.pending_review_count > 0 || entry.unresolved_count > 0) return "review_required";
  if (entry.disjoint_open > 0) return "integration_required";
  return "complete";
}

/** Fuehrt die job-bezogenen Eintraege zu einer Liste von Paaren zusammen. */
export function derivePairs(
  entries: PairStatus[],
  jobs: ClassificationJob[] = [],
): FrameworkPair[] {
  const grouped = new Map<string, PairStatus[]>();
  for (const entry of entries) {
    const key = pairKey(entry.kqr_a_id, entry.kqr_b_id);
    const bucket = grouped.get(key);
    if (bucket) bucket.push(entry);
    else grouped.set(key, [entry]);
  }

  return [...grouped.entries()].map(([key, group]) => {
    const leading = pickLeadingEntry(group);
    const runCount = jobs.filter(
      (job) => pairKey(job.kqr_a_id, job.kqr_b_id) === key,
    ).length;

    return {
      key,
      frameworkAId: leading.kqr_a_id,
      frameworkAName: leading.kqr_a_name,
      frameworkBId: leading.kqr_b_id,
      frameworkBName: leading.kqr_b_name,
      label: `${leading.kqr_a_name} ↔ ${leading.kqr_b_name}`,
      leadingJobId: leading.job_id,
      leadingJobStatus: leading.job_status,
      error: leading.error,
      lifecycle: derivePairLifecycle(leading),
      classifiedPairs: leading.classified_pairs,
      totalPairs: leading.total_pairs,
      percent:
        leading.total_pairs > 0
          ? Math.round((100 * leading.classified_pairs) / leading.total_pairs)
          : leading.job_status === "completed"
            ? 100
            : 0,
      mappingsCount: leading.mappings_count,
      pendingReviewCount: leading.pending_review_count,
      unresolvedCount: leading.unresolved_count,
      disjointTotal: leading.disjoint_total,
      disjointDecided: leading.disjoint_decided,
      disjointOpen: leading.disjoint_open,
      runCount: runCount || group.length,
    };
  });
}

/** Alle Laeufe eines Paares, neueste zuerst. */
export function runsForPair(
  jobs: ClassificationJob[],
  frameworkAId: string,
  frameworkBId: string,
): ClassificationJob[] {
  const key = pairKey(frameworkAId, frameworkBId);
  return jobs
    .filter((job) => pairKey(job.kqr_a_id, job.kqr_b_id) === key)
    .sort((a, b) => timestampValue(b.started_at) - timestampValue(a.started_at));
}

export function findPair(
  pairs: FrameworkPair[],
  frameworkAId: string,
  frameworkBId: string,
): FrameworkPair | undefined {
  const key = pairKey(frameworkAId, frameworkBId);
  return pairs.find((pair) => pair.key === key);
}

/** Ein Paar gilt als "in Arbeit", wenn es noch offene Punkte hat. */
export function pairHasOpenWork(pair: FrameworkPair): boolean {
  return (
    pair.pendingReviewCount > 0 || pair.unresolvedCount > 0 || pair.disjointOpen > 0
  );
}

/**
 * Summiert die Mappings, die im Mapping-Review tatsaechlich bearbeitet werden
 * koennen.
 *
 * `unresolvedCount` wird weiterhin nicht addiert — aber aus dem umgekehrten
 * Grund als frueher: der frueher hier dokumentierte API-Gap ist geschlossen.
 * RELATED/UNRESOLVED-Paare sind seit v0.2 persistiert, haben eine
 * `mapping_id` und stecken bereits in `pendingReviewCount`
 * (`mapping_service.needs_review()` zaehlt offenen Review-Status mit).
 * Beide Zahlen zu addieren wuerde dieselben Faelle doppelt zaehlen.
 */
export function countActionableReviews(pairs: FrameworkPair[]): number {
  return pairs.reduce((sum, pair) => sum + pair.pendingReviewCount, 0);
}

/** Summe der UNRESOLVED-Faelle; nur im Pruefbericht dokumentierbar. */
export function countUnresolved(pairs: FrameworkPair[]): number {
  return pairs.reduce((sum, pair) => sum + pair.unresolvedCount, 0);
}
