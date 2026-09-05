import { Link } from "react-router-dom";

import { AppShell, PageBody } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/common/states";

export function NotFoundPage() {
  return (
    <AppShell>
      <PageBody>
        <EmptyState
          title="Seite nicht gefunden"
          description="Diese Adresse gehört zu keinem Bereich der Anwendung."
          action={
            <Button asChild variant="primary">
              <Link to="/projects">Zur Projektübersicht</Link>
            </Button>
          }
        />
      </PageBody>
    </AppShell>
  );
}
