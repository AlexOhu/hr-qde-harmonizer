/**
 * Readiness-Abschnitt des Exports.
 *
 * Zeigt, was einem vollstaendigen Export noch fehlt, und verlinkt direkt in
 * die passend gefilterte Arbeitsansicht. Die Bewertung selbst kommt aus
 * Backend-Werten (`export_ready`, Zaehler aus `/export/summary` und
 * Pipelinestatus); hier wird sie nur zusammengesetzt und benannt.
 */

import { AlertTriangle, CheckCircle2, Circle, Layers } from "lucide-react";
import { Link } from "react-router-dom";
import type { ReactNode } from "react";

import type { ExportSummary, PipelineStatus } from "@/api/types";
import { countActionableReviews, type FrameworkPair } from "@/features/pairs/status";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { formatNumber, formatPercent } from "@/lib/utils";

export interface ReadinessCheck {
  id: string;
  label: string;
  state: "ok" | "blocked" | "pending";
  detail?: string;
  action?: ReactNode;
}

/**
 * Leitet die Pruefpunkte aus dem Projektzustand ab.
 *
 * Clustering ist eine Voraussetzung des Ontologie-Exports (das Backend
 * antwortet sonst mit HTTP 409), blockiert SSSOM und Prüfbericht aber nicht.
 */
export function buildReadinessChecks({
  projectId,
  pairs,
  pipelineStatus,
  exportSummary,
  clusterCount,
  clusteringAction,
}: {
  projectId: string;
  pairs: FrameworkPair[];
  pipelineStatus: PipelineStatus | undefined;
  /**
   * `GET /export/summary` ist hier die massgebliche Quelle fuer die Paare
   * ohne Mehrheitsentscheid, die RELATED-Paare und die Coverage-Bilanz: sie
   * zaehlt projektweit und entspricht damit genau dem, was im Pruefbericht
   * landet. Die paarbezogenen `unresolved_count` aus dem Pipelinestatus liegen
   * niedriger, weil sie nur Faelle mit aufloesbarer Framework-Zuordnung
   * erfassen.
   *
   * Die vier Coverage-Felder werden uebernommen, nicht nachgerechnet: der
   * Nenner ist eine fachliche Festlegung des Backends (K vereinigt C_conf,
   * inklusive offener Reviews) und keine Anzeigeentscheidung.
   */
  exportSummary: ExportSummary | undefined;
  clusterCount: number | undefined;
  clusteringAction: ReactNode;
}): ReadinessCheck[] {
  const projectBase = `/projects/${encodeURIComponent(projectId)}`;

  const completedPairs = pairs.filter(
    (pair) => pair.leadingJobStatus === "completed",
  ).length;
  const openReviews = countActionableReviews(pairs);
  const noConsensus = exportSummary?.no_consensus_pairs ?? 0;
  const related = exportSummary?.related_pairs ?? 0;
  const openIntegrations = pipelineStatus?.disjoint_open ?? 0;
  const clusteringDone = pipelineStatus?.clustering_done ?? (clusterCount ?? 0) > 0;
  const coverageResolved = exportSummary?.coverage_resolved ?? 0;
  const coverageTotal = exportSummary?.coverage_total ?? 0;
  const openPairs = exportSummary?.open_review_count ?? 0;

  return [
    {
      id: "comparisons",
      label: `${formatNumber(completedPairs)} von ${formatNumber(pairs.length)} Vergleichen abgeschlossen`,
      state: pairs.length > 0 && completedPairs === pairs.length ? "ok" : "blocked",
      detail:
        pairs.length === 0
          ? "Für dieses Projekt wurde noch kein Framework-Paar verglichen."
          : completedPairs < pairs.length
            ? "Mindestens ein Lauf ist noch offen, unterbrochen oder gescheitert."
            : undefined,
      action:
        pairs.length === 0 || completedPairs < pairs.length ? (
          <Button asChild variant="secondary" size="sm">
            <Link to={projectBase}>Zu den Paaren</Link>
          </Button>
        ) : undefined,
    },
    {
      id: "review",
      label:
        openReviews === 0
          ? "Mapping-Review abgeschlossen"
          : `${formatNumber(openReviews)} Mappings benötigen eine Entscheidung`,
      state: openReviews === 0 ? "ok" : "blocked",
      detail:
        openReviews === 0
          ? undefined
          : "Enthält sowohl Mappings unterhalb der Konfidenzschwelle als auch offene Paare ohne Zuordnung (RELATED oder ohne LLM-Mehrheitsentscheid). Beide sind in der Mapping-Ansicht entscheidbar.",
      action:
        openReviews > 0 ? (
          <Button asChild variant="secondary" size="sm">
            <Link to={`${projectBase}/mappings?status=review`}>Mappings prüfen</Link>
          </Button>
        ) : undefined,
    },
    {
      id: "coverage",
      label:
        coverageTotal === 0
          ? "Noch keine Kandidatenpaare"
          : `${formatNumber(coverageResolved)} von ${formatNumber(coverageTotal)} Paaren entschieden (${formatPercent(exportSummary?.coverage_ratio ?? 0)})`,
      state: coverageTotal > 0 && openPairs === 0 ? "ok" : "pending",
      detail:
        coverageTotal === 0
          ? "Die Quote entsteht erst, wenn ein Framework-Paar klassifiziert wurde."
          : openPairs > 0
            ? `Der Nenner enthält auch die ${formatNumber(openPairs)} noch offenen Paare. Die Quote gibt damit den tatsächlichen Bearbeitungsstand wieder, nicht nur den der bereits entschiedenen Einträge.`
            : undefined,
    },
    {
      id: "unresolved",
      label:
        noConsensus === 0 && related === 0
          ? "Keine ungelösten Klassifikationen"
          : `${formatNumber(noConsensus)} ohne Mehrheitsentscheid und ${formatNumber(related)} „Verwandt“ ohne Zuordnung`,
      // Nicht blockierend, sondern aufschluesselnd: diese Paare stecken
      // bereits im blockierenden Pruefpunkt "review", der sie seit v0.2
      // mitzaehlt. Zweimal blockieren wuerde dieselbe Arbeit doppelt melden.
      state: noConsensus === 0 && related === 0 ? "ok" : "pending",
      detail:
        noConsensus === 0 && related === 0
          ? undefined
          : "Diese Paare gehören noch nicht zur konjunkten Menge K. Sie sind in der Mapping-Ansicht mit „wartet auf manuelle Entscheidung“ gekennzeichnet und lassen sich dort als konjunkt oder disjunkt entscheiden.",
      action:
        noConsensus > 0 || related > 0 ? (
          <Button asChild variant="secondary" size="sm">
            <Link to={`${projectBase}/mappings?status=open`}>Offene Paare entscheiden</Link>
          </Button>
        ) : undefined,
    },
    {
      id: "integration",
      label:
        openIntegrations === 0
          ? "Nicht zugeordnete Konzepte geklärt"
          : `${formatNumber(openIntegrations)} Konzepte ohne Integrationsentscheidung`,
      state: openIntegrations === 0 ? "ok" : "blocked",
      action:
        openIntegrations > 0 ? (
          <Button asChild variant="secondary" size="sm">
            <Link to={`${projectBase}/integration?status=open`}>Konzepte klären</Link>
          </Button>
        ) : undefined,
    },
    {
      id: "clustering",
      label: clusteringDone
        ? `Clustering ausgeführt${clusterCount ? ` (${formatNumber(clusterCount)} Cluster)` : ""}`
        : "Clustering noch nicht ausgeführt",
      state: clusteringDone ? "ok" : "pending",
      detail: clusteringDone
        ? undefined
        : "Der Ontologie-Export setzt die Clusterstruktur voraus. SSSOM und Prüfbericht sind davon unabhängig.",
      action: clusteringDone ? undefined : clusteringAction,
    },
  ];
}

