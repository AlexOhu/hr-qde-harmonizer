/**
 * Zeilenlogik der Framework-Vergleiche.
 *
 * `resolvePairAction` traegt die Entscheidung, welche einzelne Folgeaktion
 * pro Zustand angeboten wird; das Rendering
 * prueft, dass davon tatsaechlich nur ein Button ankommt und dass
 * UNRESOLVED-Faelle nicht als entscheidbare Reviews erscheinen.
 */

import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { derivePairs } from "./status";
import { PairTable, pairPath, resolvePairAction } from "./PairTable";
import { makePairStatus, renderWithProviders } from "@/test/utils";
import type { FrameworkPair } from "./status";

function pair(overrides: Parameters<typeof makePairStatus>[0] = {}): FrameworkPair {
  return derivePairs([makePairStatus(overrides)])[0];
}

describe("resolvePairAction", () => {
  const href = "/projects/proj_1/pairs/ecf/esco";

  it("bietet bei einem laufenden Vergleich nur das Ansehen des Status an", () => {
    const action = resolvePairAction(pair({ job_status: "running" }), href, false);
    expect(action).toEqual({ kind: "link", label: "Status ansehen", to: href, variant: "secondary" });
  });

  it("bietet bei einem gescheiterten Vergleich einen erneuten Versuch an", () => {
    const action = resolvePairAction(pair({ job_status: "failed" }), href, false);
    expect(action).toMatchObject({ kind: "retry", label: "Erneut versuchen" });
  });

  it("bietet im Snapshot statt eines Neustarts nur das Ansehen an", () => {
    const action = resolvePairAction(pair({ job_status: "failed" }), href, true);
    expect(action).toEqual({ kind: "link", label: "Ansehen", to: href, variant: "secondary" });
  });

  it("fuehrt bei offenem Review direkt zur gefilterten Mapping-Ansicht", () => {
    const action = resolvePairAction(pair({ pending_review_count: 5 }), href, false);
    expect(action).toEqual({
      kind: "link",
      label: "Mappings prüfen",
      to: `${href}/mappings?status=review`,
      variant: "primary",
    });
  });

  it("fuehrt bei offener Integration zu den nicht zugeordneten Konzepten", () => {
    const action = resolvePairAction(
      pair({ pending_review_count: 0, unresolved_count: 0, disjoint_open: 3 }),
      href,
      false,
    );
    expect(action).toEqual({
      kind: "link",
      label: "Konzepte klären",
      to: `${href}/unmapped?status=open`,
      variant: "primary",
    });
  });

  it("bietet bei einem abgeschlossenen Vergleich ohne offene Arbeit nur Details an", () => {
    const action = resolvePairAction(pair(), href, false);
    expect(action).toEqual({ kind: "link", label: "Details ansehen", to: href, variant: "secondary" });
  });
});

describe("PairTable", () => {
  it("zeigt Ergebnis und offene Reviews getrennt von nicht auflösbaren Fällen", async () => {
    const pairs = derivePairs([
      makePairStatus({
        mappings_count: 1248,
        pending_review_count: 17,
        unresolved_count: 48,
      }),
    ]);

    renderWithProviders(
      <PairTable
        projectId="proj_1"
        pairs={pairs}
        onRetry={vi.fn()}
        onReset={vi.fn()}
        isReadOnly={false}
      />,
    );

    expect(screen.getByText(/1\.248/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /17 Reviews offen/ })).toHaveAttribute(
      "href",
      `${pairPath("proj_1", pairs[0])}/mappings?status=review`,
    );
    // 48 UNRESOLVED-Faelle sind sichtbar, aber kein Link — sie sind hier nicht entscheidbar.
    expect(screen.getByText(/48 nicht auflösbare Fälle \(UNRESOLVED\)/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /48/ })).not.toBeInTheDocument();

    // Genau eine primaere Aktion fuer diese Zeile.
    expect(screen.getAllByRole("link", { name: /prüfen|ansehen|Ansehen/ })).toHaveLength(1);
  });

  it("bietet bei einem gescheiterten Lauf genau einen Erneut-versuchen-Button", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    const pairs = derivePairs([makePairStatus({ job_status: "failed" })]);

    renderWithProviders(
      <PairTable
        projectId="proj_1"
        pairs={pairs}
        onRetry={onRetry}
        onReset={vi.fn()}
        isReadOnly={false}
      />,
    );

    const buttons = screen.getAllByRole("button", { name: /Erneut versuchen/ });
    expect(buttons).toHaveLength(1);

    await user.click(buttons[0]);
    expect(onRetry).toHaveBeenCalledWith(pairs[0]);
  });

  it("bietet im Snapshot keinen Neustart für einen gescheiterten Lauf an", () => {
    const pairs = derivePairs([makePairStatus({ job_status: "failed" })]);

    renderWithProviders(
      <PairTable projectId="proj_1" pairs={pairs} onRetry={vi.fn()} onReset={vi.fn()} isReadOnly />,
    );

    expect(screen.queryByRole("button", { name: /Erneut versuchen/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ansehen" })).toBeInTheDocument();
  });

  it("zeigt die konkrete Fehlermeldung eines gescheiterten Laufs", () => {
    const pairs = derivePairs([
      makePairStatus({ job_status: "failed", error: "Mistral-API: 429 Too Many Requests" }),
    ]);

    renderWithProviders(
      <PairTable
        projectId="proj_1"
        pairs={pairs}
        onRetry={vi.fn()}
        onReset={vi.fn()}
        isReadOnly={false}
      />,
    );

    expect(screen.getByText("Mistral-API: 429 Too Many Requests")).toBeInTheDocument();
  });

  it("zeigt bei einem unterbrochenen Lauf keine Fehlermeldung, nur den allgemeinen Hinweis", () => {
    const pairs = derivePairs([makePairStatus({ job_status: "interrupted", error: null })]);

    renderWithProviders(
      <PairTable
        projectId="proj_1"
        pairs={pairs}
        onRetry={vi.fn()}
        onReset={vi.fn()}
        isReadOnly={false}
      />,
    );

    expect(screen.getByText(/Ein API-Neustart hat den Lauf unterbrochen/)).toBeInTheDocument();
  });

  it("bietet fuer ein noch nicht gestartetes Paar keinen Zuruecksetzen-Button an", () => {
    const pairs = derivePairs([makePairStatus({ job_status: null, job_id: null })]);

    renderWithProviders(
      <PairTable
        projectId="proj_1"
        pairs={pairs}
        onRetry={vi.fn()}
        onReset={vi.fn()}
        isReadOnly={false}
      />,
    );

    expect(screen.queryByRole("button", { name: /Zurücksetzen/ })).not.toBeInTheDocument();
  });

  it("bietet im Snapshot keinen Zuruecksetzen-Button an, obwohl das Paar klassifiziert ist", () => {
    const pairs = derivePairs([makePairStatus()]);

    renderWithProviders(
      <PairTable projectId="proj_1" pairs={pairs} onRetry={vi.fn()} onReset={vi.fn()} isReadOnly />,
    );

    expect(screen.queryByRole("button", { name: /Zurücksetzen/ })).not.toBeInTheDocument();
  });

  it("oeffnet ueber Zuruecksetzen den Reset-Dialog fuer ein klassifiziertes Paar", async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();
    const pairs = derivePairs([makePairStatus()]);

    renderWithProviders(
      <PairTable
        projectId="proj_1"
        pairs={pairs}
        onRetry={vi.fn()}
        onReset={onReset}
        isReadOnly={false}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Zurücksetzen/ }));
    expect(onReset).toHaveBeenCalledWith(pairs[0]);
  });
});
