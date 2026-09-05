/**
 * Wiederverwendbare Lade-, Fehler- und Leerzustaende.
 *
 * Grundsatz: kein globaler Spinner, wenn nur ein Teilbereich laedt. Jeder
 * Bereich zeigt sein eigenes Skeleton, und ein Fehler bleibt dort sichtbar,
 * wo er entstanden ist — samt Wiederholen-Aktion.
 */

import { AlertTriangle, PlugZap, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

import { ApiError, API_BASE_URL } from "@/api/client";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-md", className)} aria-hidden="true" />;
}

/** Platzhalter fuer eine ladende Liste. */
export function SkeletonList({ rows = 4, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-2", className)} role="status" aria-label="Daten werden geladen">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-12 w-full" />
      ))}
      <span className="sr-only">Daten werden geladen …</span>
    </div>
  );
}

export function ErrorPanel({
  error,
  onRetry,
  title,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
  className?: string;
}) {
  const isConnection = error instanceof ApiError && error.isConnectionError;
  const message = error instanceof Error ? error.message : "Unbekannter Fehler.";

  return (
    <div
      role="alert"
      className={cn("rounded-lg border border-danger/30 bg-danger-soft p-4", className)}
    >
      <div className="flex items-start gap-2.5">
        {isConnection ? (
          <PlugZap className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden="true" />
        ) : (
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden="true" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-danger">
            {title ?? (isConnection ? "Backend nicht erreichbar" : "Anfrage fehlgeschlagen")}
          </p>
          <p className="mt-1 text-xs break-words text-fg-muted">{message}</p>
          {isConnection ? (
            <p className="mt-2 text-xs text-fg-muted">
              Erwartet unter <code className="font-mono">{API_BASE_URL}</code>. Backend starten mit{" "}
              <code className="font-mono">uvicorn app.api.main:app --reload</code>.
            </p>
          ) : null}
          {onRetry ? (
            <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
              <RefreshCw aria-hidden="true" />
              Erneut versuchen
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border-subtle px-6 py-10 text-center",
        className,
      )}
    >
      {icon ? <div className="text-fg-subtle [&_svg]:size-6">{icon}</div> : null}
      <p className="text-sm font-medium text-fg">{title}</p>
      {description ? (
        <p className="max-w-md text-xs text-fg-muted">{description}</p>
      ) : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}
