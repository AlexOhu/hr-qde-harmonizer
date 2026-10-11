/**
 * Filterbare Auswahl der Ankerklasse fuer `attach_to_skeleton`.
 *
 * Oben stehen die RELATED-Kandidaten des Konzepts (die Naehe, auf die sich
 * der Systemvorschlag stuetzt), darunter der Hub des Projekts als
 * skos:broader-Baum mit Einrueckung. Die Textsuche filtert auf Label und URI;
 * Oberbegriffe eines Treffers bleiben als Kontext sichtbar. Ein Wert mit
 * Doppelpunkt (URI oder CURIE wie hrqde:DQR5) kann als Freitext uebernommen
 * werden, die Liste ist eine Eingabehilfe und kein geschlossenes Vokabular.
 */

import { useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { X } from "lucide-react";

import type { AnchorCandidate } from "@/api/disjoint";
import { Input } from "@/components/ui/field";
import { cn } from "@/lib/utils";
import { filterTree } from "./anchorTree";

const MAX_ROWS = 300;
const INDENT_PX = 14;

interface Row {
  key: string;
  candidate: AnchorCandidate | null; // null = Freitext-Zeile
  freeText?: string;
  /** Nur als Oberbegriff eines Treffers sichtbar, nicht selbst getroffen. */
  context: boolean;
  heading?: string;
}

export function AnchorClassCombobox({
  id,
  describedBy,
  value,
  onChange,
  candidates,
  isLoading,
}: {
  id: string;
  describedBy?: string;
  value: string;
  onChange: (value: string) => void;
  candidates: AnchorCandidate[];
  isLoading: boolean;
}) {
  const listId = useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);

  const labelByUri = useMemo(() => {
    const map = new Map<string, string>();
    for (const c of candidates) map.set(c.uri, c.label);
    return map;
  }, [candidates]);

  const { rows, hits, truncated } = useMemo(() => {
    const filtered = filterTree(candidates, query);
    const out: Row[] = [];
    const trimmed = query.trim();
    if (trimmed.includes(":") && !labelByUri.has(trimmed)) {
      out.push({ key: "free", candidate: null, freeText: trimmed, context: false });
    }
    let lastGroup: string | null = null;
    for (const r of filtered.rows.slice(0, MAX_ROWS)) {
      const group = r.candidate.group;
      out.push({
        key: `${r.index}`,
        candidate: r.candidate,
        context: r.context,
        heading:
          group !== lastGroup
            ? group === "related"
              ? "Kandidaten aus der Klassifikation (RELATED)"
              : `Hub ${r.candidate.kqr_id}`
            : undefined,
      });
      lastGroup = group;
    }
    return { rows: out, hits: filtered.hits, truncated: filtered.rows.length > MAX_ROWS };
  }, [candidates, query, labelByUri]);

  function choose(row: Row) {
    onChange(row.candidate ? row.candidate.uri : (row.freeText ?? ""));
    setQuery("");
    setOpen(false);
  }

  function scrollTo(index: number) {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-row="${index}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      const delta = event.key === "ArrowDown" ? 1 : -1;
      const next = Math.max(0, Math.min(rows.length - 1, active + delta));
      setActive(next);
      scrollTo(next);
    } else if (event.key === "Enter" && open && rows[active]) {
      event.preventDefault();
      choose(rows[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  const selectedLabel = value ? labelByUri.get(value) : undefined;

  return (
    <div className="space-y-1.5">
      {value ? (
        <div className="flex items-start justify-between gap-2 rounded-md border border-border-subtle bg-surface-muted px-2.5 py-1.5">
          <div className="min-w-0">
            <p className="text-xs font-medium text-fg">{selectedLabel ?? "Freitext"}</p>
            <p className="font-mono text-[0.6875rem] break-all text-fg-muted">{value}</p>
          </div>
          <button
            type="button"
            className="shrink-0 rounded p-0.5 text-fg-subtle hover:text-fg"
            aria-label="Ankerklasse entfernen"
            onClick={() => onChange("")}
          >
            <X className="size-3.5" aria-hidden="true" />
          </button>
        </div>
      ) : null}
      <div className="relative">
        <Input
          id={id}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-describedby={describedBy}
          aria-activedescendant={open && rows[active] ? `${listId}-${active}` : undefined}
          value={query}
          placeholder={
            isLoading ? "Knoten werden geladen …" : value ? "Andere Klasse suchen …" : "Label oder URI suchen …"
          }
          onChange={(event) => {
            setQuery(event.target.value);
            setActive(0);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          onKeyDown={onKeyDown}
        />
        {open && !isLoading ? (
          <ul
            ref={listRef}
            id={listId}
            role="listbox"
            className="absolute z-20 mt-1 max-h-80 w-full overflow-auto rounded-md border border-border-strong bg-surface py-1 shadow-lg"
          >
            {rows.length === 0 ? (
              <li className="px-2.5 py-1.5 text-xs text-fg-subtle">Keine Treffer.</li>
            ) : null}
            {rows.map((row, i) => (
              <li key={row.key} role="presentation">
                {row.heading ? (
                  <p className="sticky top-0 bg-surface px-2.5 pt-2 pb-1 text-[0.6875rem] font-semibold tracking-wide text-fg-subtle uppercase">
                    {row.heading}
                  </p>
                ) : null}
                <div
                  id={`${listId}-${i}`}
                  data-row={i}
                  role="option"
                  aria-selected={i === active}
                  className={cn(
                    "cursor-pointer px-2.5 py-1 text-xs",
                    i === active ? "bg-accent-soft text-fg" : "text-fg hover:bg-surface-muted",
                    row.context && "text-fg-subtle",
                    row.candidate?.uri === value && "font-semibold",
                  )}
                  style={{ paddingLeft: 10 + (row.candidate ? row.candidate.depth : 0) * INDENT_PX }}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => choose(row)}
                  title={row.candidate?.uri ?? row.freeText}
                >
                  {row.candidate ? (
                    row.candidate.label
                  ) : (
                    <span>
                      Als Freitext übernehmen: <span className="font-mono">{row.freeText}</span>
                    </span>
                  )}
                </div>
              </li>
            ))}
            {truncated ? (
              <li className="px-2.5 py-1.5 text-xs text-fg-subtle">
                {hits} Treffer, die ersten {MAX_ROWS} Zeilen werden angezeigt. Suche verfeinern.
              </li>
            ) : null}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
