/**
 * Integrationstests der kritischen Nutzerpfade.
 *
 * Gerendert wird jeweils der echte Routenbaum gegen ein gefaelschtes
 * Backend; geprueft werden sowohl die Anzeige als auch die tatsaechlich
 * abgesetzten Requests.
 */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { AppRoutes } from "@/app/router";
import {
  installFakeBackend,
  makeConcept,
  makeFramework,
  makeJob,
  makeMapping,
  makeOpenMapping,
  makePairStatus,
  makePipelineStatus,
  makeProject,
  renderWithProviders,
  route,
  routeStartsWith,
  type FakeBackend,
  type FakeRoute,
} from "./utils";

let backend: FakeBackend | null = null;

afterEach(() => {
  backend?.restore();
  backend = null;
});

/** Routen, die praktisch jede Seite braucht. */
function baseRoutes(overrides: FakeRoute[] = []): FakeRoute[] {
  return [
    ...overrides,
    route("GET", "/health", () => ({ status: "ok" })),
    route("GET", "/projects/", () => [makeProject()]),
    route("GET", "/projects/proj_1", () => makeProject()),
    route("GET", "/projects/proj_1/pipeline-status", () => makePipelineStatus()),
    route("GET", "/kqr/", () => [
      makeFramework(),
      makeFramework({ id: "ecf", name: "e-CF", is_hub: false, concept_count: 45 }),
    ]),
    route("GET", "/classification/", () => [makeJob()]),
    route("GET", "/classification/preconditions", () => ({
      neo4j_reachable: false,
      llm_configured: true,
      llm_providers: "mistral",
    })),
    route("GET", "/mappings/config", () => ({ mapping_confidence_threshold: 0.67 })),
    route("GET", "/mappings/", () => []),
    route("GET", "/disjoint/concepts", () => []),
    route("GET", "/disjoint/decisions", () => []),
    route("GET", "/disjoint/summary", () => ({
      total_disjoint: 0,
      decided: 0,
      open: 0,
      by_strategy: { own_class: 0, attach_to_skeleton: 0, map_to_nearest: 0, out_of_scope: 0 },
    })),
    route("GET", "/export/summary", () => ({
      no_consensus_pairs: 0,
      related_pairs: 0,
      low_confidence_mappings: 0,
      total_open: 0,
      disjoint_open: 0,
      coverage_resolved: 10,
      coverage_total: 10,
      coverage_ratio: 1,
      open_review_count: 0,
    })),
    route("GET", "/export/clusters", () => [{ cluster_id: 1, concept_uris: [], auto_label: "A", llm_label: null, centroid_uri: null }]),
  ];
}

describe("Projekt öffnen", () => {
  it("listet Projekte und zeigt nach dem Öffnen die Projektübersicht", async () => {
    const user = userEvent.setup();
    backend = installFakeBackend(baseRoutes());

    renderWithProviders(<AppRoutes />, { route: "/projects" });

    expect(await screen.findByRole("link", { name: "IT-Harmonisierung 2026" })).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "Öffnen" }));

    // Die Übersicht zeigt Projektnamen als Überschrift und das Paar aus dem Pipelinestatus.
    expect(
      await screen.findByRole("heading", { name: "IT-Harmonisierung 2026", level: 1 }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "e-CF ↔ ESCO" })).toBeInTheDocument();
  });

  it("weist einen nicht existierenden Projekt-Deeplink klar aus", async () => {
    backend = installFakeBackend([
      ...baseRoutes(),
      route("GET", "/projects/fehlt", () => ({ detail: "Projekt 'fehlt' nicht gefunden." }), 404),
    ]);

    renderWithProviders(<AppRoutes />, { route: "/projects/fehlt" });

    expect(await screen.findByText("Projekt nicht gefunden")).toBeInTheDocument();
  });
});