export function ExportReadiness({ checks }: { checks: ReadinessCheck[] }) {
  const hasBlocking = checks.some((check) => check.state === "blocked");
  const hasPending = checks.some((check) => check.state === "pending");

  // Drei Stufen statt eines Bereit-Flags: "blocked" haelt einen Pflichtschritt
  // auf, "pending" laesst den Export zu, meldet aber einen noch unfertigen
  // Punkt (vor allem das fuer den Ontologie-Export noetige Clustering). Ein
  // pauschales "Alle Vorbedingungen sind erfuellt" waere dann irrefuehrend,
  // solange unten eine Ausstehend-Zeile mit eigener Aktion sichtbar ist.
  const level: "blocked" | "pending" | "ready" = hasBlocking
    ? "blocked"
    : hasPending
      ? "pending"
      : "ready";

  const HEADER: Record<typeof level, { title: string; description: string }> = {
    blocked: {
      title: "Export blockiert",
      description:
        "Offene Punkte werden nicht stillschweigend übergangen. Sie können trotzdem exportieren — der Prüfbericht dokumentiert dann die offenen Fälle.",
    },
    pending: {
      title: "Export bereit, einzelne Punkte offen",
      description:
        "Kein blockierender Schritt ist mehr offen, die Artefakte unten lassen sich erzeugen. Einzelne Punkte sind aber noch nicht abgeschlossen — vor allem der Ontologie-Export setzt die Clusterstruktur voraus. Die mit einem Kreis markierten Zeilen unten nennen den jeweils fehlenden Schritt.",
    },
    ready: {
      title: "Export bereit",
      description:
        "Alle Vorbedingungen sind erfüllt. Die Artefakte unten geben den vollständigen Projektstand wieder.",
    },
  };

  return (
    <Card>
      <CardHeader
        title={HEADER[level].title}
        description={HEADER[level].description}
        action={
          level === "ready" ? (
            <CheckCircle2 className="size-5 text-success" aria-hidden="true" />
          ) : level === "pending" ? (
            <Circle className="size-5 text-fg-subtle" aria-hidden="true" />
          ) : (
            <AlertTriangle className="size-5 text-warning" aria-hidden="true" />
          )
        }
      />
      <ul className="divide-y divide-border-subtle">
        {checks.map((check) => (
          <li key={check.id} className="flex items-start justify-between gap-4 px-4 py-2.5">
            <div className="flex min-w-0 items-start gap-2.5">
              <ReadinessIcon state={check.state} />
              <div className="min-w-0">
                <p className="text-xs font-medium text-fg">
                  <span className="sr-only">
                    {check.state === "ok"
                      ? "Erfüllt: "
                      : check.state === "blocked"
                        ? "Offen: "
                        : "Ausstehend: "}
                  </span>
                  {check.label}
                </p>
                {check.detail ? (
                  <p className="mt-0.5 text-xs text-fg-muted">{check.detail}</p>
                ) : null}
              </div>
            </div>
            {check.action ? <div className="shrink-0">{check.action}</div> : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}

function ReadinessIcon({ state }: { state: ReadinessCheck["state"] }) {
  if (state === "ok") {
    return <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-success" aria-hidden="true" />;
  }
  if (state === "blocked") {
    return <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden="true" />;
  }
  return <Circle className="mt-0.5 size-3.5 shrink-0 text-fg-subtle" aria-hidden="true" />;
}

export { Layers };
