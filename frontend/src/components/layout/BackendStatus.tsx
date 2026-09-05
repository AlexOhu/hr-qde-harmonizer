/**
 * Erreichbarkeit des Backends in der Kopfzeile.
 *
 * Ohne diese Anzeige waere ein nicht laufendes Backend nur als Fehler in
 * einzelnen Panels sichtbar; hier steht es unabhaengig von der Seite
 * (Visibility of System State).
 */

import { useQuery } from "@tanstack/react-query";
import { CircleCheck, CircleX } from "lucide-react";

import { request } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";
import { API_BASE_URL } from "@/api/client";

export function BackendStatus() {
  const { isError, isPending } = useQuery({
    queryKey: queryKeys.health(),
    queryFn: ({ signal }) => request<{ status: string }>("/health", { timeoutMs: 5000, signal }),
    refetchInterval: 30_000,
    retry: false,
  });

  if (isPending) {
    return <span className="text-xs text-fg-subtle">Verbindung wird geprüft …</span>;
  }

  return (
    <Tooltip content={`API-Basis-URL: ${API_BASE_URL}`}>
      <span>
        {isError ? (
          <Badge tone="danger" icon={<CircleX aria-hidden="true" />}>
            Backend offline
          </Badge>
        ) : (
          <Badge tone="success" icon={<CircleCheck aria-hidden="true" />}>
            Backend verbunden
          </Badge>
        )}
      </span>
    </Tooltip>
  );
}
