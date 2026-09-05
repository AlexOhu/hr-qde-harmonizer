/** Mapping-Review, eingegrenzt auf ein Framework-Paar. */

import { MappingWorkspace } from "@/features/mappings/MappingWorkspace";
import { usePairContext } from "@/features/pairs/PairLayout";

export function PairMappingsPage() {
  const { projectId, pair, isReadOnly } = usePairContext();

  return (
    <MappingWorkspace
      projectId={projectId}
      isReadOnly={isReadOnly}
      pair={{ frameworkAId: pair.frameworkAId, frameworkBId: pair.frameworkBId }}
    />
  );
}
