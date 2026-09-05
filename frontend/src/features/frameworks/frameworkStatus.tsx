/**
 * Nutzerfreundliche Darstellung der Framework-Zustaende.
 *
 * Die Backend-Werte (`roh`, `formalisiert`, `bereit`) bleiben technisch
 * bestehen; hier bekommen sie eine Beschriftung, die sagt, woran man ist und
 * was als Naechstes zu tun waere.
 */

import { AlertTriangle, CheckCircle2, Sigma } from "lucide-react";
import type { ReactNode } from "react";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { FrameworkStatus } from "@/api/types";

interface FrameworkStatusPresentation {
  label: string;
  tone: NonNullable<BadgeProps["tone"]>;
  icon: ReactNode;
  /** Naechster Schritt; leer, wenn nichts zu tun ist. */
  nextAction: string | null;
}

export const FRAMEWORK_STATUS_PRESENTATION: Record<FrameworkStatus, FrameworkStatusPresentation> = {
  bereit: {
    label: "Bereit",
    tone: "success",
    icon: <CheckCircle2 aria-hidden="true" />,
    nextAction: null,
  },
  formalisiert: {
    label: "Embedding erforderlich",
    tone: "warning",
    icon: <Sigma aria-hidden="true" />,
    nextAction:
      "Die Datei wurde validiert und eingelesen. Berechnen Sie die Embeddings, damit das Framework verglichen werden kann.",
  },
  roh: {
    label: "Validierung fehlgeschlagen",
    tone: "danger",
    icon: <AlertTriangle aria-hidden="true" />,
    nextAction:
      "Die Datei erfüllt das SKOS-Minimalschema nicht. Korrigieren Sie sie und laden Sie sie erneut hoch.",
  },
};

export function FrameworkStatusBadge({ status }: { status: FrameworkStatus }) {
  const presentation = FRAMEWORK_STATUS_PRESENTATION[status];
  return (
    <Badge tone={presentation.tone} icon={presentation.icon}>
      {presentation.label}
    </Badge>
  );
}
