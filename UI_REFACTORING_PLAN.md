# UI-Refactoring-Plan: Projektverwaltung, Dashboard und Projekt-Status-Seite

> Operativer Arbeitsplan für Claude Code.
> Implementierungsreihenfolge strikt einhalten — spätere Tasks setzen frühere voraus.
> Abgeschlossene Tasks mit `[x]` markieren.

---

## Ausgangslage und Problemanalyse

### Technischer Bug

Die Streamlit-Sortierlogik (`[0-9]*` als Regex) liest aus `3b_Integrationsstrategie.py`
den Sortierschlüssel `(3.0, "b_integrationsstrategie")` und aus `3_Ergebnisliste.py`
den Schlüssel `(3.0, "ergebnisliste")`. Da `"b_..."` alphabetisch vor `"ergebnisliste"`
kommt, erscheint Integrationsstrategie vor Ergebnisliste — obwohl das die falsche Reihenfolge ist.

### UCSD-Probleme der aktuellen UI

| UCSD-Prinzip | Aktuelles Problem |
|---|---|
| Visibility of System State | Kein Überblick: Nutzer sieht nicht, in welchem Schritt die Pipeline steckt |
| Recognition over Recall | Nutzer muss sich erinnern, was er zuletzt getan hat |
| User Control & Freedom | Kein Versionieren: ein Fehlschritt überschreibt Ergebnisse unwiderruflich |
| Match System / Real World | "3b_Integrationsstrategie" entspricht nicht dem mentalen Modell |
| Flexibility | Kein Neustart oder parallele Varianten möglich |

### Ziele des Refactorings

1. **Projektverwaltung**: Voneinander unabhängige, versionierbare Projekte.
   Jedes Projekt kapselt KQR-Auswahl, Klassifikationsjobs, Mappings,
   Disjoint-Entscheidungen und Clustering-Ergebnisse.
2. **Dashboard**: Startseite mit KQR-Bibliothek-Übersicht und Projektliste.
3. **Projekt-Status-Seite**: Pro Projekt eine Seite mit Pipeline-Fortschritt
   und direkten Navigationslinks zu den Aktionsseiten.


---

## Architektur-Entscheidungen (ADR)

| # | Entscheidung | Begründung | Verworfene Alternative |
|---|---|---|---|
| ADR-01 | KQR-Daten bleiben global | KQRs (Registry + TTL + Embeddings) sind projektübergreifend verwendbar; eine Kopie pro Projekt wäre redundant | Pro-Projekt-KQR-Kopien |
| ADR-02 | Projektdaten in `data/projects/{project_id}/` | Klare Trennung, einfaches Löschen/Archivieren eines Projekts als Verzeichnis | Alle Daten in Wurzel mit project_id-Spalte |
| ADR-03 | `project_id` als Query-Parameter in bestehenden API-Routen | Bestehende Routes bleiben funktionsfähig; kein Breaking Change; default `"default"` entspricht dem bisherigen globalen Datenpfad | Eigene Unterrouten `/projects/{id}/mappings/` |
| ADR-04 | In-Memory-Caches in Services nach `project_id` kodieren | Verhindert Datenvermischung zwischen Projekten im selben Prozess ohne vollständige Neuinitialisierung | Singleton-Cache ohne Projekt-Kontext |
| ADR-05 | `st.session_state["active_project_id"]` als UI-Kontext | Streamlit-konform; kein zusätzlicher Server-Zustand notwendig | Server-seitige "active project"-Variable (Concurrency-Problem) |
| ADR-06 | Snapshot = neues Projekt mit `status="snapshot"` und `parent_project_id` | Einfache Implementierung; Snapshots erscheinen als separate Einträge in der Projektliste und können nachträglich weiterbearbeitet werden | Versionssuffix am selben Projekt |
| ADR-07 | Neue Seitennummern 1–8, keine Buchstaben-Suffixe | Behebt den Sortierungsbug dauerhaft; klare, vorhersagbare Reihenfolge | Alphabetische Sortierung ohne Nummern |


---

## Phase 0 — Sofort-Fix: Sortierungsbug (kein Backend-Aufwand)

### Task 0.1 — Dateien umbenennen

```
ui/pages/1_KQR_Auswahl.py          → ui/pages/3_Rahmenwerke.py
ui/pages/2_Klassifikation.py        → ui/pages/4_Klassifikation.py
ui/pages/3_Ergebnisliste.py         → ui/pages/5_Konjunkte_Konzepte.py
ui/pages/3b_Integrationsstrategie.py → ui/pages/6_Disjunkte_Konzepte.py
ui/pages/4_SSSOM_Vorschau.py        → ui/pages/7_SSSOM_Vorschau.py
ui/pages/5_Export.py                → ui/pages/8_Export.py
```

Die Seiten 1 und 2 werden neu erstellt (Projektverwaltung, Projekt-Status).

### Task 0.2 — Seitenheader in jeder umbenannten Datei anpassen

