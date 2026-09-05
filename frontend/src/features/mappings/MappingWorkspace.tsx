/**
 * Mapping-Review als Master-Detail-Arbeitsflaeche.
 *
 * Dieselbe Flaeche bedient den paarbezogenen und den projektweiten Fall; der
 * Unterschied ist ausschliesslich die Grundmenge (`pair` gesetzt oder nicht).
 * Filter- und Auswahlzustand liegen in den Suchparametern, damit ein Link auf
 * eine bestimmte Filterlage und ein bestimmtes Mapping moeglich ist.
 */

import { useEffect, useMemo } from "react";
import { Search, Table2 } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import type { Mapping } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Input, Select } from "@/components/ui/field";
import { MasterDetail, MasterListItem } from "@/components/common/MasterDetail";
import { Pagination } from "@/components/common/Pagination";
import { EmptyState, ErrorPanel, SkeletonList } from "@/components/common/states";
import { useMappingConfig, useMappings } from "@/hooks/useMappings";
import { MappingDetail } from "./MappingDetail";
import {
  JUSTIFICATION_LABELS,
  MAPPING_STATUS_LABELS,
  isAwaitingReview,
  matchesStatusFilter,
  predicateLabel,
  type MappingStatusFilter,
} from "./mappingPresentation";
import { formatConfidence, formatNumber } from "@/lib/utils";

const STATUS_VALUES: MappingStatusFilter[] = ["all", "open", "review", "accepted", "manual"];
const PAGE_SIZE_OPTIONS = [20, 50, 100];
const DEFAULT_PAGE_SIZE = 20;

function parseStatus(value: string | null): MappingStatusFilter {
  return STATUS_VALUES.includes(value as MappingStatusFilter)
    ? (value as MappingStatusFilter)
    : "all";
}

function parsePageSize(value: string | null): number {
  const parsed = Number(value);
  return PAGE_SIZE_OPTIONS.includes(parsed) ? parsed : DEFAULT_PAGE_SIZE;
}

function parsePage(value: string | null): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