describe("Framework hochladen", () => {
  it("sendet Name, Format, Hub-Flag und Datei als Multipart-Formular", async () => {
    const user = userEvent.setup();
    backend = installFakeBackend([
      ...baseRoutes(),
      route("POST", "/kqr/", () =>
        makeFramework({ id: "dqr", name: "DQR", status: "bereit", concept_count: 32 }),
      ),
    ]);

    renderWithProviders(<AppRoutes />, { route: "/frameworks" });

    await user.click(await screen.findByRole("button", { name: /Framework hinzufügen/ }));

    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText(/^Name/), "DQR");
    await user.upload(
      within(dialog).getByLabelText(/^Datei/),
      new File(["@prefix skos: <http://www.w3.org/2004/02/skos/core#> ."], "dqr.ttl", {
        type: "text/turtle",
      }),
    );
    await user.click(within(dialog).getByLabelText(/Hub-Framework/));
    await user.click(within(dialog).getByRole("button", { name: "Hinzufügen" }));

    await waitFor(() => {
      const upload = backend!.calls.find(
        (call) => call.method === "POST" && call.url.pathname === "/kqr/",
      );
      expect(upload).toBeDefined();
      expect(upload!.body).toMatchObject({
        name: "DQR",
        source_format: "turtle",
        is_hub: "true",
      });
    });
  });

  it("berechnet Embeddings für ein formalisiertes Framework", async () => {
    const user = userEvent.setup();
    backend = installFakeBackend([
      route("GET", "/health", () => ({ status: "ok" })),
      route("GET", "/kqr/", () => [
        makeFramework({ id: "eqf", name: "EQF 2017", status: "formalisiert", is_hub: false }),
      ]),
      route("POST", "/kqr/eqf/embed", () =>
        makeFramework({ id: "eqf", name: "EQF 2017", status: "bereit", is_hub: false }),
      ),
    ]);

    renderWithProviders(<AppRoutes />, { route: "/frameworks" });

    expect(await screen.findByText("Embedding erforderlich")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Embeddings berechnen/ }));

    await waitFor(() => {
      expect(
        backend!.calls.some(
          (call) => call.method === "POST" && call.url.pathname === "/kqr/eqf/embed",
        ),
      ).toBe(true);
    });
  });
});

describe("Klassifikation starten und verfolgen", () => {
  it("startet einen Vergleich mit den gewählten Frameworks als Query-Parameter", async () => {
    const user = userEvent.setup();
    backend = installFakeBackend([
      ...baseRoutes(),
      route("POST", "/classification/start", () => ({ job_id: "job_neu" })),
    ]);

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1" });

    await user.click(await screen.findByRole("button", { name: /Vergleich hinzufügen/ }));

    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText(/Framework A/), "esco");
    await user.selectOptions(within(dialog).getByLabelText(/Framework B/), "ecf");
    await user.click(within(dialog).getByRole("button", { name: "Vergleich starten" }));

    await waitFor(() => {
      const start = backend!.calls.find(
        (call) => call.method === "POST" && call.url.pathname === "/classification/start",
      );
      expect(start).toBeDefined();
      expect(start!.url.searchParams.get("kqr_a_id")).toBe("esco");
      expect(start!.url.searchParams.get("kqr_b_id")).toBe("ecf");
      expect(start!.url.searchParams.get("project_id")).toBe("proj_1");
    });
  });

  it("verhindert den Start, wenn beide Seiten dasselbe Framework wären", async () => {
    const user = userEvent.setup();
    backend = installFakeBackend(baseRoutes());

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1" });

    await user.click(await screen.findByRole("button", { name: /Vergleich hinzufügen/ }));
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText(/Framework B/), "esco");

    expect(within(dialog).getByRole("button", { name: "Vergleich starten" })).toBeDisabled();
    expect(
      within(dialog).getByText("Bitte zwei verschiedene Frameworks wählen."),
    ).toBeInTheDocument();
  });

  it("zeigt einen laufenden Job mit Fortschritt an", async () => {
    backend = installFakeBackend([
      ...baseRoutes([
        route("GET", "/projects/proj_1/pipeline-status", () =>
          makePipelineStatus({
            kqr_pairs: [
              makePairStatus({
                job_status: "running",
                classified_pairs: 576,
                total_pairs: 900,
              }),
            ],
          }),
        ),
      ]),
    ]);

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1" });

    expect(await screen.findByText("Läuft")).toBeInTheDocument();
    expect(await screen.findByText("576 / 900 Konzeptpaare")).toBeInTheDocument();
    expect(
      screen.getByRole("progressbar", { name: /Klassifikation e-CF ↔ ESCO/ }),
    ).toHaveAttribute("aria-valuenow", "64");
  });

  it("bietet bei einem gescheiterten Lauf einen Neustart an und zeigt die Fehlermeldung", async () => {
    backend = installFakeBackend([
      ...baseRoutes([
        route("GET", "/projects/proj_1/pipeline-status", () =>
          makePipelineStatus({
            kqr_pairs: [
              makePairStatus({
                job_status: "failed",
                classified_pairs: 128,
                error: "Mistral-API: 429 Too Many Requests",
              }),
            ],
          }),
        ),
      ]),
    ]);

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1" });

    expect(await screen.findByText("Fehlgeschlagen")).toBeInTheDocument();
    expect(screen.getByText("Mistral-API: 429 Too Many Requests")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Erneut versuchen/ })).toBeInTheDocument();
  });
});