In jeder umbenannten Datei den `st.header()`-Aufruf aktualisieren:

| Datei (neu) | Neuer Header |
|---|---|
| `3_Rahmenwerke.py` | `st.header("Rahmenwerke (KQR-Bibliothek)")` |
| `4_Klassifikation.py` | `st.header("Mapping-Pipeline")` |
| `5_Konjunkte_Konzepte.py` | `st.header("Konjunkte Konzepte (K)")` |
| `6_Disjunkte_Konzepte.py` | `st.header("Disjunkte Konzepte (D)")` |
| `7_SSSOM_Vorschau.py` | keine Änderung |
| `8_Export.py` | keine Änderung |

### Task 0.3 — app.py: Navigationsliste aktualisieren

Den Markdown-Block in `ui/app.py` (Zeilen 19–30) auf die neue Reihenfolge anpassen:

```
1. Projekte — Projekte erstellen, auswählen, als Snapshot sichern
2. Projekt-Status — Pipeline-Fortschritt und offene Aktionen des aktiven Projekts
3. Rahmenwerke — KQR einpflegen, Embedding-Status prüfen
4. Mapping-Pipeline — Klassifikationsjob starten, Fortschritt verfolgen
5. Konjunkte Konzepte (K) — Mappings sichten, filtern, manuell entscheiden
6. Disjunkte Konzepte (D) — Integrationsstrategie für nicht gemappte Konzepte
7. SSSOM-Vorschau — Exportstruktur prüfen
8. Export — OWL / SSSOM-TSV / Prüfbericht herunterladen
```


---

## Phase 1 — Backend: Projektmodell

### Task 1.1 — `schemas.py` erweitern

Am Ende der Datei `app/models/schemas.py` einfügen:

```python
class ProjectStatus(str, Enum):
    """Zustand eines Projekts."""
    ACTIVE = "active"       # aktiv bearbeitbar
    SNAPSHOT = "snapshot"   # eingefroren (read-only), durch Snapshot erstellt

class Project(BaseModel):
    """Ein Harmonisierungsprojekt kapselt KQR-Auswahl und alle daraus
    resultierenden Artefakte (Mappings, Entscheidungen, Clustering)."""
    project_id: str
    name: str
    description: str | None = None
    kqr_ids: list[str]                  # KQR-IDs aus dem globalen Registry
    hub_kqr_id: str | None = None       # welcher KQR ist der Hub in diesem Projekt
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: ProjectStatus = ProjectStatus.ACTIVE
    parent_project_id: str | None = None   # bei Snapshots/Forks
    version_label: str | None = None        # z.B. "v0.3", "Snapshot 2026-07-30"

class KQRPairStatus(BaseModel):
    """Pipeline-Status für ein einzelnes KQR-Paar innerhalb eines Projekts."""
    kqr_a_id: str
    kqr_a_name: str
    kqr_b_id: str
    kqr_b_name: str
    job_status: str | None = None       # null | running | completed | failed | interrupted
    job_id: str | None = None
    total_pairs: int = 0
    classified_pairs: int = 0
    mappings_count: int = 0
    pending_review_count: int = 0       # confidence < threshold oder UNRESOLVED
    unresolved_count: int = 0

class ProjectPipelineStatus(BaseModel):
    """Vollständiger Pipeline-Status eines Projekts für die Projekt-Status-Seite."""
    project: Project
    kqr_pairs: list[KQRPairStatus]
    disjoint_total: int = 0
    disjoint_decided: int = 0
    disjoint_open: int = 0
    clustering_done: bool = False
    export_ready: bool = False          # True wenn alle offenen Einträge = 0
```


### Task 1.2 — `project_service.py` erstellen

**Datei:** `app/services/project_service.py` (neu)

