/**
 * Nicht zugeordnete Konzepte als Master-Detail-Arbeitsflaeche.
 *
 * Wie beim Mapping-Review bedient dieselbe Flaeche den paarbezogenen und den
 * projektweiten Fall. Projektweit lassen sich alle offenen Entscheidungen
 * abarbeiten, ohne jedes Paar einzeln zu oeffnen.
 */

import { useEffect, useMemo } from "react";
import { Puzzle, Search } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import type { Concept, IntegrationDecision, IntegrationStrategy } from "@/api/types";
import { INTEGRATION_STRATEGIES } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Input, Select } from "@/components/ui/field";
import { MasterDetail, MasterListItem } from "@/components/common/MasterDetail";
import { EmptyState, ErrorPanel, SkeletonList } from "@/components/common/states";
import { indexDecisions, useIntegrationDecisions, useUnmappedConcepts } from "@/hooks/useIntegration";
import { ConceptDetail } from "./ConceptDetail";
import {
  INTEGRATION_STATUS_LABELS,
  STRATEGY_PRESENTATION,
  type IntegrationStatusFilter,
} from "./integrationPresentation";
import { formatNumber } from "@/lib/utils";

const STATUS_VALUES: IntegrationStatusFilter[] = ["all", "open", "decided"];

function parseStatus(value: string | null): IntegrationStatusFilter {
  return STATUS_VALUES.includes(value as IntegrationStatusFilter)
    ? (value as IntegrationStatusFilter)
    : "all";
}

