/**
 * Routenbaum.
 *
 * Die URL traegt den vollstaendigen Arbeitskontext: Projekt, Framework-Paar
 * und Arbeitsbereich stehen im Pfad, Filter und ausgewaehlter Datensatz in
 * den Suchparametern. Deep-Links, Vor/Zurueck und mehrere Tabs funktionieren
 * dadurch ohne globalen Anwendungszustand.
 */

import { Navigate, Route, Routes } from "react-router-dom";

import { ProjectLayout } from "@/features/projects/ProjectLayout";
import { PairLayout } from "@/features/pairs/PairLayout";
import { ProjectsPage } from "@/pages/ProjectsPage";
import { FrameworkLibraryPage } from "@/pages/FrameworkLibraryPage";
import { ProjectOverviewPage } from "@/pages/ProjectOverviewPage";
import { ProjectMappingsPage } from "@/pages/ProjectMappingsPage";
import { ProjectIntegrationPage } from "@/pages/ProjectIntegrationPage";
import { ProjectExportPage } from "@/pages/ProjectExportPage";
import { PairOverviewPage } from "@/pages/PairOverviewPage";
import { PairMappingsPage } from "@/pages/PairMappingsPage";
import { PairUnmappedPage } from "@/pages/PairUnmappedPage";
import { PairRunsPage } from "@/pages/PairRunsPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/projects" replace />} />
      <Route path="/projects" element={<ProjectsPage />} />
      <Route path="/frameworks" element={<FrameworkLibraryPage />} />

      <Route path="/projects/:projectId" element={<ProjectLayout />}>
        <Route index element={<ProjectOverviewPage />} />
        <Route path="mappings" element={<ProjectMappingsPage />} />
        <Route path="integration" element={<ProjectIntegrationPage />} />
        <Route path="export" element={<ProjectExportPage />} />

        <Route path="pairs/:frameworkAId/:frameworkBId" element={<PairLayout />}>
          <Route index element={<PairOverviewPage />} />
          <Route path="mappings" element={<PairMappingsPage />} />
          <Route path="unmapped" element={<PairUnmappedPage />} />
          <Route path="runs" element={<PairRunsPage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
