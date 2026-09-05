import { cn } from "@/lib/utils";

/**
 * Fortschrittsbalken. `label` beschreibt den Wert fuer Screenreader, damit
 * der Fortschritt nicht nur visuell existiert.
 */
export function Progress({
  value,
  label,
  className,
  tone = "accent",
}: {
  /** 0–100. */
  value: number;
  label: string;
  className?: string;
  tone?: "accent" | "info" | "success" | "warning" | "danger";
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const barTone = {
    accent: "bg-accent",
    info: "bg-info",
    success: "bg-success",
    warning: "bg-warning",
    danger: "bg-danger",
  }[tone];

  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-muted", className)}
    >
      <div
        className={cn("h-full rounded-full transition-[width] duration-300", barTone)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
