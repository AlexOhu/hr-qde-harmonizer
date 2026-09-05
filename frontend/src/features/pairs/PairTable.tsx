/**
 * Liste der Framework-Vergleiche — die zentrale Darstellung der
 * Projektuebersicht.
 *
 * Jede Zeile beantwortet fuenf Fragen auf einen Blick: Welche Frameworks?
 * Welcher Zustand? Welches Ergebnis? Welche Arbeit ist offen? Was ist die
 * naechste Aktion? Genau eine primaere Aktion pro Zeile (Action Proximity) —
 * ihre Herleitung steht in `resolvePairAction`.
 */

import { ArrowRight, RotateCcw, RotateCw } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tooltip } from "@/components/ui/tooltip";
import { PAIR_LIFECYCLE_PRESENTATION, PairStatusBadge } from "./PairStatusBadge";
import type { FrameworkPair } from "./status";
import { formatNumber, pluralize } from "@/lib/utils";

export function pairPath(projectId: string, pair: FrameworkPair): string {
  return `/projects/${encodeURIComponent(projectId)}/pairs/${encodeURIComponent(
    pair.frameworkAId,
  )}/${encodeURIComponent(pair.frameworkBId)}`;
}

type PairAction =
  | { kind: "link"; label: string; to: string; variant: "primary" | "secondary" }
  | { kind: "retry"; label: string; variant: "primary" | "secondary" }
  | null;

/**
 * Leitet die eine sinnvolle Folgeaktion einer Zeile ab. Laufende und
 * gescheiterte Laeufe sind dringender als offene Fachaufgaben, die wiederum
 * vor einem reinen "Ansehen" kommen.
 */
export function resolvePairAction(
  pair: FrameworkPair,
  href: string,
  isReadOnly: boolean,
): PairAction {
  switch (pair.lifecycle) {
    case "not_started":
      return isReadOnly ? null : { kind: "retry", label: "Vergleich starten", variant: "primary" };
    case "running":
      return { kind: "link", label: "Status ansehen", to: href, variant: "secondary" };
    case "paused":
      return { kind: "link", label: "Fortsetzen", to: href, variant: "primary" };
    case "failed":
    case "interrupted":
      return isReadOnly
        ? { kind: "link", label: "Ansehen", to: href, variant: "secondary" }
        : { kind: "retry", label: "Erneut versuchen", variant: "primary" };
    case "review_required":
      return {
        kind: "link",
        label: "Mappings prüfen",
        to: `${href}/mappings?status=review`,
        variant: "primary",
      };
    case "integration_required":
      return {
        kind: "link",
        label: "Konzepte klären",
        to: `${href}/unmapped?status=open`,
        variant: "primary",
      };
    case "complete":
      return { kind: "link", label: "Details ansehen", to: href, variant: "secondary" };
  }
}

export function PairTable({
  projectId,
  pairs,
  onRetry,
  onReset,
  isReadOnly,
}: {
  projectId: string;
  pairs: FrameworkPair[];
  /** Startet bzw. wiederholt einen Lauf; im Snapshot nicht verfuegbar. */
  onRetry: (pair: FrameworkPair) => void;
  /** Oeffnet den Reset-Dialog fuer ein bereits klassifiziertes Paar; im Snapshot nicht verfuegbar. */
  onReset: (pair: FrameworkPair) => void;
  isReadOnly: boolean;
}) {
  return (
    <ul
      aria-label="Framework-Vergleiche mit Status, Ergebnis und empfohlener Aktion"
      className="divide-y divide-border-subtle rounded-lg border border-border-subtle bg-surface"
    >
      {pairs.map((pair) => (
        <PairRow
          key={pair.key}
          projectId={projectId}
          pair={pair}
          onRetry={onRetry}
          onReset={onReset}
          isReadOnly={isReadOnly}
        />
      ))}
    </ul>
  );
}

function PairRow({
  projectId,
  pair,
  onRetry,
  onReset,
  isReadOnly,
}: {
  projectId: string;
  pair: FrameworkPair;
  onRetry: (pair: FrameworkPair) => void;
  onReset: (pair: FrameworkPair) => void;
  isReadOnly: boolean;
}) {
  const href = pairPath(projectId, pair);
  const action = resolvePairAction(pair, href, isReadOnly);
  // Zuruecksetzen ist eine sekundaere, destruktive Aktion: sie greift nur,
  // wenn ueberhaupt schon klassifiziert wurde, und nicht im Snapshot.
  const canReset = !isReadOnly && pair.lifecycle !== "not_started";

  return (
    <li className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={href}
            className="text-sm font-medium text-fg hover:text-accent hover:underline"
          >
            {pair.label}
          </Link>
          <PairStatusBadge lifecycle={pair.lifecycle} />
        </div>
        <p className="mt-0.5 font-mono text-[0.6875rem] text-fg-subtle">
          {pair.frameworkAId} ↔ {pair.frameworkBId}
        </p>

        <div className="mt-2">
          <PairRowBody pair={pair} href={href} />
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:pl-4">
        {canReset ? (
          <Button variant="danger" size="sm" onClick={() => onReset(pair)}>
            <RotateCcw aria-hidden="true" />
            Zurücksetzen
          </Button>
        ) : null}
        <PairRowAction pair={pair} action={action} onRetry={onRetry} />
      </div>
    </li>
  );
}