```python
"""
Verwaltet Projekte als eigenständige Datencontainer.

Persistenz-Design:
- Projektmetadaten in data/projects/{project_id}/project.json
- Projektspezifische Laufzeitdaten im selben Verzeichnis:
    classification_jobs.json, mappings.json, disjoint_decisions.json,
    clusters.json, clusters_dag.json, sssom/, ontology/
- Globale KQR-Daten (kqr_registry.json, formalized/, raw/, Embeddings)
  bleiben unverändert unter data/ — sie werden zwischen Projekten geteilt.

Namenskonvention: project_id ist ein slugifizierter Name + Zeitstempel-Suffix,
z.B. "esco_ecf_dqr_20260730T142233Z".
"""
from pathlib import Path
from datetime import datetime
from app.models.schemas import Project, ProjectStatus, ProjectPipelineStatus

PROJECTS_DIR = DATA_DIR / "projects"

def create_project(name: str, kqr_ids: list[str], description: str | None = None,
                   hub_kqr_id: str | None = None) -> Project:
    """Erstellt ein neues Projekt und legt das Verzeichnis an."""

def list_projects() -> list[Project]:
    """Alle Projekte, absteigend nach updated_at sortiert."""

def get_project(project_id: str) -> Project:
    """KeyError wenn nicht gefunden."""

def update_project(project_id: str, name: str | None = None,
                   description: str | None = None) -> Project:
    """Aktualisiert Name/Beschreibung; updated_at wird gesetzt."""

def create_snapshot(project_id: str, version_label: str) -> Project:
    """
    Kopiert alle projektspezifischen Datendateien in ein neues Projekt-
    verzeichnis (shutil.copytree). Das neue Projekt erhält status=SNAPSHOT
    und parent_project_id=project_id. Das Original bleibt unverändert.
    Artefakte unter sssom/ und ontology/ werden mitgopiert.
    """

def fork_project(project_id: str, new_name: str,
                 new_kqr_ids: list[str]) -> Project:
    """
    Erstellt ein neues ACTIVE-Projekt mit anderem KQR-Set.
    Keine Daten werden übernommen — leerer Start mit anderen KQRs.
    parent_project_id zeigt auf die Quelle (Dokumentation der Herkunft).
    """

def delete_project(project_id: str) -> None:
    """Löscht Projektverzeichnis und Metadaten. SNAPSHOT-Status ändert sich nicht."""

def get_project_data_dir(project_id: str) -> Path:
    """Gibt data/projects/{project_id}/ zurück. Hilfsfunktion für andere Services."""

def get_pipeline_status(project_id: str) -> ProjectPipelineStatus:
    """
    Aggregiert KQRPairStatus für alle KQR-Paare, die im Projekt klassifiziert
    wurden (aus classification_jobs.json des Projekts), plus Disjoint-Zusammenfassung
    und Clustering-Status.
    Ruft mapping_service und disjoint_service mit project_id auf.
    """
```


### Task 1.3 — Bestehende Services um `project_id` erweitern

Alle vier datenführenden Services erhalten `project_id: str = "default"` als Parameter.
Der Datenpfad wird dynamisch aus `project_service.get_project_data_dir(project_id)`
abgeleitet statt hartcodiert. In-Memory-Caches werden von

```python
_mappings: list[Mapping] = []
```
auf
```python
_mappings: dict[str, list[Mapping]] = {}   # key: project_id
```
umgestellt. Alle bestehenden Funktionen delegieren auf die neue projektspezifische
interne Implementierung.

**Betroffene Dateien:**

- `app/services/mapping_service.py`:
  Alle Funktionen (add_mappings, list_mappings, get_classified_pairs,
  update_mapping, export_summary) erhalten `project_id: str = "default"`.
  `MAPPINGS_PATH` wird zur lokalen Variable `_path(project_id)`.

- `app/services/classification_service.py`:
  `start_classification_job`, `list_jobs`, `get_job_progress`, `pause_job`,
  `resume_job` erhalten `project_id: str = "default"`.
  `JOBS_PATH` wird zur Funktion `_jobs_path(project_id)`.
  `_jobs: dict[str, dict]` wird zu `_jobs: dict[str, dict[str, dict]]`
  (äußerer Key: project_id).

- `app/services/disjoint_service.py`:
  Alle Funktionen erhalten `project_id: str = "default"`.
  `DISJOINT_PATH` wird zu `_path(project_id)`.

- `app/services/ontology_service.py`:
  `run_clustering`, `get_cluster_results`, `get_harmonised_clusters`
  erhalten `project_id: str = "default"`.
  `CLUSTERS_PATH` wird zu `_path(project_id)`.

**Migrationskompatibilität:**
Beim Start des Servers, falls `data/projects/` nicht existiert aber
`data/mappings.json` vorhanden ist, legt `project_service` automatisch
ein Projekt `"default"` an und verschiebt die bestehenden Datendateien
in `data/projects/default/`. So bleibt der bisherige Stand erhalten.


---

## Phase 2 — Backend: API-Routen

### Task 2.1 — Neue Router-Datei `app/api/routes/projects.py`

```
GET  /projects/
     → project_service.list_projects()
     Rückgabe: list[Project], absteigend nach updated_at

POST /projects/
     Body: {name, kqr_ids, description?, hub_kqr_id?}
     → project_service.create_project(...)
     Rückgabe: Project (HTTP 201)

GET  /projects/{project_id}
     → project_service.get_project(project_id)
     HTTP 404 wenn nicht gefunden

PUT  /projects/{project_id}
     Body: {name?, description?}
     → project_service.update_project(...)

GET  /projects/{project_id}/pipeline-status
     → project_service.get_pipeline_status(project_id)
     Rückgabe: ProjectPipelineStatus

POST /projects/{project_id}/snapshot
     Body: {version_label}
     → project_service.create_snapshot(project_id, version_label)
     Rückgabe: das neue Snapshot-Projekt

POST /projects/{project_id}/fork
     Body: {new_name, new_kqr_ids}
     → project_service.fork_project(...)
     Rückgabe: das neue Projekt

DELETE /projects/{project_id}
     → project_service.delete_project(project_id)
     HTTP 409 wenn es sich um das letzte ACTIVE-Projekt handelt
```