describe("Mapping manuell entscheiden", () => {
  const reviewMapping = makeMapping({ mapping_confidence: 0.54 });

  it("speichert Prädikat, Begründung und Autor", async () => {
    const user = userEvent.setup();
    backend = installFakeBackend([
      ...baseRoutes([route("GET", "/mappings/", () => [reviewMapping])]),
      route("PUT", "/mappings/map_1", () =>
        makeMapping({ mapping_source: "manual", mapping_confidence: 1.0, author: "AO" }),
      ),
    ]);

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/mappings" });

    // Das erste Mapping wird automatisch ausgewählt, die Detailspalte ist gefüllt.
    expect(await screen.findByRole("heading", { name: "Manuelle Entscheidung" })).toBeInTheDocument();

    // Die Auswahl nennt das SKOS-Prädikat als Wert, die deutsche Beschriftung als Text.
    await user.selectOptions(screen.getByLabelText(/^Relation/), "skos:exactMatch");
    await user.type(screen.getByLabelText(/^Begründung/), "Beide bezeichnen dieselbe Fähigkeit.");
    await user.type(screen.getByLabelText(/^Autor/), "AO");
    await user.click(screen.getByRole("button", { name: "Entscheidung speichern" }));

    await waitFor(() => {
      const update = backend!.calls.find(
        (call) => call.method === "PUT" && call.url.pathname === "/mappings/map_1",
      );
      expect(update).toBeDefined();
      expect(update!.body).toEqual({
        predicate: "skos:exactMatch",
        justification: "Beide bezeichnen dieselbe Fähigkeit.",
        author: "AO",
      });
    });
  });

  it("verlangt eine Begründung, bevor gespeichert wird", async () => {
    const user = userEvent.setup();
    backend = installFakeBackend(baseRoutes([route("GET", "/mappings/", () => [reviewMapping])]));

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/mappings" });

    await user.click(await screen.findByRole("button", { name: "Entscheidung speichern" }));

    expect(
      await screen.findByText("Eine Begründung ist verpflichtend zu dokumentieren."),
    ).toBeInTheDocument();
    expect(
      backend!.calls.some((call) => call.method === "PUT"),
    ).toBe(false);
  });

  it("zeigt automatisch akzeptierte Mappings ohne Bearbeitungsformular", async () => {
    backend = installFakeBackend(
      baseRoutes([
        route("GET", "/mappings/", () => [
          makeMapping({ mapping_confidence: 0.95, predicate_id: "skos:exactMatch" }),
        ]),
      ]),
    );

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/mappings" });

    expect(await screen.findByText(/Automatisch akzeptiert/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Manuelle Entscheidung" })).not.toBeInTheDocument();
  });
});

describe("Mapping-Liste paginiert", () => {
  const mappings = Array.from({ length: 25 }, (_, index) =>
    makeMapping({
      mapping_id: `map_${index + 1}`,
      subject_label: `Konzept ${index + 1}`,
      mapping_confidence: 0.95,
    }),
  );

  it("zeigt Mappings seitenweise mit konfigurierbarer Seitengröße", async () => {
    const user = userEvent.setup();
    backend = installFakeBackend(baseRoutes([route("GET", "/mappings/", () => mappings)]));

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/mappings" });

    const list = await screen.findByRole("region", { name: "Mapping-Liste" });
    await waitFor(() => expect(within(list).getAllByRole("listitem")).toHaveLength(20));
    expect(within(list).getByText("Seite 1 von 2")).toBeInTheDocument();

    await user.click(within(list).getByRole("button", { name: "Nächste Seite" }));
    await waitFor(() => expect(within(list).getAllByRole("listitem")).toHaveLength(5));
    expect(within(list).getByText("Seite 2 von 2")).toBeInTheDocument();

    await user.selectOptions(
      within(list).getByRole("combobox", { name: "Einträge pro Seite" }),
      "100",
    );
    await waitFor(() => expect(within(list).getAllByRole("listitem")).toHaveLength(25));
    expect(within(list).getByText("Seite 1 von 1")).toBeInTheDocument();
  });
});

describe("Integrationsentscheidung speichern", () => {
  const concept = makeConcept();

  it("sendet Strategie, Begründung und Autor an das Backend", async () => {
    const user = userEvent.setup();
    backend = installFakeBackend([
      ...baseRoutes([route("GET", "/disjoint/concepts", () => [concept])]),
      routeStartsWith("GET", "/disjoint/concepts/", () => ({
        concept_id: concept.uri,
        suggested_strategy: "own_class",
      })),
      routeStartsWith("POST", "/disjoint/concepts/", () => ({
        decision_id: "dec_1",
        concept_id: concept.uri,
        concept_label: concept.pref_label,
        kqr_id: "ecf",
        strategy: "own_class",
        anchor_class: null,
        context_loss_note: null,
        justification: "Eigenständiges Konzept ohne Entsprechung.",
        author: "AO",
        created_at: "2026-08-25T10:00:00",
      })),
    ]);

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/integration" });

    expect(
      await screen.findByRole("heading", { name: "Integrationsstrategie festlegen" }),
    ).toBeInTheDocument();

    await user.type(
      screen.getByLabelText(/^Begründung/),
      "Eigenständiges Konzept ohne Entsprechung.",
    );
    await user.type(screen.getByLabelText(/^Autor/), "AO");
    await user.click(screen.getByRole("button", { name: "Entscheidung speichern" }));

    await waitFor(() => {
      const decide = backend!.calls.find(
        (call) => call.method === "POST" && call.url.pathname.includes("/decide"),
      );
      expect(decide).toBeDefined();
      expect(decide!.body).toMatchObject({
        strategy: "own_class",
        justification: "Eigenständiges Konzept ohne Entsprechung.",
        author: "AO",
        anchor_class: null,
        context_loss_note: null,
      });
      // Die Konzept-URI steht prozentkodiert im Pfad.
      expect(decodeURIComponent(decide!.url.pathname)).toContain(concept.uri);
    });
  });

  it("verlangt bei „An Skelett anhängen“ eine Zielklasse", async () => {
    const user = userEvent.setup();
    backend = installFakeBackend([
      ...baseRoutes([route("GET", "/disjoint/concepts", () => [concept])]),
      routeStartsWith("GET", "/disjoint/concepts/", () => ({
        concept_id: concept.uri,
        suggested_strategy: "own_class",
      })),
    ]);

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/integration" });

    await user.selectOptions(await screen.findByLabelText(/^Strategie/), "attach_to_skeleton");
    await user.type(screen.getByLabelText(/^Begründung/), "Nah an einer Oberklasse.");
    await user.type(screen.getByLabelText(/^Autor/), "AO");
    await user.click(screen.getByRole("button", { name: "Entscheidung speichern" }));

    expect(
      await screen.findByText('Für „An Skelett anhängen“ ist eine Zielklasse erforderlich.'),
    ).toBeInTheDocument();
    expect(backend!.calls.some((call) => call.method === "POST")).toBe(false);
  });

  it("weist eine bereits andernorts getroffene Entscheidung als solche aus", async () => {
    backend = installFakeBackend([
      ...baseRoutes([
        route("GET", "/disjoint/concepts", () => [concept]),
        route("GET", "/disjoint/decisions", () => [
          {
            decision_id: "dec_1",
            concept_id: concept.uri,
            concept_label: concept.pref_label,
            kqr_id: "ecf",
            strategy: "out_of_scope",
            anchor_class: null,
            context_loss_note: null,
            justification: "Gehört nicht zur Zieldomäne.",
            author: "AO",
            created_at: "2026-08-24T10:00:00",
          },
        ]),
      ]),
    ]);

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/integration" });

    expect(await screen.findByText("Gehört nicht zur Zieldomäne.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Entscheidung ändern" })).toBeInTheDocument();
  });
});

describe("Export-Readiness", () => {
  it("meldet den Export als bereit, wenn nichts offen ist", async () => {
    backend = installFakeBackend(baseRoutes());

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/export" });

    expect(await screen.findByText("Export bereit")).toBeInTheDocument();
    expect(screen.getByText("Mapping-Review abgeschlossen")).toBeInTheDocument();
  });

  it("nennt die Blocker und verlinkt in die gefilterte Arbeitsansicht", async () => {
    backend = installFakeBackend(
      baseRoutes([
        route("GET", "/projects/proj_1/pipeline-status", () =>
          makePipelineStatus({
            kqr_pairs: [makePairStatus({ pending_review_count: 12, disjoint_open: 4 })],
            disjoint_open: 4,
            disjoint_decided: 6,
            export_ready: false,
          }),
        ),
      ]),
    );

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/export" });

    expect(await screen.findByText("Export blockiert")).toBeInTheDocument();
    expect(
      screen.getByText("12 Mappings benötigen eine Entscheidung"),
    ).toBeInTheDocument();

    expect(screen.getByRole("link", { name: "Mappings prüfen" })).toHaveAttribute(
      "href",
      "/projects/proj_1/mappings?status=review",
    );
    expect(screen.getByRole("link", { name: "Konzepte klären" })).toHaveAttribute(
      "href",
      "/projects/proj_1/integration?status=open",
    );
  });

  it("blockiert den Ontologie-Export, solange kein Clustering vorliegt", async () => {
    backend = installFakeBackend(
      baseRoutes([
        route("GET", "/export/clusters", () => []),
        route("GET", "/projects/proj_1/pipeline-status", () =>
          makePipelineStatus({ clustering_done: false }),
        ),
      ]),
    );

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/export" });

    expect(await screen.findByText("Clustering noch nicht ausgeführt")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Clustering starten/ })).toBeInTheDocument();

    // Der Kopf darf nicht "Alle Vorbedingungen sind erfüllt" behaupten, solange
    // das Clustering als Ausstehend-Zeile mit eigener Aktion sichtbar ist.
    expect(screen.getByText("Export bereit, einzelne Punkte offen")).toBeInTheDocument();
    expect(screen.queryByText("Export bereit")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Alle Vorbedingungen sind erfüllt/),
    ).not.toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Harmonisierte Ontologie herunterladen" }),
    ).toBeDisabled();
    // SSSOM und Prüfbericht haengen nicht am Clustering und bleiben nutzbar.
    expect(screen.getByRole("button", { name: "SSSOM-Mappings herunterladen" })).toBeEnabled();
  });
});

