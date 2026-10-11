/**
 * Zentrale Query-Key-Fabrik.
 *
 * Alle Keys sind hierarchisch aufgebaut, damit eine Mutation gezielt
 * invalidieren kann: `queryKeys.project.all(projectId)` trifft jeden Key,
 * der mit `["project", projectId]` beginnt, also auch Pipeline-Status,
 * Mappings und Integrationsentscheidungen dieses Projekts.
 */

import type { MappingFilters } from "./mappings";

export const queryKeys = {
  health: () => ["health"] as const,

  frameworks: {
    list: () => ["frameworks"] as const,
    detail: (frameworkId: string) => ["frameworks", frameworkId] as const,
  },

  projects: {
    list: () => ["projects"] as const,
  },

  project: {
    /** Praefix aller projektbezogenen Queries — Basis fuer Invalidierung. */
    all: (projectId: string) => ["project", projectId] as const,
    detail: (projectId: string) => ["project", projectId, "detail"] as const,
    pipelineStatus: (projectId: string) => ["project", projectId, "pipeline-status"] as const,
    jobs: (projectId: string) => ["project", projectId, "classification-jobs"] as const,
    pairResetEvents: (projectId: string) => ["project", projectId, "pair-reset-events"] as const,
    mappings: (projectId: string, filters: MappingFilters) =>
      ["project", projectId, "mappings", filters] as const,
    disjointConcepts: (projectId: string, pair?: { a: string; b: string }) =>
      ["project", projectId, "disjoint-concepts", pair ?? null] as const,
    disjointDecisions: (projectId: string) => ["project", projectId, "disjoint-decisions"] as const,
    disjointSummary: (projectId: string, pair?: { a: string; b: string }) =>
      ["project", projectId, "disjoint-summary", pair ?? null] as const,
    strategySuggestion: (projectId: string, conceptId: string) =>
      ["project", projectId, "strategy-suggestion", conceptId] as const,
    anchorCandidates: (projectId: string, conceptId: string) =>
      ["project", projectId, "anchor-candidates", conceptId] as const,
    exportSummary: (projectId: string) => ["project", projectId, "export-summary"] as const,
    clusters: (projectId: string) => ["project", projectId, "clusters"] as const,
    sssomPreview: (projectId: string, limit: number) =>
      ["project", projectId, "sssom-preview", limit] as const,
  },

  mappingConfig: () => ["mapping-config"] as const,
  preconditions: () => ["preconditions"] as const,
} as const;
