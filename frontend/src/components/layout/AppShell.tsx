/**
 * Anwendungsrahmen: feste Seitenleiste links, scrollender Inhalt rechts.
 *
 * Nur der Inhaltsbereich scrollt. Master-Detail-Arbeitsflaechen koennen
 * dadurch die volle Hoehe nutzen und ihre Listen in eigenen Scrollbereichen
 * halten, statt die ganze Seite mitzuziehen.
 */

import type { ReactNode } from "react";

import { Sidebar, type SidebarProps } from "./Sidebar";
import { BackendStatus } from "./BackendStatus";

export function AppShell({ children, ...sidebarProps }: SidebarProps & { children: ReactNode }) {
  return (
    <div className="flex h-full">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-100 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:text-xs focus:font-medium"
      >
        Zum Inhalt springen
      </a>

      <Sidebar {...sidebarProps} />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-11 shrink-0 items-center justify-end gap-3 border-b border-border-subtle bg-surface px-4">
          <BackendStatus />
        </header>
        <main id="main-content" className="min-h-0 flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}

/**
 * Kopfbereich einer Seite. `actions` steht rechts neben dem Titel, damit die
 * primaere Aktion dort sitzt, wo ihr Gegenstand benannt wird.
 */
export function PageHeader({
  title,
  description,
  actions,
  meta,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border-subtle bg-surface px-6 py-4">
      <div className="min-w-0">
        <h1 className="text-lg font-semibold text-fg">{title}</h1>
        {meta ? <div className="mt-1.5 flex flex-wrap items-center gap-2">{meta}</div> : null}
        {description ? (
          <p className="mt-1.5 max-w-2xl text-xs text-fg-muted">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function PageBody({ children }: { children: ReactNode }) {
  return <div className="px-6 py-5">{children}</div>;
}
