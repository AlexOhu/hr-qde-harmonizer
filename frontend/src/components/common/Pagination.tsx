/**
 * Seitenleiste fuer clientseitig paginierte Listen.
 *
 * Rein praesentational: die aufrufende Stelle haelt Seite und Seitengroesse
 * im Zustand (i. d. R. in den Suchparametern, damit ein Link reproduzierbar
 * bleibt) und uebergibt bereits berechnete Werte.
 */

import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/field";
import { formatNumber } from "@/lib/utils";

export function Pagination({
  page,
  totalPages,
  pageSize,
  pageSizeOptions,
  totalCount,
  onPageChange,
  onPageSizeChange,
}: {
  /** 1-basiert. */
  page: number;
  totalPages: number;
  pageSize: number;
  pageSizeOptions: number[];
  totalCount: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <label className="flex items-center gap-1.5 text-xs text-fg-muted">
        <span className="hidden sm:inline">Pro Seite</span>
        <Select
          value={String(pageSize)}
          onChange={(event) => onPageSizeChange(Number(event.target.value))}
          aria-label="Einträge pro Seite"
          className="h-7 w-auto py-0 pr-7 text-xs"
        >
          {pageSizeOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </Select>
      </label>

      <div className="flex items-center gap-2">
        <span className="text-xs tabular-nums text-fg-muted">
          {totalCount === 0
            ? "Seite 0 von 0"
            : `Seite ${formatNumber(page)} von ${formatNumber(totalPages)}`}
        </span>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Vorherige Seite"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            <ChevronLeft aria-hidden="true" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Nächste Seite"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
          >
            <ChevronRight aria-hidden="true" />
          </Button>
        </div>
      </div>
    </div>
  );
}
