import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { ApiError } from "@/api/client";
import { ToastProvider } from "@/components/ui/toast";
import { TooltipProvider } from "@/components/ui/tooltip";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Ein nicht laufendes Backend oder eine 404 wird nicht wiederholt —
        // das kostet nur Zeit, bevor der Fehler sichtbar wird. Alles andere
        // bekommt zwei Versuche gegen kurzzeitige Aussetzer.
        retry: (failureCount, error) => {
          if (error instanceof ApiError && (error.isConnectionError || error.status < 500)) {
            return false;
          }
          return failureCount < 2;
        },
        refetchOnWindowFocus: false,
        staleTime: 1000,
      },
      mutations: { retry: false },
    },
  });
}

export function AppProviders({ children }: { children: ReactNode }) {
  // Im State statt als Modulkonstante, damit Tests jeweils einen frischen
  // Cache bekommen und sich nicht gegenseitig beeinflussen.
  const [queryClient] = useState(createQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={200}>
        <ToastProvider>{children}</ToastProvider>
      </TooltipProvider>
    </QueryClientProvider>
  );
}
