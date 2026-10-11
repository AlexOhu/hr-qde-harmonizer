/**
 * Filterlogik der Ankerklassen-Auswahl: Treffer der Textsuche plus ihre
 * Oberbegriffe im skos:broader-Baum (DFS-Reihenfolge des Backends).
 */

import type { AnchorCandidate } from "@/api/disjoint";

function matches(candidate: AnchorCandidate, terms: string[]): boolean {
  const hay = `${candidate.label} ${candidate.uri}`.toLowerCase();
  return terms.every((t) => hay.includes(t));
}

/** Treffer plus ihre Oberbegriffe (Stapel ueber die DFS-Reihenfolge). */
export function filterTree(
  candidates: AnchorCandidate[],
  query: string,
): { rows: { candidate: AnchorCandidate; context: boolean; index: number }[]; hits: number } {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) {
    return { rows: candidates.map((c, index) => ({ candidate: c, context: false, index })), hits: candidates.length };
  }
  const visible = new Map<number, boolean>(); // index -> context?
  const stack: number[] = [];
  let hits = 0;
  candidates.forEach((c, i) => {
    if (c.group === "related") {
      if (matches(c, terms)) {
        visible.set(i, false);
        hits += 1;
      }
      return;
    }
    stack.length = c.depth;
    if (matches(c, terms)) {
      hits += 1;
      visible.set(i, false);
      for (const ancestor of stack) if (!visible.has(ancestor)) visible.set(ancestor, true);
    }
    stack.push(i);
  });
  const rows = [...visible.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([index, context]) => ({ candidate: candidates[index], context, index }));
  return { rows, hits };
}