/** Der Aktionsbereich rendert genau einen Button je nach `resolvePairAction`. */
function PairRowAction({
  pair,
  action,
  onRetry,
}: {
  pair: FrameworkPair;
  action: PairAction;
  onRetry: (pair: FrameworkPair) => void;
}) {
  if (!action) return null;

  if (action.kind === "retry") {
    return (
      <Button variant={action.variant} size="sm" onClick={() => onRetry(pair)}>
        <RotateCw aria-hidden="true" />
        {action.label}
      </Button>
    );
  }

  return (
    <Button asChild variant={action.variant} size="sm">
      <Link to={action.to}>
        {action.label}
        <ArrowRight aria-hidden="true" />
      </Link>
    </Button>
  );
}

/** Ergebnis- und Statuszeile: je nach Lebenszyklus Fortschritt, Fehlerhinweis oder Kennzahlen. */
function PairRowBody({ pair, href }: { pair: FrameworkPair; href: string }) {
  if (pair.lifecycle === "not_started") {
    return (
      <p className="text-xs text-fg-muted">
        Für dieses Paar wurde noch kein Vergleich ausgeführt.
      </p>
    );
  }

  if (pair.lifecycle === "running" || pair.lifecycle === "paused") {
    return (
      <div className="max-w-64">
        {pair.totalPairs > 0 ? (
          <>
            <Progress
              value={pair.percent}
              tone={pair.lifecycle === "paused" ? "warning" : "info"}
              label={`Klassifikation ${pair.label}: ${pair.percent} Prozent`}
            />
            <p className="mt-1 text-[0.6875rem] tabular-nums text-fg-muted">
              {formatNumber(pair.classifiedPairs)} / {formatNumber(pair.totalPairs)} Konzeptpaare
            </p>
          </>
        ) : null}
        {pair.lifecycle === "paused" ? (
          <p className="mt-1 text-[0.6875rem] text-fg-muted">
            {PAIR_LIFECYCLE_PRESENTATION.paused.hint}
          </p>
        ) : null}
      </div>
    );
  }

  if (pair.lifecycle === "failed" || pair.lifecycle === "interrupted") {
    // Ein gescheiterter Lauf traegt die Ausnahme aus classification_service;
    // ein unterbrochener Lauf hat keine Ausnahme erlebt (nur einen
    // Prozess-Neustart) und bleibt beim allgemeinen Hinweistext.
    return (
      <div className="max-w-md space-y-0.5 text-xs text-fg-muted">
        <p>{PAIR_LIFECYCLE_PRESENTATION[pair.lifecycle].hint}</p>
        {pair.error ? <p className="font-mono text-[0.6875rem] text-danger">{pair.error}</p> : null}
      </div>
    );
  }

  // review_required | integration_required | complete: Kennzahlen, semantisch
  // getrennt in Ergebnis (Information) und offene Arbeit (moeglicherweise
  // mit Aktion).
  return (
    <div className="space-y-1 text-xs text-fg-muted">
      <p>
        <span className="tabular-nums font-medium text-fg">
          {formatNumber(pair.mappingsCount)}
        </span>{" "}
        {pluralize(pair.mappingsCount, "Mapping", "Mappings")}
        {" · "}
        {pair.pendingReviewCount > 0 ? (
          <Link
            to={`${href}/mappings?status=review`}
            className="font-medium text-accent tabular-nums hover:underline"
          >
            {formatNumber(pair.pendingReviewCount)}{" "}
            {pluralize(pair.pendingReviewCount, "Review", "Reviews")} offen
          </Link>
        ) : (
          <span>Keine Reviews offen</span>
        )}
      </p>

      {pair.unresolvedCount > 0 ? (
        <UnresolvedNote count={pair.unresolvedCount} />
      ) : null}

      {pair.disjointTotal > 0 ? (
        pair.disjointOpen > 0 ? (
          <p>
            <Link
              to={`${href}/unmapped?status=open`}
              className="font-medium text-accent tabular-nums hover:underline"
            >
              {formatNumber(pair.disjointOpen)}{" "}
              {pluralize(pair.disjointOpen, "Konzept", "Konzepte")} ohne Integrationsentscheidung
            </Link>
          </p>
        ) : (
          <p className="tabular-nums">
            {formatNumber(pair.disjointDecided)}{" "}
            {pluralize(pair.disjointDecided, "Konzept", "Konzepte")} integriert
          </p>
        )
      ) : null}
    </div>
  );
}

/**
 * UNRESOLVED-Faelle sind nutzerverstaendlich beschriftet und bewusst kein
 * Link: sie sind im Mapping-Review nicht entscheidbar (siehe
 * `countActionableReviews` in status.ts) und erscheinen nur im Pruefbericht.
 */
function UnresolvedNote({ count }: { count: number }): ReactNode {
  return (
    <Tooltip content="UNRESOLVED-Fälle erreichten keinen Mehrheitsentscheid und gehören nicht zur konjunkten Menge K. Sie sind in dieser Ansicht nicht entscheidbar, erscheinen aber vollständig im Prüfbericht.">
      <p className="w-fit cursor-help underline decoration-dotted">
        {formatNumber(count)} nicht auflösbare {pluralize(count, "Fall", "Fälle")} (UNRESOLVED) ·
        nur im Prüfbericht
      </p>
    </Tooltip>
  );
}
