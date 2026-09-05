/**
 * Anzeigebegriffe der Integrationsstrategien.
 *
 * In der Oberflaeche heissen diese Konzepte "nicht zugeordnet"; der
 * mathematische Begriff (disjunkte Menge D) steht als Erlaeuterung daneben,
 * nicht als Ueberschrift.
 */

import type { IntegrationStrategy } from "@/api/types";

interface StrategyPresentation {
  label: string;
  description: string;
}

export const STRATEGY_PRESENTATION: Record<IntegrationStrategy, StrategyPresentation> = {
  own_class: {
    label: "Eigenständige Klasse",
    description:
      "Das Konzept wird unverändert als eigene Klasse in die harmonisierte Ontologie übernommen. Es bekommt keinen Anschluss an einen bestehenden Knoten.",
  },
  attach_to_skeleton: {
    label: "An Skelett anhängen",
    description:
      "Das Konzept wird als Unterklasse eines HR-QDE-Skelettknotens eingehängt (z. B. eines DQR-Niveaus). Die Zielklasse ist anzugeben.",
  },
  map_to_nearest: {
    label: "An nächstliegendes Konzept anhängen",
    description:
      "Das Konzept wird per skos:relatedMatch an das nächstgelegene Hub-Konzept gehängt. Weil dabei Bedeutung verloren geht, ist ein Vermerk zum Kontextverlust Pflicht.",
  },
  out_of_scope: {
    label: "Außerhalb des Geltungsbereichs",
    description:
      "Das Konzept gehört nicht zur harmonisierten Ontologie. Der Ausschluss ist zu begründen.",
  },
};

/** Strategien, die ein zusaetzliches Pflichtfeld nach sich ziehen. */
export const STRATEGY_REQUIRES_ANCHOR: IntegrationStrategy = "attach_to_skeleton";
export const STRATEGY_REQUIRES_CONTEXT_LOSS_NOTE: IntegrationStrategy = "map_to_nearest";

/** Erklaerung des Fachbegriffs, als Tooltip bzw. Fliesstext verwendet. */
export const UNMAPPED_EXPLANATION =
  "Nicht zugeordnete Konzepte kommen in keinem Mapping der konjunkten Menge K " +
  "(exactMatch, broadMatch, narrowMatch) vor. Fachlich entsprechen sie der disjunkten Menge D " +
  "des Modells. Für jedes muss entschieden werden, wie es in die harmonisierte Ontologie eingeht.";

export type IntegrationStatusFilter = "all" | "open" | "decided";

export const INTEGRATION_STATUS_LABELS: Record<IntegrationStatusFilter, string> = {
  all: "Alle",
  open: "Nur offen",
  decided: "Nur entschieden",
};