### Task 2.2 — `project_id` Query-Parameter in bestehenden Routen ergänzen

Alle bestehenden API-Routen, die auf projektspezifische Daten zugreifen,
erhalten `project_id: str = Query(default="default")` als FastAPI-Parameter.
Der Wert wird an den jeweiligen Service weitergegeben.

Betroffene Router:
- `app/api/routes/classification.py` — alle Endpunkte
- `app/api/routes/mappings.py` — alle Endpunkte
- `app/api/routes/disjoint.py` — alle Endpunkte
- `app/api/routes/export.py` — alle Endpunkte

### Task 2.3 — `app/api/main.py` erweitern

```python
from app.api.routes import projects
app.include_router(projects.router, prefix="/projects", tags=["Projektverwaltung"])
```


---

## Phase 3 — UI: api_client.py Erweiterungen

**Datei:** `ui/api_client.py`

### Task 3.1 — Projekt-Kontext-Header

Alle bestehenden Request-Funktionen erhalten den `project_id`-Parameter
als optionales Keyword-Argument und übergeben ihn als Query-Parameter:

```python
def _request(method: str, path: str, project_id: str | None = None, **kwargs):
    params = kwargs.pop("params", {})
    if project_id is not None:
        params["project_id"] = project_id
    # ... bestehende Implementierung
```

Alle öffentlichen Funktionen (list_mappings, start_classification, etc.)
erhalten `project_id: str | None = None` als Parameter, der an `_request`
weitergegeben wird.

### Task 3.2 — Neue Projekt-API-Funktionen

```python
def list_projects() -> list[dict]: ...
def create_project(name: str, kqr_ids: list[str], description: str | None = None,
                   hub_kqr_id: str | None = None) -> dict: ...
def get_project(project_id: str) -> dict: ...
def update_project(project_id: str, name: str | None = None,
                   description: str | None = None) -> dict: ...
def get_pipeline_status(project_id: str) -> dict: ...
def create_snapshot(project_id: str, version_label: str) -> dict: ...
def fork_project(project_id: str, new_name: str, new_kqr_ids: list[str]) -> dict: ...
def delete_project(project_id: str) -> None: ...
```

### Task 3.3 — Session-State-Hilfsfunktion

```python
# ui/session.py (neue Hilfsdatei, von allen Pages importiert)
import streamlit as st

def get_active_project_id() -> str | None:
    return st.session_state.get("active_project_id")

def set_active_project(project_id: str, project_name: str) -> None:
    st.session_state["active_project_id"] = project_id
    st.session_state["active_project_name"] = project_name

def require_active_project() -> str:
    """
    Gibt project_id zurück oder zeigt Fehler + Link zur Projektseite.
    Wird am Anfang jeder project-spezifischen Page aufgerufen.
    """
    pid = get_active_project_id()
    if pid is None:
        st.warning("Kein Projekt ausgewählt. Bitte zuerst ein Projekt öffnen.")
        st.page_link("pages/1_Projekte.py", label="→ Zur Projektübersicht")
        st.stop()
    return pid

def render_active_project_badge() -> None:
    """Zeigt den Projektnamen als Badge oben auf project-spezifischen Pages."""
    name = st.session_state.get("active_project_name", "Unbekannt")
    pid = st.session_state.get("active_project_id", "")
    st.caption(f"Aktives Projekt: **{name}** (`{pid}`)")
```


---

## Phase 4 — UI: Dashboard (app.py)

**Datei:** `ui/app.py` — vollständig ersetzen.

### Aufbau der neuen Startseite

```
st.set_page_config(page_title="HR-QDE Harmonizer", layout="wide")
st.title("HR-QDE Harmonizer")

# Backend-Status
[Backend-Erreichbarkeits-Check wie bisher]

# ── Spalte 1: KQR-Bibliothek ──────────────────────────────────────────────
# ── Spalte 2: Projekte ────────────────────────────────────────────────────
col_kqr, col_projects = st.columns([1, 2])
```

#### Spalte 1 — KQR-Bibliothek

```python
with col_kqr:
    st.subheader("Rahmenwerke (KQR)")
    kqr_list = list_kqr()
    for kqr in kqr_list:
        icon = {"bereit": "🟢", "formalisiert": "🟡", "roh": "🔴"}.get(kqr["status"], "⚪")
        hub = " *(Hub)*" if kqr.get("is_hub") else ""
        count = f"{kqr['concept_count']} Konzepte" if kqr.get("concept_count") else ""
        st.markdown(f"{icon} **{kqr['name']}{hub}** {count}")
    st.page_link("pages/3_Rahmenwerke.py", label="KQR verwalten →")
```

#### Spalte 2 — Projektliste mit aktivem Projekt