export function IntegrationWorkspace({
  projectId,
  isReadOnly,
  pair,
  pairOptions,
}: {
  projectId: string;
  isReadOnly: boolean;
  pair?: { frameworkAId: string; frameworkBId: string };
  pairOptions?: { key: string; label: string; frameworkAId: string; frameworkBId: string }[];
}) {
  const [searchParams, setSearchParams] = useSearchParams();

  const status = parseStatus(searchParams.get("status"));
  const search = searchParams.get("q") ?? "";
  const selectedUri = searchParams.get("selected");
  const frameworkFilter = searchParams.get("framework") ?? "";
  const strategyFilter = searchParams.get("strategy") ?? "";
  const pairFilterKey = searchParams.get("pair") ?? "";

  const activePairOption = pairOptions?.find((option) => option.key === pairFilterKey);
  const effectivePair = pair ?? activePairOption;

  const conceptsQuery = useUnmappedConcepts(projectId, effectivePair);
  const decisionsQuery = useIntegrationDecisions(projectId);

  const decisionsByConcept = useMemo(
    () => indexDecisions(decisionsQuery.data),
    [decisionsQuery.data],
  );

  function updateParams(changes: Record<string, string | null>) {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        for (const [key, value] of Object.entries(changes)) {
          if (value === null || value === "") next.delete(key);
          else next.set(key, value);
        }
        return next;
      },
      { replace: true },
    );
  }

  const allConcepts = useMemo(() => conceptsQuery.data ?? [], [conceptsQuery.data]);

  const frameworkOptions = useMemo(() => {
    const ids = new Set(allConcepts.map((concept) => concept.kqr_id));
    return [...ids].sort();
  }, [allConcepts]);

  /** Freitextsuche und Feinfilter laufen clientseitig (API-Gap: kein Suchparameter). */
  const visibleConcepts = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return allConcepts.filter((concept) => {
      const decision = decisionsByConcept.get(concept.uri);

      if (status === "open" && decision) return false;
      if (status === "decided" && !decision) return false;
      if (frameworkFilter && concept.kqr_id !== frameworkFilter) return false;
      if (strategyFilter && decision?.strategy !== strategyFilter) return false;

      if (!needle) return true;
      return (
        concept.pref_label.toLowerCase().includes(needle) ||
        concept.uri.toLowerCase().includes(needle) ||
        (concept.definition ?? "").toLowerCase().includes(needle)
      );
    });
  }, [allConcepts, decisionsByConcept, status, frameworkFilter, strategyFilter, search]);

  const selectedConcept = visibleConcepts.find((concept) => concept.uri === selectedUri) ?? null;

  useEffect(() => {
    if (visibleConcepts.length === 0) {
      if (selectedUri) updateParams({ selected: null });
      return;
    }
    if (!selectedConcept) {
      updateParams({ selected: visibleConcepts[0].uri });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleConcepts, selectedConcept, selectedUri]);

  const openCount = allConcepts.filter((concept) => !decisionsByConcept.has(concept.uri)).length;

  const toolbar = (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-fg-muted">
          {conceptsQuery.isPending
            ? "Wird geladen …"
            : `${formatNumber(visibleConcepts.length)} von ${formatNumber(allConcepts.length)}`}
        </span>
        {openCount > 0 ? (
          <Badge tone="warning">{formatNumber(openCount)} offen</Badge>
        ) : allConcepts.length > 0 ? (
          <Badge tone="success">Alle entschieden</Badge>
        ) : null}
      </div>

      <div className="relative">
        <Search
          className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-fg-subtle"
          aria-hidden="true"
        />
        <Input
          type="search"
          value={search}
          onChange={(event) => updateParams({ q: event.target.value, selected: null })}
          placeholder="Konzept, URI oder Definition suchen"
          aria-label="Konzepte durchsuchen"
          className="pl-8"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <Select
          value={status}
          onChange={(event) => updateParams({ status: event.target.value, selected: null })}
          aria-label="Nach Status filtern"
          className="flex-1"
        >
          {STATUS_VALUES.map((value) => (
            <option key={value} value={value}>
              {INTEGRATION_STATUS_LABELS[value]}
            </option>
          ))}
        </Select>

        <Select
          value={frameworkFilter}
          onChange={(event) => updateParams({ framework: event.target.value, selected: null })}
          aria-label="Nach Framework filtern"
          className="flex-1"
        >
          <option value="">Alle Frameworks</option>
          {frameworkOptions.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-wrap gap-2">
        {pairOptions && pairOptions.length > 0 ? (
          <Select
            value={pairFilterKey}
            onChange={(event) => updateParams({ pair: event.target.value, selected: null })}
            aria-label="Nach Framework-Paar filtern"
            className="flex-1"
          >
            <option value="">Alle Paare</option>
            {pairOptions.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </Select>
        ) : null}

        <Select
          value={strategyFilter}
          onChange={(event) => updateParams({ strategy: event.target.value, selected: null })}
          aria-label="Nach Strategie filtern"
          className="flex-1"
        >
          <option value="">Alle Strategien</option>
          {INTEGRATION_STRATEGIES.map((option) => (
            <option key={option} value={option}>
              {STRATEGY_PRESENTATION[option].label}
            </option>
          ))}
        </Select>
      </div>
    </div>
  );

  const list = conceptsQuery.isPending ? (
    <SkeletonList rows={8} className="p-4" />
  ) : conceptsQuery.isError ? (
    <div className="p-4">
      <ErrorPanel error={conceptsQuery.error} onRetry={() => void conceptsQuery.refetch()} />
    </div>
  ) : visibleConcepts.length === 0 ? (
    <EmptyState
      className="m-4"
      icon={<Puzzle />}
      title={
        allConcepts.length === 0 ? "Keine nicht zugeordneten Konzepte" : "Kein Treffer im Filter"
      }
      description={
        allConcepts.length === 0
          ? "Alle Konzepte dieser Auswahl kommen in mindestens einem Mapping vor."
          : "Passen Sie Suche oder Filter an."
      }
    />
  ) : (
    <ul>
      {visibleConcepts.map((concept) => (
        <li key={concept.uri}>
          <ConceptListItem
            concept={concept}
            decision={decisionsByConcept.get(concept.uri)}
            selected={concept.uri === selectedUri}
            onSelect={() => updateParams({ selected: concept.uri })}
          />
        </li>
      ))}
    </ul>
  );

  return (
    <MasterDetail
      listLabel="Liste nicht zugeordneter Konzepte"
      detailTitle="Konzeptdetails"
      toolbar={toolbar}
      list={list}
      hasSelection={Boolean(selectedConcept)}
      onCloseDetail={() => updateParams({ selected: null })}
      detail={
        selectedConcept ? (
          <ConceptDetail
            concept={selectedConcept}
            decision={decisionsByConcept.get(selectedConcept.uri)}
            projectId={projectId}
            isReadOnly={isReadOnly}
            currentPairFrameworkIds={
              effectivePair
                ? [effectivePair.frameworkAId, effectivePair.frameworkBId]
                : undefined
            }
          />
        ) : (
          <EmptyState
            className="m-5"
            title="Kein Konzept ausgewählt"
            description="Wählen Sie links ein Konzept, um seine Integrationsstrategie festzulegen."
          />
        )
      }
    />
  );
}

function ConceptListItem({
  concept,
  decision,
  selected,
  onSelect,
}: {
  concept: Concept;
  decision: IntegrationDecision | undefined;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <MasterListItem selected={selected} onSelect={onSelect}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-medium text-fg">{concept.pref_label}</p>
          <p className="truncate font-mono text-[0.6875rem] text-fg-subtle">{concept.kqr_id}</p>
        </div>
        <div className="shrink-0">
          {decision ? (
            <Badge tone="success">
              {STRATEGY_PRESENTATION[decision.strategy as IntegrationStrategy].label}
            </Badge>
          ) : (
            <Badge tone="warning">Offen</Badge>
          )}
        </div>
      </div>
    </MasterListItem>
  );
}
