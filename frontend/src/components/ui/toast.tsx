/**
 * Toasts fuer erfolgreiche Mutationen und kurze Fehlermeldungen.
 *
 * Fachlich relevante Fehler (z. B. blockierter Export) gehoeren NICHT hierher
 * — die bleiben als Panel auf der Seite sichtbar. Toasts sind fluechtig.
 */

import * as ToastPrimitive from "@radix-ui/react-toast";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";

type ToastTone = "success" | "error" | "info";

interface ToastItem {
  id: number;
  title: string;
  description?: string;
  tone: ToastTone;
}

interface ToastContextValue {
  toast: (input: { title: string; description?: string; tone?: ToastTone }) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextToastId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: number) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const toast = useCallback<ToastContextValue["toast"]>(({ title, description, tone = "success" }) => {
    setItems((current) => [...current, { id: nextToastId++, title, description, tone }]);
  }, []);

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      <ToastPrimitive.Provider swipeDirection="right" duration={5000}>
        {children}
        {items.map((item) => (
          <ToastItemView key={item.id} item={item} onDismiss={() => dismiss(item.id)} />
        ))}
        <ToastPrimitive.Viewport className="fixed bottom-0 right-0 z-100 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2 p-4 outline-none" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}

const TONE_ICONS: Record<ToastTone, ReactNode> = {
  success: <CheckCircle2 className="size-4 text-success" aria-hidden="true" />,
  error: <AlertTriangle className="size-4 text-danger" aria-hidden="true" />,
  info: <Info className="size-4 text-info" aria-hidden="true" />,
};

function ToastItemView({ item, onDismiss }: { item: ToastItem; onDismiss: () => void }) {
  return (
    <ToastPrimitive.Root
      onOpenChange={(open: boolean) => {
        if (!open) onDismiss();
      }}
      className={cn(
        "flex items-start gap-2.5 rounded-lg border bg-surface p-3 shadow-md",
        item.tone === "error" ? "border-danger/30" : "border-border-subtle",
      )}
    >
      {TONE_ICONS[item.tone]}
      <div className="min-w-0 flex-1">
        <ToastPrimitive.Title className="text-xs font-semibold text-fg">
          {item.title}
        </ToastPrimitive.Title>
        {item.description ? (
          <ToastPrimitive.Description className="mt-0.5 text-xs break-words text-fg-muted">
            {item.description}
          </ToastPrimitive.Description>
        ) : null}
      </div>
      <ToastPrimitive.Close
        aria-label="Meldung schliessen"
        className="rounded text-fg-subtle hover:text-fg"
      >
        <X className="size-3.5" aria-hidden="true" />
      </ToastPrimitive.Close>
    </ToastPrimitive.Root>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast muss innerhalb von <ToastProvider> verwendet werden.");
  return context;
}