```python
with col_projects:
    st.subheader("Projekte")

    # Schnellerfassung
    with st.expander("+ Neues Projekt"):
        # Formular: Name, Beschreibung, KQR-Multiselect (nur Status=bereit),
        # Hub-KQR-Auswahl, Schaltfläche "Erstellen"
        # → create_project(...) → set_active_project(...) → st.rerun()

    projects = list_projects()
    if not projects:
        st.info("Noch kein Projekt vorhanden. Erstellen Sie oben ein neues Projekt.")
    else:
        for project in projects:
            is_active = (get_active_project_id() == project["project_id"])
            status_icon = "📸" if project["status"] == "snapshot" else "📂"
            border_color = "blue" if is_active else None  # st.container hat kein border_color — Workaround: border=True bei aktivem

            with st.container(border=True):
                col_info, col_actions = st.columns([3, 1])
                with col_info:
                    label = f"{status_icon} **{project['name']}**"
                    if project.get("version_label"):
                        label += f" *({project['version_label']})*"
                    if is_active:
                        label += " ← aktiv"
                    st.markdown(label)
                    kqr_names = ", ".join(project.get("kqr_ids", []))
                    st.caption(f"KQR: {kqr_names} · Erstellt: {project['created_at'][:10]}")
                    if project.get("description"):
                        st.caption(project["description"])
                with col_actions:
                    if st.button("Öffnen", key=f"open_{project['project_id']}"):
                        set_active_project(project["project_id"], project["name"])
                        st.switch_page("pages/2_Projekt_Status.py")
```

**UCSD-Begründung:**
- *Visibility of System State*: KQR-Status und Projektliste auf einem Blick.
- *Recognition over Recall*: Nutzer sieht alle Projekte mit KQR-Inhalt, muss sich
  nichts merken.
- *User Control*: Schnellerfassung im Expander reduziert Klicktiefe für
  den häufigen Fall "neues Projekt starten".


---

## Phase 5 — UI: Projektverwaltung (`ui/pages/1_Projekte.py`)

Diese Seite ergänzt das Dashboard um die vollständige Projektverwaltung.
Sie richtet sich an Nutzer, die mehr als nur "Öffnen" tun wollen.

### Aufbau

```
st.header("Projekte")

# ── Tab 1: Projektliste ───────────────────────────────────────────────────
# ── Tab 2: Neues Projekt / Fork ───────────────────────────────────────────
tab_list, tab_new = st.tabs(["Alle Projekte", "Neu / Fork"])
```

#### Tab 1 — Vollständige Projektliste

Pro Projekt eine Zeile in einer `st.dataframe`-Tabelle:

| Spalte | Inhalt |
|---|---|
| Name | project["name"] |
| KQR | kommaseparierte kqr_ids |
| Status | 📂 Aktiv / 📸 Snapshot |
| Version | version_label |
| Erstellt | created_at[:10] |

Unterhalb der Tabelle: Aktionen für das ausgewählte Projekt als Buttons:

```
[Öffnen]  [Snapshot erstellen]  [Fork / Ableiten]  [Umbenennen]  [Löschen]
```

- **Öffnen**: `set_active_project(...)` + `st.switch_page("pages/2_Projekt_Status.py")`
- **Snapshot erstellen**: Expander öffnet, Eingabe `version_label`, dann
  `create_snapshot(project_id, version_label)` → `st.success("Snapshot '{label}' erstellt.")`
- **Fork / Ableiten**: Expander mit neuem Namen + KQR-Multiselect →
  `fork_project(...)` → Weiterleitung zu neuem Projekt
- **Umbenennen**: Inline-Textfeld + `update_project(...)`
- **Löschen**: Bestätigungsdialog (`st.warning` + Checkbox "Ja, Projekt löschen")

#### Tab 2 — Neues Projekt

Vollständiges Formular:
```
Name (Pflicht), Beschreibung (optional),
KQR-Multiselect (nur Status "bereit"), Hub-KQR-Select,
[Erstellen]-Button → create_project(...) → Weiterleitung
```

**UCSD-Begründung:**
- *User Control & Freedom*: Snapshot-Mechanismus gibt Rückzugsmöglichkeit.
- *Error Prevention*: Lösch-Bestätigung verhindert versehentliches Löschen.
- *Consistency*: Alle Projektoperationen an einem Ort.


---

## Phase 6 — UI: Projekt-Status-Seite (`ui/pages/2_Projekt_Status.py`)

Dies ist die zentrale neue Seite. Sie dient als Cockpit für ein einzelnes Projekt:
Pipeline-Fortschritt und offene Aktionen auf einen Blick, mit direkten Links
in die jeweiligen Aktionsseiten.

### Aufbau

```python
from session import require_active_project, render_active_project_badge

render_active_project_badge()
project_id = require_active_project()

st.header("Projekt-Status")

status = get_pipeline_status(project_id)   # GET /projects/{id}/pipeline-status
```

#### Abschnitt 1 — Projektinfo und Aktionen

