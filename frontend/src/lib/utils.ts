import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Klassennamen zusammenfuehren; spaetere Tailwind-Utilities gewinnen. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

const numberFormat = new Intl.NumberFormat("de-DE");

export function formatNumber(value: number): string {
  return numberFormat.format(value);
}

export function formatPercent(value: number, fractionDigits = 0): string {
  return `${value.toFixed(fractionDigits)} %`;
}

export function formatConfidence(value: number): string {
  return value.toFixed(2);
}

const dateTimeFormat = new Intl.DateTimeFormat("de-DE", {
  dateStyle: "medium",
  timeStyle: "short",
});

const dateFormat = new Intl.DateTimeFormat("de-DE", { dateStyle: "medium" });

/**
 * Das Backend liefert teils naive Zeitstempel (`datetime.utcnow()`, ohne
 * Zeitzonen-Suffix), teils aware (`datetime.now(timezone.utc).isoformat()`).
 * Ein naiver Wert wird hier als UTC interpretiert, damit die Anzeige nicht je
 * nach Herkunftsfeld um Stunden springt.
 */
function parseBackendDate(value: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasZone ? value : `${value}Z`);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = parseBackendDate(value);
  return Number.isNaN(date.getTime()) ? "—" : dateTimeFormat.format(date);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = parseBackendDate(value);
  return Number.isNaN(date.getTime()) ? "—" : dateFormat.format(date);
}

export function timestampValue(value: string | null | undefined): number {
  if (!value) return 0;
  const time = parseBackendDate(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

/** Letztes URI-Segment — kompakte Kennung, wenn die volle URI zu lang ist. */
export function shortUri(uri: string): string {
  const withoutFragment = uri.split("#").pop() ?? uri;
  return withoutFragment.split("/").filter(Boolean).pop() ?? uri;
}

/** Stabiler, reihenfolgeunabhaengiger Schluessel eines Framework-Paars. */
export function pairKey(frameworkAId: string, frameworkBId: string): string {
  return [frameworkAId, frameworkBId].sort().join("::");
}

export function pluralize(count: number, singular: string, plural: string): string {
  return count === 1 ? singular : plural;
}
