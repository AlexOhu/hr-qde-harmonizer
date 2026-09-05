/**
 * Testhilfen.
 *
 * Die Tests sprechen die Anwendung ueber ein gefaelschtes `fetch` an, nicht
 * ueber gemockte Hooks: so laufen API-Client, Query-Verdrahtung, Routing und
 * Komponenten gemeinsam durch — genau die Schichten, die zusammenpassen
 * muessen.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactElement } from "react";
import { vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { TooltipProvider } from "@/components/ui/tooltip";
import type {
  ClassificationJob,
  Concept,
  Framework,
  Mapping,
  PairStatus,
  PipelineStatus,
  Project,
} from "@/api/types";

export function renderWithProviders(
  ui: ReactElement,
  { route = "/" }: { route?: string } = {},
): RenderResult {
  const queryClient = new QueryClient({
    defaultOptions: {
      // Kein Retry und keine Frischezeit: Tests sollen deterministisch und
      // ohne Wartezeit auf Fehler reagieren.
      queries: { retry: false, staleTime: 0, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  return render(
    <MemoryRouter initialEntries={[route]}>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <ToastProvider>{ui}</ToastProvider>
        </TooltipProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

/** Eine Route-Definition des gefaelschten Backends. */
export interface FakeRoute {
  method?: string;
  /** Wird gegen Pfad + Query getestet. */
  match: (url: URL, method: string) => boolean;
  respond: (request: { url: URL; method: string; body: unknown }) => unknown;
  status?: number;
}

export interface FakeBackend {
  /** Alle abgesetzten Requests, in Reihenfolge. */
  calls: { method: string; url: URL; body: unknown }[];
  restore: () => void;
}

/**
 * Ersetzt `globalThis.fetch` durch eine Route-Tabelle. Nicht abgedeckte
 * Pfade schlagen mit 404 fehl, statt still `undefined` zu liefern — sonst
 * bleiben fehlende Stubs unbemerkt.
 */
export function installFakeBackend(routes: FakeRoute[]): FakeBackend {
  const calls: FakeBackend["calls"] = [];

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const rawUrl = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(rawUrl);
    const method = (init?.method ?? "GET").toUpperCase();

    let body: unknown = undefined;
    if (typeof init?.body === "string") {
      try {
        body = JSON.parse(init.body);
      } catch {
        body = init.body;
      }
    } else if (init?.body instanceof FormData) {
      body = Object.fromEntries(init.body.entries());
    }

    calls.push({ method, url, body });

    const route = routes.find(
      (candidate) =>
        (candidate.method ?? "GET").toUpperCase() === method && candidate.match(url, method),
    );

    if (!route) {
      return new Response(JSON.stringify({ detail: `Keine Testroute für ${method} ${url.pathname}` }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }

    const payload = route.respond({ url, method, body });
    const status = route.status ?? 200;
    if (status === 204) return new Response(null, { status });

    return new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });

  vi.stubGlobal("fetch", fetchMock);

  return { calls, restore: () => vi.unstubAllGlobals() };
}

/** Kurzform fuer eine Route, die auf einen exakten Pfad passt. */
export function route(
  method: string,
  pathname: string,
  respond: FakeRoute["respond"],
  status?: number,
): FakeRoute {
  return {
    method,
    match: (url) => url.pathname === pathname,
    respond,
    status,
  };
}

/** Route, die auf ein Pfad-Praefix passt (z. B. URI-Pfadparameter). */
export function routeStartsWith(
  method: string,
  prefix: string,
  respond: FakeRoute["respond"],
  status?: number,
): FakeRoute {
  return {
    method,
    match: (url) => url.pathname.startsWith(prefix),
    respond,
    status,
  };
}

// ── Fabriken fuer Testdaten ──────────────────────────────────────────────

export function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    project_id: "proj_1",
    name: "IT-Harmonisierung 2026",
    description: "Testprojekt",
    kqr_ids: ["esco", "ecf"],
    hub_kqr_id: "esco",
    created_at: "2026-08-01T10:00:00",
    updated_at: "2026-08-20T10:00:00",
    status: "active",
    parent_project_id: null,
    version_label: null,
    ...overrides,
  };
}

export function makeFramework(overrides: Partial<Framework> = {}): Framework {
  return {
    id: "esco",
    name: "ESCO",
    namespace_uri: "http://example.org/esco/",
    source_format: "turtle",
    status: "bereit",
    concept_count: 956,
    is_hub: true,
    ...overrides,
  };
}

export function makePairStatus(overrides: Partial<PairStatus> = {}): PairStatus {
  return {
    kqr_a_id: "ecf",
    kqr_a_name: "e-CF",
    kqr_b_id: "esco",
    kqr_b_name: "ESCO",
    job_status: "completed",
    job_id: "job_1",
    error: null,
    total_pairs: 900,
    classified_pairs: 900,
    mappings_count: 732,
    pending_review_count: 0,
    unresolved_count: 0,
    disjoint_total: 10,
    disjoint_decided: 10,
    disjoint_open: 0,
    ...overrides,
  };
}

export function makePipelineStatus(overrides: Partial<PipelineStatus> = {}): PipelineStatus {
  return {
    project: makeProject(),
    kqr_pairs: [makePairStatus()],
    disjoint_total: 10,
    disjoint_decided: 10,
    disjoint_open: 0,
    clustering_done: true,
    export_ready: true,
    ...overrides,
  };
}

export function makeJob(overrides: Partial<ClassificationJob> = {}): ClassificationJob {
  return {
    job_id: "job_1",
    kqr_a_id: "ecf",
    kqr_b_id: "esco",
    status: "completed",
    done_pairs: 900,
    total_pairs: 900,
    error: null,
    percent: 100,
    started_at: "2026-08-20T09:00:00+00:00",
    finished_at: "2026-08-20T09:45:00+00:00",
    ...overrides,
  };
}

export function makeMapping(overrides: Partial<Mapping> = {}): Mapping {
  return {
    mapping_id: "map_1",
    subject_id: "http://example.org/ecf/a1",
    subject_label: "Cloud computing",
    subject_kqr_id: "ecf",
    object_id: "http://example.org/esco/s1",
    object_label: "Data architecture",
    object_kqr_id: "esco",
    predicate_id: "skos:relatedMatch",
    mapping_confidence: 0.54,
    mapping_tool: "HR-QDE-Harmonizer-v0.1",
    mapping_justification: "semapv:LLMBasedMatching",
    mapping_source: "algorithmic",
    author: null,
    created_at: "2026-08-20T09:30:00",
    justification: null,
    review_status: "conjunct",
    context_loss_note: null,
    ...overrides,
  };
}

/**
 * Ein noch nicht entschiedenes offenes Paar. Seit v0.2 liefert
 * `GET /mappings/` solche Eintraege mit, statt sie auszublenden. Ohne
 * LLM-Mehrheitsentscheid ist `predicate_id` null; ein offenes RELATED trägt
 * `skos:relatedMatch`.
 */
export function makeOpenMapping(overrides: Partial<Mapping> = {}): Mapping {
  return makeMapping({
    mapping_id: "map_open",
    predicate_id: null,
    review_status: "open",
    mapping_confidence: 0.67,
    ...overrides,
  });
}

export function makeConcept(overrides: Partial<Concept> = {}): Concept {
  return {
    uri: "http://example.org/ecf/b2",
    kqr_id: "ecf",
    pref_label: "IT-Governance",
    definition: "Steuerung der IT im Unternehmen.",
    broader: [],
    narrower: [],
    ...overrides,
  };
}