```
[Projekt: {name}]  [Status: Aktiv/Snapshot]  [KQR: esco, ecf, dqr]
                              [Snapshot erstellen]  [Fork / Ableiten]
```

Ein `st.info`-Banner wenn das Projekt den Status SNAPSHOT hat:
"Dieses Projekt ist ein Snapshot (eingefroren). Aktionen sind schreibgeschützt."

#### Abschnitt 2 — Pipeline-Übersicht (pro KQR-Paar)

Für jedes KQR-Paar in `status.kqr_pairs` eine Karte:

```python
for pair in status.kqr_pairs:
    with st.container(border=True):
        col_title, col_metrics, col_action = st.columns([2, 3, 1])

        with col_title:
            st.markdown(f"**{pair.kqr_a_name}** ↔ **{pair.kqr_b_name}**")
            # Fortschrittsbalken: classified_pairs / total_pairs
            if pair.total_pairs > 0:
                pct = pair.classified_pairs / pair.total_pairs
                st.progress(pct, text=f"Klassifikation: {pair.classified_pairs}/{pair.total_pairs}")
            else:
                st.caption("Noch keine Klassifikation gestartet.")

        with col_metrics:
            c1, c2, c3 = st.columns(3)
            c1.metric("Mappings", pair.mappings_count)
            c2.metric("Review offen", pair.pending_review_count,
                      delta=None if pair.pending_review_count == 0 else f"−{pair.pending_review_count}",
                      delta_color="inverse")
            c3.metric("UNRESOLVED", pair.unresolved_count,
                      delta_color="inverse")

        with col_action:
            job_status = pair.job_status
            if job_status is None:
                if st.button("Pipeline starten", key=f"start_{pair.kqr_a_id}_{pair.kqr_b_id}"):
                    # start_classification(pair.kqr_a_id, pair.kqr_b_id, project_id=project_id)
                    st.switch_page("pages/4_Klassifikation.py")
            elif job_status in ("running",):
                st.info("Läuft …")
                if st.button("Fortschritt", key=f"prog_{pair.kqr_a_id}"):
                    st.switch_page("pages/4_Klassifikation.py")
            elif job_status == "completed":
                if pair.pending_review_count > 0:
                    if st.button(f"Review ({pair.pending_review_count})",
                                 key=f"rev_{pair.kqr_a_id}", type="primary"):
                        st.switch_page("pages/5_Konjunkte_Konzepte.py")
                else:
                    st.success("✅ Vollständig")
```


#### Abschnitt 3 — Disjunkte Konzepte

```python
st.subheader("Disjunkte Konzepte (D)")
d = status  # ProjectPipelineStatus
col_d1, col_d2, col_d3 = st.columns(3)
col_d1.metric("Gesamt", d.disjoint_total)
col_d2.metric("Entschieden", d.disjoint_decided)
col_d3.metric("Offen", d.disjoint_open,
              delta_color="inverse" if d.disjoint_open > 0 else "off")
if d.disjoint_open > 0:
    if st.button(f"Integrationsstrategie festlegen ({d.disjoint_open} offen)",
                 type="primary"):
        st.switch_page("pages/6_Disjunkte_Konzepte.py")
else:
    st.success("✅ Alle disjunkten Konzepte entschieden.")
```

#### Abschnitt 4 — Clustering und Export

```python
st.subheader("Clustering & Export")
col_cl, col_ex = st.columns(2)

with col_cl:
    if status.clustering_done:
        st.success("✅ Clustering abgeschlossen (HDBSCAN)")
    else:
        st.warning("Clustering noch nicht ausgeführt.")
        if st.button("Clustering starten"):
            # run_clustering(status.project.kqr_ids, project_id=project_id)
            st.rerun()

with col_ex:
    if status.export_ready:
        st.success("✅ Bereit für Export")
        if st.button("Zur Export-Seite →"):
            st.switch_page("pages/8_Export.py")
    else:
        open_items = d.disjoint_open + sum(p.pending_review_count for p in status.kqr_pairs)
        st.warning(f"Export noch nicht bereit: {open_items} offene Einträge.")
        if st.button("Details im Export prüfen →"):
            st.switch_page("pages/8_Export.py")
```

**UCSD-Begründung:**
- *Visibility of System State*: Alle Pipeline-Schritte auf einem Blick mit
  konkreten Zahlen statt abstraktem Statustext.
- *Recognition over Recall*: Nutzer muss nicht wissen, welche Seite welche
  Funktion hat — die Aktions-Buttons navigieren direkt zum richtigen Ort.
- *Gulf of Evaluation*: Metric-Widgets zeigen sofort, ob Handlungsbedarf besteht.
- *Progressive Disclosure*: Pro KQR-Paar nur die jeweils relevante Aktion
  sichtbar (starten vs. Review vs. ✅).
- *Mixed Initiative*: System bewertet automatisch den Export-Bereit-Status;
  Nutzer trifft manuelle Entscheidungen nur wo nötig.


---

## Phase 7 — UI: Bestehende Pages anpassen

