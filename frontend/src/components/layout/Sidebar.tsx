/**
 * Hauptnavigation.
 *
 * Global gibt es nur zwei Ziele (Projekte, Framework-Bibliothek). Sobald ein
 * Projekt geoeffnet ist, kommt ein Projektabschnitt mit den vier fachlichen
 * Bereichen dazu. Klassifikation, SSSOM-Vorschau und Projekt-Status sind
 * bewusst KEINE Navigationsziele: sie sind Aktionen bzw. Bestandteile der
 * jeweiligen Arbeitsflaeche.
 */

import {
  FolderKanban,
  LayoutDashboard,
  Library,
  PackageOpen,
  Puzzle,
  Table2,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import type { Project } from "@/api/types";
import { cn } from "@/lib/utils";

interface NavItemProps {
  to: string;
  icon: ReactNode;
  label: string;
  /** Offene Punkte; wird als Zahl neben dem Eintrag angezeigt. */
  count?: number;
  end?: boolean;
}

function NavItem({ to, icon, label, count, end }: NavItemProps) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }: { isActive: boolean }) =>
        cn(
          "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors [&_svg]:size-4",
          isActive
            ? "bg-accent-soft text-accent"
            : "text-fg-muted hover:bg-surface-muted hover:text-fg",
        )
      }
    >
      {icon}
      <span className="flex-1 truncate">{label}</span>
      {count !== undefined && count > 0 ? (
        <span
          className="rounded-full bg-warning-soft px-1.5 text-[0.6875rem] font-semibold tabular-nums text-warning"
          aria-label={`${count} offen`}
        >
          {count}
        </span>
      ) : null}
    </NavLink>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="px-2.5 pb-1 pt-4 text-[0.6875rem] font-semibold tracking-wide text-fg-subtle uppercase">
      {children}
    </div>
  );
}

export interface SidebarProps {
  /** Gesetzt, sobald ein Projekt geoeffnet ist. */
  project?: Project;
  openReviews?: number;
  openIntegrations?: number;
}

export function Sidebar({ project, openReviews, openIntegrations }: SidebarProps) {
  const projectBase = project ? `/projects/${encodeURIComponent(project.project_id)}` : null;

  return (
    <nav
      aria-label="Hauptnavigation"
      className="flex h-full w-56 shrink-0 flex-col overflow-y-auto border-r border-border-subtle bg-surface px-2 pb-4"
    >
      <div className="px-2.5 pb-3 pt-4">
        <NavLink to="/projects" className="block">
          <div className="text-sm font-semibold text-fg">HR-QDE Harmonizer</div>
          <div className="text-[0.6875rem] text-fg-subtle">Rahmenwerk-Harmonisierung</div>
        </NavLink>
      </div>

      <div className="space-y-0.5">
        <NavItem to="/projects" icon={<FolderKanban />} label="Projekte" end />
        <NavItem to="/frameworks" icon={<Library />} label="Framework-Bibliothek" />
      </div>

      {project && projectBase ? (
        <>
          <SectionLabel>Aktuelles Projekt</SectionLabel>
          <div className="px-2.5 pb-2">
            <div className="truncate text-xs font-medium text-fg" title={project.name}>
              {project.name}
            </div>
            {project.status === "snapshot" ? (
              <Badge tone="neutral" className="mt-1">
                Snapshot · schreibgeschützt
              </Badge>
            ) : null}
          </div>
          <div className="space-y-0.5">
            <NavItem to={projectBase} icon={<LayoutDashboard />} label="Übersicht" end />
            <NavItem
              to={`${projectBase}/mappings`}
              icon={<Table2 />}
              label="Mappings"
              count={openReviews}
            />
            <NavItem
              to={`${projectBase}/integration`}
              icon={<Puzzle />}
              label="Integration"
              count={openIntegrations}
            />
            <NavItem to={`${projectBase}/export`} icon={<PackageOpen />} label="Export" />
          </div>
        </>
      ) : null}
    </nav>
  );
}
