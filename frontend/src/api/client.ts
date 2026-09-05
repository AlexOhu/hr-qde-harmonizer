/**
 * Gemeinsamer HTTP-Client fuer alle Backend-Aufrufe.
 *
 * Zentral behandelt: Verbindungsfehler, HTTP-Fehler samt FastAPI-`detail`,
 * Timeouts und Datei-Downloads. Kein Modul ausserhalb von `src/api/` ruft
 * `fetch` direkt auf — Komponenten sprechen ausschliesslich ueber die Hooks
 * in `src/api/*.ts` mit dem Backend.
 */

import type { DownloadedFile } from "./types";

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ??
  "http://localhost:8000";

const DEFAULT_TIMEOUT_MS = 30_000;

/** Laufende Klassifikationen koennen einzelne Requests spuerbar verlangsamen. */
const LONG_TIMEOUT_MS = 180_000;

/**
 * Ein fehlgeschlagener Backend-Aufruf. `status === 0` bedeutet, dass die
 * Anfrage das Backend nie erreicht hat (Netzwerkfehler oder Timeout) — die
 * UI unterscheidet diesen Fall, weil dann nicht das Projekt kaputt ist,
 * sondern der Server nicht laeuft.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string | null;
  readonly url: string;

  constructor(message: string, options: { status: number; detail?: string | null; url: string }) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.detail = options.detail ?? null;
    this.url = options.url;
  }

  /** Backend nicht erreichbar (nicht: Backend antwortet mit Fehler). */
  get isConnectionError(): boolean {
    return this.status === 0;
  }

  /** Zustandskonflikt, z. B. Schreibversuch auf einem Snapshot. */
  get isConflict(): boolean {
    return this.status === 409;
  }
}

export type QueryParams = Record<
  string,
  string | number | boolean | null | undefined
>;

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  params?: QueryParams;
  json?: unknown;
  body?: BodyInit;
  timeoutMs?: number;
  signal?: AbortSignal;
}

function buildUrl(path: string, params?: QueryParams): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === null || value === undefined) continue;
    url.searchParams.set(key, String(value));
  }
  return url.toString();
}

/** FastAPI liefert Fehler als `{"detail": ...}`; `detail` kann bei
 *  Validierungsfehlern (422) auch eine Liste von Objekten sein. */
async function extractDetail(response: Response): Promise<string | null> {
  try {
    const data: unknown = await response.clone().json();
    if (data && typeof data === "object" && "detail" in data) {
      const { detail } = data as { detail: unknown };
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        return detail
          .map((item) =>
            item && typeof item === "object" && "msg" in item
              ? String((item as { msg: unknown }).msg)
              : JSON.stringify(item),
          )
          .join("; ");
      }
      return JSON.stringify(detail);
    }
    return null;
  } catch {
    return null;
  }
}

async function rawRequest(path: string, options: RequestOptions = {}): Promise<Response> {
  const { method = "GET", params, json, body, timeoutMs = DEFAULT_TIMEOUT_MS, signal } = options;
  const url = buildUrl(path, params);

  const timeoutController = new AbortController();
  const timer = setTimeout(() => timeoutController.abort(), timeoutMs);

  // Der Abbruch kann aus zwei Quellen kommen: dem Timeout oder dem von
  // TanStack Query uebergebenen Query-Signal.
  const abortSignal = signal
    ? AbortSignal.any([signal, timeoutController.signal])
    : timeoutController.signal;

  const headers: Record<string, string> = {};
  if (json !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: json !== undefined ? JSON.stringify(json) : body,
      signal: abortSignal,
    });
  } catch (error) {
    const aborted = timeoutController.signal.aborted;
    throw new ApiError(
      aborted
        ? `Zeitueberschreitung nach ${Math.round(timeoutMs / 1000)}s: ${path}`
        : `Backend unter ${API_BASE_URL} nicht erreichbar.`,
      { status: 0, detail: error instanceof Error ? error.message : null, url },
    );
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    const detail = await extractDetail(response);
    throw new ApiError(detail ?? `${response.status} ${response.statusText}`, {
      status: response.status,
      detail,
      url,
    });
  }

  return response;
}

/** JSON-Request. Bei `204 No Content` wird `undefined` zurueckgegeben. */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await rawRequest(path, options);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * Datei-Download. Der Dateiname stammt aus `Content-Disposition` (das
 * Backend exponiert diesen Header per CORS, siehe `app/api/main.py`); ohne
 * Header greift `fallbackName`.
 */
export async function download(
  path: string,
  fallbackName: string,
  options: RequestOptions = {},
): Promise<DownloadedFile> {
  const response = await rawRequest(path, { timeoutMs: LONG_TIMEOUT_MS, ...options });
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
  return {
    blob: await response.blob(),
    filename: match ? decodeURIComponent(match[1]) : fallbackName,
  };
}

/**
 * Uebergibt eine heruntergeladene Datei an den Browser. Bewusst hier und
 * nicht in einer Komponente, damit die Object-URL zuverlaessig freigegeben
 * wird.
 */
export function saveFile({ blob, filename }: DownloadedFile): void {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export { LONG_TIMEOUT_MS };
