import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

export const TooltipProvider = TooltipPrimitive.Provider;

/**
 * Tooltip fuer ergaenzende Erlaeuterungen (z. B. dass "nicht zugeordnete
 * Konzepte" der disjunkten Menge D entsprechen). Nie fuer Information, die
 * zum Verstaendnis noetig ist — Tooltips sind auf Touchgeraeten schwer
 * erreichbar.
 */
export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          sideOffset={6}
          collisionPadding={8}
          className="z-50 max-w-72 rounded-md border border-border-subtle bg-surface px-2.5 py-1.5 text-xs text-fg-muted shadow-md"
        >
          {content}
          <TooltipPrimitive.Arrow className="fill-surface" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
