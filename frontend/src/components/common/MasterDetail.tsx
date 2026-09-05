/**
 * Master-Detail-Arbeitsflaeche fuer grosse Entscheidungsmengen.
 *
 * Auf breiten Viewports stehen Liste und Detail nebeneinander, beide mit
 * eigenem Scrollbereich; das Detail bleibt beim Blaettern durch die Liste
 * stehen. Darunter fuellt die Liste die Breite und das Detail oeffnet als
 * Drawer — nie ein horizontal unbenutzbares Layout.
 */

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { useIsWideViewport } from "@/hooks/useMediaQuery";
import { cn } from "@/lib/utils";

export function MasterDetail({
  toolbar,
  list,
  footer,
  detail,
  detailTitle,
  hasSelection,
  onCloseDetail,
  listLabel,
}: {
  /** Suche und Filter oberhalb der Liste. */
  toolbar: ReactNode;
  list: ReactNode;
  /** Optionale Leiste unterhalb der Liste, z. B. Paginierung. */
  footer?: ReactNode;
  detail: ReactNode;
  /** Ueberschrift des Drawers auf schmalen Viewports. */
  detailTitle: string;
  hasSelection: boolean;
  onCloseDetail: () => void;
  listLabel: string;
}) {
  const isWide = useIsWideViewport();

  return (
    <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
      <section
        aria-label={listLabel}
        className="flex min-h-0 min-w-0 flex-col border-border-subtle lg:w-[26rem] lg:shrink-0 lg:border-r xl:w-[30rem]"
      >
        <div className="shrink-0 border-b border-border-subtle bg-surface px-4 py-3">{toolbar}</div>
        <div className="min-h-0 flex-1 overflow-y-auto">{list}</div>
        {footer ? (
          <div className="shrink-0 border-t border-border-subtle bg-surface px-4 py-2.5">
            {footer}
          </div>
        ) : null}
      </section>

      {isWide ? (
        <section
          aria-label={detailTitle}
          className="min-h-0 min-w-0 flex-1 overflow-y-auto bg-canvas"
        >
          {detail}
        </section>
      ) : (
        <DialogPrimitive.Root
          open={hasSelection}
          onOpenChange={(open: boolean) => {
            if (!open) onCloseDetail();
          }}
        >
          <DialogPrimitive.Portal>
            <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/25" />
            <DialogPrimitive.Content
              className={cn(
                "fixed inset-y-0 right-0 z-50 flex w-[min(32rem,100vw)] flex-col bg-canvas shadow-xl",
              )}
            >
              <div className="flex shrink-0 items-center justify-between gap-4 border-b border-border-subtle bg-surface px-4 py-3">
                <DialogPrimitive.Title className="text-sm font-semibold text-fg">
                  {detailTitle}
                </DialogPrimitive.Title>
                <DialogPrimitive.Description className="sr-only">
                  Details des ausgewählten Eintrags
                </DialogPrimitive.Description>
                <DialogPrimitive.Close asChild>
                  <Button variant="ghost" size="icon" aria-label="Detailansicht schließen">
                    <X aria-hidden="true" />
                  </Button>
                </DialogPrimitive.Close>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto">{detail}</div>
            </DialogPrimitive.Content>
          </DialogPrimitive.Portal>
        </DialogPrimitive.Root>
      )}
    </div>
  );
}

/**
 * Ein Eintrag der Master-Liste.
 *
 * `<button>` statt `<div onClick>`: Tastaturbedienung und Rollen kommen vom
 * Browser, `aria-current` benennt die Auswahl fuer Screenreader.
 */
export function MasterListItem({
  selected,
  onSelect,
  children,
  className,
}: {
  selected: boolean;
  onSelect: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected ? "true" : undefined}
      className={cn(
        "w-full border-b border-border-subtle px-4 py-2.5 text-left transition-colors",
        selected ? "bg-accent-soft" : "bg-surface hover:bg-surface-muted",
        className,
      )}
    >
      {children}
    </button>
  );
}

/** Rahmen der Detailspalte mit begrenzter Zeilenlaenge. */
export function DetailPanel({ children }: { children: ReactNode }) {
  return <div className="mx-auto max-w-3xl px-5 py-5">{children}</div>;
}

/** Beschriftetes Feld in der Detailansicht. */
export function DetailField({
  label,
  children,
  mono = false,
}: {
  label: string;
  children: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-[0.6875rem] font-medium tracking-wide text-fg-subtle uppercase">
        {label}
      </dt>
      <dd className={cn("mt-0.5 text-xs break-words text-fg", mono && "font-mono")}>{children}</dd>
    </div>
  );
}
