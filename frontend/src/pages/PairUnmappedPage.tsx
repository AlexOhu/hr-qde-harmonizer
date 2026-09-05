/** Nicht zugeordnete Konzepte, eingegrenzt auf ein Framework-Paar. */

import { IntegrationWorkspace } from "@/features/integration/IntegrationWorkspace";
import { usePairContext } from "@/features/pairs/PairLayout";

export function PairUnmappedPage() {
  const { projectId, pair, isReadOnly } = usePairContext();

  return (
    <IntegrationWorkspace
      projectId={projectId}
      isReadOnly={isReadOnly}
      pair={{ frameworkAId: pair.frameworkAId, frameworkBId: pair.frameworkBId }}
    />
  );
}