describe("Snapshots sind schreibgeschützt", () => {
  it("bietet in einem Snapshot weder Vergleichsstart noch Entscheidungsformular", async () => {
    const snapshot = makeProject({
      project_id: "proj_1",
      status: "snapshot",
      version_label: "Stand 2026-08-20",
    });

    backend = installFakeBackend(
      baseRoutes([
        route("GET", "/projects/proj_1", () => snapshot),
        route("GET", "/projects/proj_1/pipeline-status", () =>
          makePipelineStatus({ project: snapshot }),
        ),
      ]),
    );

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1" });

    expect(await screen.findAllByText(/Snapshot/)).not.toHaveLength(0);
    expect(screen.queryByRole("button", { name: /Vergleich hinzufügen/ })).not.toBeInTheDocument();
  });

  it("zeigt statt des Mapping-Formulars einen Hinweis auf den Schreibschutz", async () => {
    const snapshot = makeProject({ project_id: "proj_1", status: "snapshot" });

    backend = installFakeBackend(
      baseRoutes([
        route("GET", "/projects/proj_1", () => snapshot),
        route("GET", "/projects/proj_1/pipeline-status", () =>
          makePipelineStatus({ project: snapshot }),
        ),
        route("GET", "/mappings/", () => [makeMapping({ mapping_confidence: 0.4 })]),
      ]),
    );

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/mappings" });

    expect(await screen.findByText(/In einem Snapshot ist es\s+schreibgeschützt/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Manuelle Entscheidung" })).not.toBeInTheDocument();
  });
});

describe("Fehlerbehandlung", () => {
  it("meldet ein nicht erreichbares Backend mit Wiederholen-Aktion", async () => {
    backend = installFakeBackend([]);
    // Kein Route-Treffer heisst hier 404; ein echter Verbindungsfehler wird
    // separat geprueft, indem fetch selbst wirft.
    backend.restore();
    backend = installFakeBackend([
      {
        method: "GET",
        match: () => true,
        respond: () => {
          throw new TypeError("Failed to fetch");
        },
      },
    ]);

    renderWithProviders(<AppRoutes />, { route: "/projects" });

    expect(await screen.findByText("Backend nicht erreichbar")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Erneut versuchen/ })).toBeInTheDocument();
  });
});