export function MappingWorkspace({
  projectId,
  isReadOnly,
  pair,
  /** Auswahlliste zum Eingrenzen auf ein Paar (nur projektweite Ansicht). */
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
  const selectedId = searchParams.get("selected");
  const pairFilterKey = searchParams.get("pair") ?? "";
  const pageSize = parsePageSize(searchParams.get("pageSize"));
  const requestedPage = parsePage(searchParams.get("page"));

  const activePairOption = pairOptions?.find((option) => option.key === pairFilterKey);
  const effectivePair = pair ?? activePairOption;

  const configQuery = useMappingConfig();
  const threshold = configQuery.data?.mapping_confidence_threshold ?? 0.67;

  const mappingsQuery = useMappings(projectId, {
    frameworkAId: effectivePair?.frameworkAId,
    frameworkBId: effectivePair?.frameworkBId,
  });

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

  const allMappings = useMemo(() => mappingsQuery.data ?? [], [mappingsQuery.data]);

  /**
   * Freitextsuche laeuft clientseitig: `GET /mappings/` kennt keinen
   * Suchparameter (API-Gap). Die Grundmenge eines Paares bleibt handhabbar,
   * weil der Server bereits paarbezogen filtert.
   */
  const visibleMappings = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return allMappings
      .filter((mapping) => matchesStatusFilter(mapping, status, threshold))
      .filter((mapping) => {
        if (!needle) return true;
        return (
          mapping.subject_label.toLowerCase().includes(needle) ||
          mapping.object_label.toLowerCase().includes(needle) ||
          mapping.subject_id.toLowerCase().includes(needle) ||
          mapping.object_id.toLowerCase().includes(needle)
        );
      })
      .sort((a, b) => {
        // Faelle mit Entscheidungsbedarf zuerst, danach aufsteigende Konfidenz
        // — die unsichersten Mappings stehen oben.
        const aOpen = matchesStatusFilter(a, "review", threshold) ? 0 : 1;
        const bOpen = matchesStatusFilter(b, "review", threshold) ? 0 : 1;
        if (aOpen !== bOpen) return aOpen - bOpen;
        return a.mapping_confidence - b.mapping_confidence;
      });
  }, [allMappings, search, status, threshold]);

  const totalPages = Math.max(1, Math.ceil(visibleMappings.length / pageSize));
  // Schrumpft die Ergebnismenge unter die angeforderte Seite (Filterwechsel,
  // kleinere Seitengroesse), faellt die Anzeige auf die letzte gueltige
  // Seite zurueck statt eine leere Liste zu zeigen.
  const page = Math.min(requestedPage, totalPages);
  const pagedMappings = useMemo(
    () => visibleMappings.slice((page - 1) * pageSize, page * pageSize),
    [visibleMappings, page, pageSize],
  );

  const selectedMapping =
    visibleMappings.find((mapping) => mapping.mapping_id === selectedId) ?? null;

  // Faellt die Auswahl durch einen Filter- oder Seitenwechsel weg, rueckt der
  // erste Eintrag der aktuellen Seite nach — die Detailspalte bleibt gefuellt.
  useEffect(() => {
    if (visibleMappings.length === 0) {
      if (selectedId) updateParams({ selected: null });
      return;
    }
    if (!selectedMapping) {
      updateParams({ selected: (pagedMappings[0] ?? visibleMappings[0]).mapping_id });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleMappings, pagedMappings, selectedMapping, selectedId]);

  const openCount = allMappings.filter((mapping) =>
    matchesStatusFilter(mapping, "review", threshold),
  ).length;
  // Getrennt ausgewiesen: ein Paar ohne Zuordnung ist etwas anderes als ein
  // Mapping mit zu niedriger Konfidenz, und nur Ersteres geht durch die
  // Konjunkt/Disjunkt-Weiche.
  const awaitingCount = allMappings.filter(isAwaitingReview).length;

  const toolbar = (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-fg-muted">
          {mappingsQuery.isPending
            ? "Wird geladen …"
            : `${formatNumber(visibleMappings.length)} von ${formatNumber(allMappings.length)}`}
        </span>
        <div className="flex shrink-0 items-center gap-1.5">
          {awaitingCount > 0 ? (
            <Badge tone="warning">{formatNumber(awaitingCount)} ohne Zuordnung</Badge>
          ) : null}
          {openCount > 0 ? (
            <Badge tone="warning">{formatNumber(openCount)} Review offen</Badge>
          ) : allMappings.length > 0 ? (
            <Badge tone="success">Review abgeschlossen</Badge>
          ) : null}
        </div>
      </div>

      <div className="relative">
        <Search
          className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-fg-subtle"
          aria-hidden="true"
        />
        <Input
          type="search"
          value={search}
          onChange={(event) => updateParams({ q: event.target.value, selected: null, page: null })}
          placeholder="Konzept oder URI suchen"
          aria-label="Mappings durchsuchen"
          className="pl-8"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <Select
          value={status}
          onChange={(event) =>
            updateParams({ status: event.target.value, selected: null, page: null })
          }
          aria-label="Nach Status filtern"
          className="flex-1"
        >
          {STATUS_VALUES.map((value) => (
            <option key={value} value={value}>
              {MAPPING_STATUS_LABELS[value]}
            </option>
          ))}
        </Select>

        {pairOptions && pairOptions.length > 0 ? (
          <Select
            value={pairFilterKey}
            onChange={(event) =>
              updateParams({ pair: event.target.value, selected: null, page: null })
            }
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
      </div>
    </div>
  );

  const list = mappingsQuery.isPending ? (
    <SkeletonList rows={8} className="p-4" />
  ) : mappingsQuery.isError ? (
    <div className="p-4">
      <ErrorPanel error={mappingsQuery.error} onRetry={() => void mappingsQuery.refetch()} />
    </div>
  ) : visibleMappings.length === 0 ? (
    <EmptyState
      className="m-4"
      icon={<Table2 />}
      title={allMappings.length === 0 ? "Keine Mappings vorhanden" : "Kein Treffer im Filter"}
      description={
        allMappings.length === 0
          ? "Für diese Auswahl wurde noch kein Vergleich abgeschlossen."
          : "Passen Sie Suche oder Statusfilter an."
      }
    />
  ) : (
    <ul>
      {pagedMappings.map((mapping) => (
        <li key={mapping.mapping_id}>
          <MappingListItem
            mapping={mapping}
            threshold={threshold}
            selected={mapping.mapping_id === selectedId}
            onSelect={() => updateParams({ selected: mapping.mapping_id })}
          />
        </li>
      ))}
    </ul>
  );

  const footer =
    !mappingsQuery.isPending && !mappingsQuery.isError && visibleMappings.length > 0 ? (
      <Pagination
        page={page}
        totalPages={totalPages}
        pageSize={pageSize}
        pageSizeOptions={PAGE_SIZE_OPTIONS}
        totalCount={visibleMappings.length}
        onPageChange={(nextPage) => updateParams({ page: String(nextPage), selected: null })}
        onPageSizeChange={(nextPageSize) =>
          updateParams({ pageSize: String(nextPageSize), page: null, selected: null })
        }
      />
    ) : null;

  return (
    <MasterDetail
      listLabel="Mapping-Liste"
      detailTitle="Mapping-Details"
      toolbar={toolbar}
      list={list}
      footer={footer}
      hasSelection={Boolean(selectedMapping)}
      onCloseDetail={() => updateParams({ selected: null })}
      detail={
        selectedMapping ? (
          <MappingDetail
            mapping={selectedMapping}
            projectId={projectId}
            threshold={threshold}
            isReadOnly={isReadOnly}
          />
        ) : (
          <EmptyState
            className="m-5"
            title="Kein Mapping ausgewählt"
            description="Wählen Sie links einen Eintrag, um Details zu sehen und zu entscheiden."
          />
        )
      }
    />
  );
}

function MappingListItem({
  mapping,
  threshold,
  selected,
  onSelect,
}: {
  mapping: Mapping;
  threshold: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const awaitsReview = isAwaitingReview(mapping);
  const isManual = mapping.mapping_source === "manual";
  const needsReview = !awaitsReview && !isManual && mapping.mapping_confidence < threshold;

  return (
    <MasterListItem selected={selected} onSelect={onSelect}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-medium text-fg">{mapping.subject_label}</p>
          <p className="truncate text-xs text-fg-muted">↔ {mapping.object_label}</p>
          {awaitsReview ? (
            <p className="mt-0.5 truncate text-[0.6875rem] text-warning">
              {predicateLabel(mapping.predicate_id)} · wartet auf manuelle Entscheidung
            </p>
          ) : (
            <p className="mt-0.5 truncate text-[0.6875rem] text-fg-subtle">
              {JUSTIFICATION_LABELS[mapping.mapping_justification] ??
                mapping.mapping_justification}
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <span className="text-xs font-medium tabular-nums text-fg">
            {formatConfidence(mapping.mapping_confidence)}
          </span>
          {awaitsReview ? (
            <Badge tone="warning">Offen</Badge>
          ) : isManual ? (
            <Badge tone="accent">Manuell</Badge>
          ) : needsReview ? (
            <Badge tone="warning">Review</Badge>
          ) : (
            <Badge tone="success">Akzeptiert</Badge>
          )}
        </div>
      </div>
    </MasterListItem>
  );
}
