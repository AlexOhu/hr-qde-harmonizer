/**
 * Formular-Primitiven.
 *
 * `Field` verdrahtet Label, Control und Hilfetext ueber eine generierte ID,
 * damit jedes Control eine programmatisch verknuepfte Beschriftung hat und
 * Fehlermeldungen per `aria-describedby` vorgelesen werden.
 */

import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const controlClasses =
  "w-full rounded-md border border-border-strong bg-surface px-2.5 py-1.5 text-sm text-fg placeholder:text-fg-subtle disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-fg-subtle";

export function Label({
  children,
  htmlFor,
  required,
  className,
}: {
  children: ReactNode;
  htmlFor?: string;
  required?: boolean;
  className?: string;
}) {
  return (
    <label htmlFor={htmlFor} className={cn("block text-xs font-medium text-fg", className)}>
      {children}
      {required ? (
        <span className="ml-1 text-danger" aria-hidden="true">
          *
        </span>
      ) : null}
      {required ? <span className="sr-only"> (Pflichtfeld)</span> : null}
    </label>
  );
}

export interface FieldProps {
  label: ReactNode;
  /** Erhaelt die generierte ID und die `aria-describedby`-Verknuepfung. */
  children: (props: { id: string; "aria-describedby": string | undefined }) => ReactNode;
  hint?: ReactNode;
  error?: string | null;
  required?: boolean;
  className?: string;
}

export function Field({ label, children, hint, error, required, className }: FieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={id} required={required}>
        {label}
      </Label>
      {children({ id, "aria-describedby": describedBy })}
      {hint ? (
        <p id={hintId} className="text-xs text-fg-subtle">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} role="alert" className="text-xs font-medium text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(controlClasses, "h-8", className)} {...props} />;
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(controlClasses, "min-h-[72px] resize-y", className)} {...props} />;
}

/**
 * Natives `<select>` statt einer Custom-Listbox: Tastatur- und
 * Screenreader-Verhalten kommt vom Browser, und die Auswahllisten hier sind
 * kurz und brauchen keine Suche.
 */
export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(controlClasses, "h-8 py-0 pr-8", className)} {...props}>
      {children}
    </select>
  );
}

export function Checkbox({
  label,
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode }) {
  const id = useId();
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <input
        id={id}
        type="checkbox"
        className="size-3.5 rounded border-border-strong accent-accent"
        {...props}
      />
      <label htmlFor={id} className="text-xs text-fg select-none">
        {label}
      </label>
    </div>
  );
}