Alle projekt-spezifischen Pages (4–8) erhalten am Seitenanfang denselben Block:

```python
from session import require_active_project, render_active_project_badge
render_active_project_badge()
project_id = require_active_project()
```

Alle `api_client`-Aufrufe erhalten `project_id=project_id` als Argument.

### Task 7.1 — `4_Klassifikation.py` (war `2_Klassifikation.py`)

- `project_id` an `start_classification`, `list_classification_jobs`,
  `check_preconditions` übergeben.
- KQR-Selectboxen zeigen nur KQR aus `status.project.kqr_ids`, nicht alle
  global registrierten KQR. Das verhindert, dass versehentlich KQR aus dem
  falschen Projekt kombiniert werden.
  Implementierung: `kqr_list = [k for k in list_kqr() if k["id"] in project_kqr_ids]`
- Nach Klassifikationsabschluss: Button "Zur Projekt-Status-Seite →".

### Task 7.2 — `5_Konjunkte_Konzepte.py` (war `3_Ergebnisliste.py`)

- `project_id` an `list_mappings`, `update_mapping`, `get_mapping_config` übergeben.
- KQR-Filter-Selectbox zeigt nur die KQR des aktiven Projekts.
- Nach Speichern einer manuellen Entscheidung: kurze Zusammenfassung
  "X von Y Mappings noch ohne manuelle Entscheidung" (Visibility of System State).

### Task 7.3 — `6_Disjunkte_Konzepte.py` (war `3b_Integrationsstrategie.py`)

- `project_id` an alle `disjoint_*`-Funktionen übergeben.
- Keine weiteren inhaltlichen Änderungen.

### Task 7.4 — `7_SSSOM_Vorschau.py` (war `4_SSSOM_Vorschau.py`)

- `project_id` an `sssom_preview` übergeben.

### Task 7.5 — `8_Export.py` (war `5_Export.py`)

- `project_id` an `export_summary`, `export_sssom`, `export_ontology`,
  `export_audit_report`, `get_clusters`, `run_clustering` übergeben.
- Nach erfolgreichem Export: Button "Snapshot erstellen" mit vorausgefülltem
  `version_label = datetime.now().strftime("Export %Y-%m-%d")`.

### Task 7.6 — `3_Rahmenwerke.py` (war `1_KQR_Auswahl.py`)

- **Keine** `project_id`-Abhängigkeit: KQR sind global.
- `require_active_project()` wird hier **nicht** aufgerufen.
- Button "Weiter zur Klassifikation →" ändert sich zu:
  "Zurück zur Projekt-Status-Seite →" (navigiert zu `2_Projekt_Status.py`).


---

## Phase 8 — Datenmigration

### Task 8.1 — Automatische Migration beim Serverstart

In `app/services/project_service.py` eine `_migrate_legacy_data()` Funktion,
die beim Modulimport einmalig aufgerufen wird:

```python
def _migrate_legacy_data() -> None:
    """
    Falls data/projects/ noch nicht existiert, aber data/mappings.json vorhanden ist:
    1. Erstellt data/projects/default/
    2. Verschiebt (nicht kopiert) folgende Dateien:
         data/mappings.json           → data/projects/default/mappings.json
         data/classification_jobs.json → data/projects/default/classification_jobs.json
         data/disjoint_decisions.json  → data/projects/default/disjoint_decisions.json
         data/clusters.json            → data/projects/default/clusters.json
         data/clusters_dag.json        → data/projects/default/clusters_dag.json
         data/sssom/                   → data/projects/default/sssom/
         data/ontology/                → data/projects/default/ontology/
    3. Legt data/projects/default/project.json mit name="Migrated Default"
       und kqr_ids=[alle aktuell registrierten KQR-IDs] an.
    Wenn data/projects/ bereits existiert: keine Aktion.
    """
```

**Wichtig**: Die Funktion ist idempotent — ein zweiter Aufruf verändert nichts.
Formalisierte TTL-Dateien und die KQR-Registry bleiben unangetastet.

---

## Phase 9 — Tests

### Task 9.1 — `tests/test_project_service.py` (neu)

```python
"""
Alle Tests mit tmp_path-Fixture (keine permanenten Daten).
Tests:
- create_project() legt Verzeichnis und project.json an.
- list_projects() gibt leere Liste bei leerem data/projects/ zurück.
- get_project() wirft KeyError für unbekannte IDs.
- update_project() ändert name/description, aktualisiert updated_at.
- create_snapshot() kopiert alle Datendateien, setzt status=SNAPSHOT.
  Original-Projekt bleibt unverändert.
- fork_project() erstellt leeres neues Projekt mit parent_project_id.
- delete_project() entfernt Verzeichnis.
- _migrate_legacy_data() verschiebt Dateien korrekt, ist idempotent.
- get_pipeline_status() gibt leere kqr_pairs bei neuem Projekt zurück.
"""
```

### Task 9.2 — Bestehende Tests anpassen