describe("Offene Paare in der Ergebnisliste", () => {
  /**
   * Der Kern des Ausbaus aus Sicht der Oberflaeche: offene Paare (RELATED
   * oder ohne LLM-Mehrheitsentscheid) wurden frueher gar nicht geliefert und
   * daher auch nicht angezeigt. Jetzt stehen sie in der Liste, als offen
   * gekennzeichnet und übersetzt beschriftet, und sind an Ort und Stelle
   * entscheidbar.
   */
  const openMapping = makeOpenMapping({
    mapping_id: "map_open_1",
    subject_label: "Kryptografie anwenden",
    object_label: "Datensicherheit",
  });

  function mappingRoutes(extra: FakeRoute[] = []): FakeRoute[] {
    return baseRoutes([route("GET", "/mappings/", () => [openMapping]), ...extra]);
  }

  it("zeigt ein Paar ohne Mehrheitsentscheid übersetzt und mit dem Hinweis auf die offene Entscheidung", async () => {
    backend = installFakeBackend(mappingRoutes());

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/mappings" });

    expect(await screen.findByText("Kryptografie anwenden")).toBeInTheDocument();
    expect(
      screen.getByText(/Kein Konsens · wartet auf manuelle Entscheidung/),
    ).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Offene Entscheidung" })).toBeInTheDocument();
  });

  it("weist die Herkunft als mapping_justification aus", async () => {
    backend = installFakeBackend(
      baseRoutes([
        route("GET", "/mappings/", () => [
          makeMapping({ mapping_justification: "semapv:StructuralMatching" }),
        ]),
      ]),
    );

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/mappings" });

    // Die Liste nennt die Herkunft ausgeschrieben, die Detailspalte
    // zusaetzlich die SEMAPV-CURIE. Beides ersetzt die frueher gezeigte
    // match_type-Bezeichnung.
    const list = await screen.findByRole("region", { name: "Mapping-Liste" });
    expect(await within(list).findByText("Struktureller Shortcut")).toBeInTheDocument();

    const details = screen.getByRole("region", { name: "Mapping-Details" });
    expect(await within(details).findByText("semapv:StructuralMatching")).toBeInTheDocument();
    expect(within(details).queryByText(/^llm$/)).not.toBeInTheDocument();
  });

  it("sendet den Konjunkt-Zweig mit dem gewählten Prädikat", async () => {
    const user = userEvent.setup();
    backend = installFakeBackend(
      mappingRoutes([
        routeStartsWith("PUT", "/mappings/", () => ({
          ...openMapping,
          review_status: "conjunct",
          predicate_id: "skos:broadMatch",
          mapping_justification: "semapv:MappingReview",
        })),
      ]),
    );

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/mappings" });

    await screen.findByRole("heading", { name: "Offene Entscheidung" });
    await user.selectOptions(screen.getByLabelText(/^Prädikat/), "skos:broadMatch");
    await user.type(screen.getByLabelText(/^Autor/), "AO");
    await user.click(screen.getByRole("button", { name: "Entscheidung speichern" }));

    await waitFor(() => {
      const call = backend!.calls.find(
        (candidate) => candidate.method === "PUT" && candidate.url.pathname.endsWith("/review"),
      );
      expect(call).toBeDefined();
      expect(call!.body).toMatchObject({
        decision: "conjunct",
        predicate: "skos:broadMatch",
        confidence: 1,
        author: "AO",
      });
      expect(call!.url.pathname).toContain("map_open_1");
    });
  });

  it("sendet den Disjunkt-Zweig mit der gewählten Strategie", async () => {
    const user = userEvent.setup();
    backend = installFakeBackend(
      mappingRoutes([
        routeStartsWith("PUT", "/mappings/", () => ({
          ...openMapping,
          review_status: "disjunct",
          mapping_justification: "semapv:MappingReview",
        })),
      ]),
    );

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/mappings" });

    await screen.findByRole("heading", { name: "Offene Entscheidung" });
    await user.click(screen.getByRole("button", { name: /Disjunkt: kein Mapping/ }));
    await user.selectOptions(screen.getByLabelText(/^Strategie/), "out_of_scope");
    await user.type(screen.getByLabelText(/^Autor/), "AO");
    await user.click(screen.getByRole("button", { name: "Entscheidung speichern" }));

    await waitFor(() => {
      const call = backend!.calls.find(
        (candidate) => candidate.method === "PUT" && candidate.url.pathname.endsWith("/review"),
      );
      expect(call).toBeDefined();
      expect(call!.body).toMatchObject({
        decision: "disjunct",
        strategy: "out_of_scope",
        author: "AO",
      });
    });
  });

  it("verlangt bei map_to_nearest einen Kontextverlust-Vermerk", async () => {
    const user = userEvent.setup();
    backend = installFakeBackend(mappingRoutes());

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/mappings" });

    await screen.findByRole("heading", { name: "Offene Entscheidung" });
    await user.click(screen.getByRole("button", { name: /Disjunkt: kein Mapping/ }));
    await user.selectOptions(screen.getByLabelText(/^Strategie/), "map_to_nearest");
    await user.type(screen.getByLabelText(/^Autor/), "AO");
    await user.click(screen.getByRole("button", { name: "Entscheidung speichern" }));

    expect(await screen.findByText(/ist ein Vermerk zum Kontextverlust erforderlich/)).toBeInTheDocument();
    expect(backend!.calls.some((call) => call.method === "PUT")).toBe(false);
  });

  it("sendet den Kontextverlust-Vermerk mit, sobald er ausgefüllt ist", async () => {
    const user = userEvent.setup();
    backend = installFakeBackend(
      mappingRoutes([routeStartsWith("PUT", "/mappings/", () => openMapping)]),
    );

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/mappings" });

    await screen.findByRole("heading", { name: "Offene Entscheidung" });
    await user.click(screen.getByRole("button", { name: /Disjunkt: kein Mapping/ }));
    await user.selectOptions(screen.getByLabelText(/^Strategie/), "map_to_nearest");
    await user.type(screen.getByLabelText(/^Vermerk zum Kontextverlust/), "Niveaubezug entfällt.");
    await user.type(screen.getByLabelText(/^Autor/), "AO");
    await user.click(screen.getByRole("button", { name: "Entscheidung speichern" }));

    await waitFor(() => {
      const call = backend!.calls.find(
        (candidate) => candidate.method === "PUT" && candidate.url.pathname.endsWith("/review"),
      );
      expect(call!.body).toMatchObject({
        decision: "disjunct",
        strategy: "map_to_nearest",
        context_loss_note: "Niveaubezug entfällt.",
      });
    });
  });

  it("bietet in einem Snapshot kein Entscheidungsformular an", async () => {
    backend = installFakeBackend(
      mappingRoutes([route("GET", "/projects/proj_1", () => makeProject({ status: "snapshot" }))]),
    );

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/mappings" });

    expect(await screen.findByText(/wartet auf manuelle Entscheidung/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Offene Entscheidung" })).not.toBeInTheDocument();
  });
});

describe("Coverage-Quote im Export", () => {
  /** Ein Nenner ohne die offenen Paare meldete hier 100 % statt 70 %. */
  const partialCoverage = route("GET", "/export/summary", () => ({
    no_consensus_pairs: 1,
    related_pairs: 2,
    low_confidence_mappings: 0,
    total_open: 3,
    disjoint_open: 0,
    coverage_resolved: 7,
    coverage_total: 10,
    coverage_ratio: 0.7,
    open_review_count: 3,
  }));

  it("weist offene Paare im Nenner aus, statt sie herauszurechnen", async () => {
    backend = installFakeBackend(baseRoutes([partialCoverage]));

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/export" });

    expect(await screen.findByText(/7 von 10 Paaren entschieden/)).toBeInTheDocument();
    expect(screen.getByText(/Der Nenner enthält auch die 3 noch offenen Paare/)).toBeInTheDocument();
  });

  it("verlinkt die offenen Paare in die gefilterte Mapping-Ansicht", async () => {
    backend = installFakeBackend(baseRoutes([partialCoverage]));

    renderWithProviders(<AppRoutes />, { route: "/projects/proj_1/export" });

    const link = await screen.findByRole("link", { name: "Offene Paare entscheiden" });
    expect(link).toHaveAttribute("href", "/projects/proj_1/mappings?status=open");
  });
});
