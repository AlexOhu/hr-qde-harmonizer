# HR-QDE Harmonizer — React-Oberfläche

Bedienoberfläche für den Prototyp zur Harmonisierung von Kompetenz-,
Qualifikations- und Berufsrahmenwerken. Die Anwendung ist eine Single-Page-App
und spricht ausschließlich die bestehende FastAPI-REST-Schnittstelle des
Projekts an. Sie ist die einzige Bedienoberfläche des Prototyps.

---

## 1. Voraussetzungen

- Node.js 20.19+ oder 22.12+ (entwickelt und getestet mit Node 24)
- Das FastAPI-Backend dieses Repositorys, lauffähig auf Port 8000

---

## 2. Installation

```bash
cd frontend
npm install
```

---

## 3. Backend und Frontend gemeinsam starten

Beide Prozesse laufen parallel in je einem eigenen Terminal.

**Terminal 1 — Backend (Repository-Wurzel):**

```bash
.venv\Scripts\activate
uvicorn app.api.main:app --reload
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Die Oberfläche läuft anschließend auf <http://localhost:5173>, das Backend auf
<http://localhost:8000>.

Neo4j ist optional (ADR-5). Ist es nicht erreichbar, wird das im Dialog
„Vergleich starten“ als Hinweis angezeigt, blockiert den Lauf aber nicht.

---

## 4. API-Basis-URL

Die Adresse des Backends steht in `VITE_API_BASE_URL`. Ohne gesetzte Variable
greift der Standard `http://localhost:8000`.

```bash
cp .env.example .env.local   # und bei Bedarf anpassen
```

`.env.local` ist nicht eingecheckt. Für einen abweichenden Port genügt:

```
VITE_API_BASE_URL=http://localhost:8001
```

### CORS

Der Vite-Dev-Server ist ein eigener Origin. Das Backend erlaubt ihn über die
`CORSMiddleware` in `app/api/main.py`; die zugelassenen Origins stehen in
`CORS_ALLOW_ORIGINS` (`.env` des Backends, kommagetrennt) und decken
standardmäßig `http://localhost:5173` ab. Läuft das Frontend auf einem anderen
Port, muss dieser Origin dort ergänzt werden.

---

## 5. Build und Tests

```bash
npm run build        # Typprüfung (tsc -b) und Produktions-Build nach dist/
npm run typecheck    # nur Typprüfung
npm run test         # Vitest, einmaliger Lauf
npm run test:watch   # Vitest im Watch-Modus
npm run lint         # oxlint
npm run preview      # gebautes dist/ lokal ausliefern
```

Die Tests laufen ohne Backend: `src/test/utils.tsx` ersetzt `fetch` durch eine
Routentabelle. Geprüft werden die kritischen Nutzerpfade — Projekt öffnen,
Framework hochladen und einbetten, Klassifikation starten, laufenden Job
anzeigen, Mapping manuell entscheiden, Integrationsentscheidung speichern,
Export-Readiness — jeweils gegen den echten Routenbaum, samt der tatsächlich
abgesetzten Requests.

---

## 6. Aufbau der Oberfläche

Die Navigation folgt den fachlichen Arbeitsobjekten, nicht den technischen
Funktionsgruppen der Vorgängeroberfläche.

```
Project
 ├── Frameworks          global, projektübergreifend
 ├── FrameworkPair       zentrale Arbeitseinheit
 │    ├── ClassificationRun
 │    ├── Mapping
 │    └── IntegrationDecision
 ├── Cluster
 ├── Export
 └── Snapshot
```

Global gibt es zwei Ziele (Projekte, Framework-Bibliothek). Ist ein Projekt
geöffnet, kommen vier Bereiche hinzu: Übersicht, Mappings, Integration, Export.
Klassifikation, SSSOM-Vorschau und Projekt-Status sind bewusst keine eigenen
Seiten — die Klassifikation ist eine Aktion auf der Projektübersicht, die
SSSOM-Vorschau Teil des Exports, der Projektstatus die Übersicht selbst.

### Routen

```
/projects
/projects/:projectId
/projects/:projectId/mappings
/projects/:projectId/integration
/projects/:projectId/export
/projects/:projectId/pairs/:frameworkAId/:frameworkBId
/projects/:projectId/pairs/:frameworkAId/:frameworkBId/mappings
/projects/:projectId/pairs/:frameworkAId/:frameworkBId/unmapped
/projects/:projectId/pairs/:frameworkAId/:frameworkBId/runs
/frameworks
```

Der Arbeitskontext steht vollständig in der URL: Projekt, Framework-Paar und
Bereich im Pfad, Filter und ausgewählter Datensatz in den Suchparametern
(`?status=review&q=…&selected=…`). Deep-Links, Vor/Zurück und mehrere Tabs
funktionieren dadurch ohne globalen Anwendungszustand.

---

## 7. Projektstruktur

```
src/
  api/            Typisierter API-Layer; einzige Stelle mit fetch-Aufrufen
    client.ts       HTTP-Client: Fehler, Timeouts, Downloads
    types.ts        TypeScript-Spiegel der Pydantic-Schemas
    queryKeys.ts    Hierarchische Query-Keys für gezielte Invalidierung
    projects.ts frameworks.ts classification.ts mappings.ts disjoint.ts exports.ts

  app/
    providers.tsx   QueryClient, Tooltip- und Toast-Provider
    router.tsx      Routenbaum

  components/
    layout/         AppShell, Sidebar, Backend-Status
    common/         MasterDetail, Lade-/Fehler-/Leerzustände
    ui/             Basiskomponenten (Radix + Tailwind)

  features/
    projects/       Projektkontext (ProjectLayout) und Projektdialoge
    frameworks/     Framework-Status und Upload-Dialog
    pairs/          Paar-Ableitung, Pair-Workspace, Vergleichsdialog
    mappings/       Mapping-Review (Master-Detail)
    integration/    Nicht zugeordnete Konzepte (Master-Detail)
    export/         Readiness und SSSOM-Vorschau

  hooks/          Query- und Mutation-Hooks je Domäne
  lib/            Formatierung und Hilfsfunktionen
  pages/          Seiten, setzen die Features zusammen
  test/           Testhilfen und Integrationstests
```

