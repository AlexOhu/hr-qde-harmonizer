/**
 * Einheitliche Darstellung der Paar- und Job-Zustaende.
 *
 * Alle Beschriftungen stehen hier zentral, damit derselbe Zustand in
 * Projektuebersicht, Pair-Workspace und Run-Historie identisch benannt wird
 * (Recognition over Recall).
 */

import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  ClipboardCheck,
  Loader2,
  PauseCircle,
  PlugZap,
  Puzzle,
} from "lucide-react";
import type { ReactNode } from "react";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";
import type { JobStatus } from "@/api/types";
import type { PairLifecycle } from "./status";

interface StatusPresentation {
  label: string;
  tone: NonNullable<BadgeProps["tone"]>;
  icon: ReactNode;
  /** Kurze Erlaeuterung, was als Naechstes zu tun ist. */
  hint: string;
}

export const PAIR_LIFECYCLE_PRESENTATION: Record<PairLifecycle, StatusPresentation> = {
  not_started: {
    label: "Nicht gestartet",
    tone: "neutral",
    icon: <CircleDashed aria-hidden="true" />,
    hint: "Für dieses Paar wurde noch kein Vergleich ausgeführt.",
  },
  running: {
    label: "Läuft",
    tone: "info",
    icon: <Loader2 className="animate-spin" aria-hidden="true" />,
    hint: "Die Klassifikation läuft im Hintergrund.",
  },
  paused: {
    label: "Pausiert",
    tone: "warning",
    icon: <PauseCircle aria-hidden="true" />,
    hint: "Der Lauf wurde angehalten und kann fortgesetzt werden.",
  },
  failed: {
    label: "Fehlgeschlagen",
    tone: "danger",
    icon: <AlertTriangle aria-hidden="true" />,
    hint: "Der Lauf wurde abgebrochen. Ein Neustart klassifiziert nur die verbliebenen Paare.",
  },
  interrupted: {
    label: "Unterbrochen",
    tone: "warning",
    icon: <PlugZap aria-hidden="true" />,
    hint: "Ein API-Neustart hat den Lauf unterbrochen. Bereits klassifizierte Paare sind erhalten.",
  },
  review_required: {
    label: "Review erforderlich",
    tone: "warning",
    icon: <ClipboardCheck aria-hidden="true" />,
    hint:
      "Es liegen Mappings unterhalb der Konfidenzschwelle und/oder Klassifikationen ohne "
      + "Mehrheitsentscheid (UNRESOLVED) vor. Nur Erstere lassen sich unter „Mappings“ entscheiden; "
      + "UNRESOLVED-Fälle dokumentiert der Prüfbericht.",
  },
  integration_required: {
    label: "Integration erforderlich",
    tone: "warning",
    icon: <Puzzle aria-hidden="true" />,
    hint: "Nicht zugeordnete Konzepte brauchen noch eine Integrationsstrategie.",
  },
  complete: {
    label: "Abgeschlossen",
    tone: "success",
    icon: <CheckCircle2 aria-hidden="true" />,
    hint: "Klassifikation, Review und Integrationsentscheidungen sind vollständig.",
  },
};

export const JOB_STATUS_PRESENTATION: Record<JobStatus, StatusPresentation> = {
  running: PAIR_LIFECYCLE_PRESENTATION.running,
  paused: PAIR_LIFECYCLE_PRESENTATION.paused,
  failed: PAIR_LIFECYCLE_PRESENTATION.failed,
  interrupted: PAIR_LIFECYCLE_PRESENTATION.interrupted,
  completed: {
    label: "Abgeschlossen",
    tone: "success",
    icon: <CheckCircle2 aria-hidden="true" />,
    hint: "Alle Kandidatenpaare wurden klassifiziert.",
  },
};

export function PairStatusBadge({ lifecycle }: { lifecycle: PairLifecycle }) {
  const presentation = PAIR_LIFECYCLE_PRESENTATION[lifecycle];
  return (
    <Tooltip content={presentation.hint}>
      <span>
        <Badge tone={presentation.tone} icon={presentation.icon}>
          {presentation.label}
        </Badge>
      </span>
    </Tooltip>
  );
}

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const presentation = JOB_STATUS_PRESENTATION[status];
  return (
    <Tooltip content={presentation.hint}>
      <span>
        <Badge tone={presentation.tone} icon={presentation.icon}>
          {presentation.label}
        </Badge>
      </span>
    </Tooltip>
  );
}