Tests, die `mapping_service`, `classification_service`, `disjoint_service`
direkt importieren, müssen `project_id="test"` an alle Aufrufe übergeben
und `tmp_path`-basierte Datenpfade verwenden.
Die bestehende `isolated_services`-Fixture in `conftest.py` wird um
`project_id="test"` und die entsprechende Verzeichnisstruktur erweitert.


---

## Implementierungsreihenfolge (strikt einhalten)

```
Phase 0: Sofort-Fix
[ ] Task 0.1 — Dateien umbenennen (ui/pages/)
[ ] Task 0.2 — st.header() in umbenannten Dateien anpassen
[ ] Task 0.3 — app.py Navigationsliste aktualisieren
[ ] Smoke-Test: Streamlit starten, Sidebar-Reihenfolge prüfen

Phase 1: Backend Projektmodell
[ ] Task 1.1 — schemas.py: Project, KQRPairStatus, ProjectPipelineStatus
[ ] Task 1.2 — project_service.py erstellen (inkl. _migrate_legacy_data)
[ ] Task 1.3 — mapping_service.py: project_id-Parameter ergänzen
[ ] Task 1.3 — classification_service.py: project_id-Parameter ergänzen
[ ] Task 1.3 — disjoint_service.py: project_id-Parameter ergänzen
[ ] Task 1.3 — ontology_service.py: project_id-Parameter ergänzen

Phase 2: API-Routen
[ ] Task 2.1 — app/api/routes/projects.py erstellen
[ ] Task 2.2 — project_id Query-Parameter in classification/mappings/disjoint/export
[ ] Task 2.3 — app/api/main.py: projects-Router einbinden
[ ] Smoke-Test: FastAPI starten, GET /projects/ und POST /projects/ testen

Phase 3: api_client und session
[ ] Task 3.1 — api_client.py: _request() mit project_id erweitern
[ ] Task 3.2 — api_client.py: Projekt-Funktionen ergänzen
[ ] Task 3.3 — ui/session.py erstellen

Phase 4: Dashboard
[ ] Task 4.x — app.py vollständig ersetzen
[ ] Smoke-Test: Streamlit starten, Projektliste und KQR-Übersicht prüfen

Phase 5 & 6: Neue Pages
[ ] Task 5.x — ui/pages/1_Projekte.py erstellen
[ ] Task 6.x — ui/pages/2_Projekt_Status.py erstellen
[ ] Smoke-Test: Projekt erstellen, öffnen, Status-Seite prüfen

Phase 7: Bestehende Pages anpassen
[ ] Task 7.1 — 4_Klassifikation.py
[ ] Task 7.2 — 5_Konjunkte_Konzepte.py
[ ] Task 7.3 — 6_Disjunkte_Konzepte.py
[ ] Task 7.4 — 7_SSSOM_Vorschau.py
[ ] Task 7.5 — 8_Export.py
[ ] Task 7.6 — 3_Rahmenwerke.py

Phase 8: Migration
[ ] Task 8.1 — _migrate_legacy_data() Smoke-Test mit bestehendem data/

Phase 9: Tests
[ ] Task 9.1 — test_project_service.py
[ ] Task 9.2 — conftest.py und bestehende Tests anpassen
[ ] pytest -x ausführen, alle Tests grün
```

---

## Invarianten (analog ERWEITERUNGSPLAN.md)

1. **KQR-Daten bleiben global** — `data/kqr_registry.json`, `data/formalized/`,
   `data/raw/` und der Embeddings-Cache werden nicht in Projektverzeichnisse kopiert.

2. **SNAPSHOT-Projekte sind schreibgeschützt** — Alle Service-Funktionen, die
   Daten schreiben (add_mappings, decide, etc.), prüfen bei `project_id` ob
   `status == SNAPSHOT` und werfen eine `ValueError` wenn ja.

3. **`project_id="default"` als Fallback** — Alle Service-Funktionen mit
   `project_id: str = "default"` bleiben rückwärtskompatibel. Bestehende
   Tests, die keinen `project_id` übergeben, funktionieren weiterhin.

4. **Keine neuen VH-Werte** — Dieses Refactoring ist reine Infrastruktur.
   Empirische Parameter (min_cluster_size, k, few-shot-Anzahl) werden nicht
   verändert.

5. **Pydantic an Modulgrenzen** — `project_service.py` gibt `Project`-Objekte
   zurück, keine rohen Dicts. API-Routen serialisieren via `response_model`.

6. **Tests laufen ohne Netzwerk** — `test_project_service.py` verwendet
   ausschließlich `tmp_path` und keine echten Backend-Aufrufe.

---

## Out of Scope (nicht Teil dieses Plans)

- Benutzerauthentifizierung / Mehrbenutzer-Isolation
- Echtzeit-Synchronisierung zwischen Browser-Tabs (ein Tab = eine Session)
- Automatisches Versionieren bei jedem Mapping-Update
- REST-API für externe Integration der Projektdaten