Zustandsführung: Serverzustand über TanStack Query, URL-Zustand über React
Router, lokaler UI-Zustand über React State. Eine globale State-Library gibt es
nicht.

Aktualisierung laufender Jobs: TanStack Query pollt, solange mindestens ein Job
`running` ist (`usePipelineStatus`, `useClassificationJobs`). Ein späterer
Wechsel auf SSE oder WebSockets berührt nur diese beiden Hooks — die
Komponenten lesen ausschließlich das Query-Ergebnis.

---

## 8. Bekannte Einschränkungen der API

Die Oberfläche macht Backend-Regeln sichtbar, definiert sie aber nicht neu. Wo
die gewünschte Darstellung und die vorhandene API auseinandergehen, ist das
hier festgehalten statt im Frontend nachgebaut zu werden.

| Thema | Sachverhalt | Umgang in der UI |
|---|---|---|
| **Paare vs. Jobs** | `GET /projects/{id}/pipeline-status` liefert einen `kqr_pairs`-Eintrag **pro Job**, nicht pro Paar. Ein Paar mit mehreren Läufen erscheint mehrfach; die Metriken sind über die Duplikate identisch. | `features/pairs/status.ts` fasst sie zu einem Paar zusammen und wählt den maßgeblichen Lauf. |
| **~~Offene Paare nicht abrufbar~~ (geschlossen)** | Seit v0.2 (ADR-16) persistiert die Pipeline jedes offene Paar (RELATED oder ohne LLM-Mehrheitsentscheid) als `Mapping` mit stabiler `mapping_id` und `review_status: "open"`; ohne Mehrheitsentscheid ist `predicate_id` `null`. `GET /mappings/` liefert sie mit, `PUT /mappings/{id}/review` entscheidet sie. | Die Ergebnisliste kennzeichnet sie als „wartet auf manuelle Entscheidung“ (übersetzte Relation bzw. „Kein Konsens“) und öffnet die Konjunkt/Disjunkt-Weiche. Sie stecken bereits in `pending_review_count`, werden also nicht mehr getrennt addiert. |
| **Zwei Zahlen für Paare ohne Mehrheitsentscheid** | `GET /export/summary` zählt projektweit über alle Mappings (`no_consensus_pairs`); die paarbezogenen `unresolved_count` liegen niedriger, weil sie nur Fälle mit auflösbarer Framework-Zuordnung erfassen. | Die Export-Readiness verwendet die projektweite Zahl aus `/export/summary`, weil genau sie im Prüfbericht landet. |
| **Coverage nur projektweit** | `GET /export/summary` liefert `coverage_resolved`, `coverage_total`, `coverage_ratio` und `open_review_count` ausschließlich für das gesamte Projekt, nicht je Framework-Paar. | Die Quote steht in der Export-Readiness. Paarbezogen zeigt die Oberfläche weiterhin nur die Zähler aus dem Pipelinestatus, statt eine Quote selbst zu berechnen. |
| **Keine Suche/Paginierung** | `GET /mappings/` und `GET /disjoint/concepts` kennen weder Volltextsuche noch Sortierung oder Paginierung. | Serverseitig wird auf das Paar eingegrenzt, Freitextsuche und Feinfilter laufen clientseitig auf der geladenen Menge. |
| **Validierungsfehler flüchtig** | `kqr_service._validation_errors` liegt nur im Prozessspeicher. Nach einem API-Neustart ist die Liste leer, der Status bleibt `roh`. | Die Bibliothek zeigt den Status weiter an und weist darauf hin, dass Fehlerdetails nur bis zum Neustart vorliegen. |
| **Clustering synchron** | `POST /export/clusters/run` läuft im Request durch, es gibt keinen Hintergrundjob wie bei der Klassifikation. | Großzügiges Timeout; nur diese Mutation zeigt einen Ladezustand, die übrige Oberfläche bleibt bedienbar. |

### Am Backend vorgenommene Änderungen

Drei kleine, rückwärtskompatible Ergänzungen waren nötig:

1. **CORS** (`app/api/main.py`, `app/config.py`): `CORSMiddleware` mit
   `CORS_ALLOW_ORIGINS`. Ohne sie blockt der Browser jede Antwort.
   `Content-Disposition` wird exponiert, damit Downloads ihren Dateinamen
   behalten.
2. **Job-Zeitstempel** (`app/services/classification_service.py`):
   `started_at` und `finished_at` je Job, damit die Laufhistorie eines Paares
   sortier- und lesbar ist. Ältere Jobs ohne diese Felder liefern `null`.
3. **Schreibschutz-Statuscode** (`app/api/routes/disjoint.py`): Der Versuch,
   in einem Snapshot zu entscheiden, quittierte mit HTTP 500. Jetzt 409, analog
   zu `classification/start`.

Bestehendes Verhalten wurde nicht verändert; die 95 Backend-Tests laufen
unverändert durch.

---

## 9. Begriffe

In der Oberfläche heißt es durchgehend **Framework** bzw.
**Rahmenwerk** und **nicht zugeordnete Konzepte**; die Backend-Bezeichnungen
`kqr` und „disjunkte Menge D“ bleiben technisch bestehen und werden in
Tooltips erläutert.
