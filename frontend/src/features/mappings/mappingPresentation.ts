/**
 * Anzeigebegriffe rund um Mappings.
 *
 * Das Backend spricht genau ein Relationsvokabular: `MappingPredicate`
 * (SKOS-Mapping-Prädikate als CURIE), persistiert in `Mapping.predicate_id`.
 * Ein offenes Paar ohne LLM-Mehrheitsentscheid trägt `predicate_id = null`.
 * Die Oberfläche übersetzt jeden Fall konsequent ins Deutsche; ob ein Eintrag
 * noch auf eine Entscheidung wartet, sagt `review_status` (bzw.
 * `isAwaitingReview`), nicht die Wortwahl.
 */

import type { Mapping, MappingJustification, MappingPredicate } from "@/api/types";

/** Deutsche Beschriftung je SKOS-Prädikat. Richtung der Subsumtion ausgesprochen. */
export const PREDICATE_LABELS: Record<MappingPredicate, string> = {
  "skos:exactMatch": "Äquivalent",
  "skos:closeMatch": "Nahezu äquivalent",
  "skos:broadMatch": "Objekt umfasst Subjekt",
  "skos:narrowMatch": "Subjekt umfasst Objekt",
  "skos:relatedMatch": "Verwandt",
};

export const PREDICATE_DESCRIPTIONS: Record<MappingPredicate, string> = {
  "skos:exactMatch": "Beide Konzepte bezeichnen denselben Sachverhalt.",
  "skos:closeMatch": "Weitgehend deckungsgleich, aber nicht in jedem Kontext austauschbar.",
  "skos:broadMatch": "Das Objekt ist der weitere Begriff.",
  "skos:narrowMatch": "Das Subjekt ist der weitere Begriff.",
  "skos:relatedMatch": "Semantisch nah, aber weder gleich noch über-/untergeordnet.",
};

/** Ein offenes Paar, dessen drei LLM-Läufe zu keinem Mehrheitsentscheid kamen. */
export const NO_CONSENSUS_LABEL = "Kein Konsens";
export const NO_CONSENSUS_DESCRIPTION =
  "Die drei LLM-Läufe kamen zu keinem Mehrheitsentscheid. Das Paar wartet auf eine manuelle Entscheidung.";

/** Übersetzte Relation, unabhängig vom review_status. `null` -> "Kein Konsens". */
export function predicateLabel(predicateId: MappingPredicate | null): string {
  return predicateId ? PREDICATE_LABELS[predicateId] : NO_CONSENSUS_LABEL;
}

export function predicateDescription(predicateId: MappingPredicate | null): string {
  return predicateId ? PREDICATE_DESCRIPTIONS[predicateId] : NO_CONSENSUS_DESCRIPTION;
}

/**
 * Herkunft eines Mappings, benannt statt als SEMAPV-CURIE gezeigt. Ein
 * Reviewer soll erkennen, ob ein Eintrag bereits bestaetigt wurde oder noch
 * algorithmisch unbestaetigt ist.
 */
export const JUSTIFICATION_LABELS: Record<MappingJustification, string> = {
  "semapv:StructuralMatching": "Struktureller Shortcut",
  "semapv:LLMBasedMatching": "LLM-Klassifikation",
  "semapv:MappingReview": "Manuell bestätigt",
};

export const JUSTIFICATION_DESCRIPTIONS: Record<MappingJustification, string> = {
  "semapv:StructuralMatching":
    "Aus einer bekannten Cross-Referenz zwischen den Rahmenwerken abgeleitet, ohne LLM-Aufruf.",
  "semapv:LLMBasedMatching":
    "Aus der LLM-Dreifachklassifikation mit Mehrheitsentscheid, noch nicht menschlich bestätigt.",
  "semapv:MappingReview": "Im Review von einer Person entschieden und damit verbindlich.",
};

/**
 * Wartet dieser Eintrag auf eine Entscheidung der Review-Weiche? Betrifft
 * genau die offenen Paare (RELATED oder ohne Mehrheitsentscheid), die frueher
 * aus der Liste herausgefiltert wurden.
 */
export function isAwaitingReview(mapping: Mapping): boolean {
  return mapping.review_status === "open";
}

/** Sortier- und Filterzustand der Mapping-Liste. */
export type MappingStatusFilter = "all" | "open" | "review" | "accepted" | "manual";

export const MAPPING_STATUS_LABELS: Record<MappingStatusFilter, string> = {
  all: "Alle",
  open: "Wartet auf Entscheidung",
  review: "Entscheidung erforderlich",
  accepted: "Automatisch akzeptiert",
  manual: "Manuell entschieden",
};

export function matchesStatusFilter(
  mapping: Mapping,
  filter: MappingStatusFilter,
  threshold: number,
): boolean {
  switch (filter) {
    case "open":
      return isAwaitingReview(mapping);
    case "review":
      // Spiegelt `mapping_service.needs_review()`: offener Review ODER
      // Konfidenz unterhalb der Schwelle.
      return (
        isAwaitingReview(mapping) ||
        (mapping.mapping_source !== "manual" && mapping.mapping_confidence < threshold)
      );
    case "accepted":
      return (
        !isAwaitingReview(mapping) &&
        mapping.mapping_source !== "manual" &&
        mapping.mapping_confidence >= threshold
      );
    case "manual":
      return !isAwaitingReview(mapping) && mapping.mapping_source === "manual";
    case "all":
      return true;
  }
}
