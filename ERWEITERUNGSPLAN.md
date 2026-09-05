# Erweiterungsplan: Prototyp 2 (FZ2.3) und Prototyp 3 (FZ3.3)

> Dieses Dokument ist der operative Arbeitsplan für Claude Code.
> Implementierungsreihenfolge strikt einhalten — spätere Tasks setzen
> frühere voraus. Jeden abgeschlossenen Task mit `[x]` markieren.

---

## Ausgangslage

| Komponente | Status |
|---|---|
| Schritt 1 Formalisierung (`step1_formalization/`) | ✅ implementiert |
| Schritt 2 Embedding + Vorfilter (`step2_embedding_prefilter/prefilter.py`, `embed.py`) | ✅ implementiert |
| Schritt 3 LLM-Klassifikation (`step3_classification/`) | ✅ implementiert |
| Schritt 4 SSSOM-Export (`step4_export/sssom_writer.py`) | ✅ implementiert |
| API-Routes (kqr, classification, mappings, export/sssom) | ✅ implementiert |
| Streamlit-UI Seiten 1–4 | ✅ implementiert |
| `step2_embedding_prefilter/clustering.py` | ✅ implementiert (Erweiterungsplan) |
| `step4_export/ontology_export.py` | ✅ implementiert (Erweiterungsplan) |
| API `POST /export/ontology` + `/audit-report` | ✅ implementiert (HTTP 409 statt 501 bei fehlendem Clustering) |
| Seite 5 OWL-Export + Prüfbericht | ✅ implementiert |
| Disjoint-Entscheidungsworkflow (FZ3.3) | ✅ implementiert (Seite 3b) |

Alle neuen Dateien folgen den Konventionen in `CLAUDE.md`:
Python 3.11+, Typannotationen verpflichtend, Pydantic an Modulgrenzen,
kein Code ohne zugehörigen Test (Tests laufen ohne Netzwerk/LLM/Neo4j).

---

## Phase 0 — Schemas erweitern

**Datei:** `app/models/schemas.py`
**Abhängigkeit:** keine (wird von allen anderen Tasks benötigt)

### Task 0.1 — `ClusterResult` und `HarmonisedCluster` hinzufügen

Am Ende der Datei, nach `SSSOMRecord`, einfügen:

```python
class ClusterResult(BaseModel):
    """Ergebnis eines HDBSCAN-Clusters (FZ2.3, Abschnitt 4.4.1)."""
    cluster_id: int                    # -1 = Noise/Ausreißer
    concept_uris: list[str]            # Concept.uri-Werte im Cluster
    auto_label: str                    # häufigstes prefLabel (deterministisch)
    llm_label: str | None = None       # LLM-verfeinertes Label (zweistufig, VH1.6)
    centroid_uri: str | None = None    # Konzept mit kleinstem L2-Abstand zum Zentroid


class HarmonisedCluster(BaseModel):
    """Knoten im harmonisierten DAG (rdfs:subClassOf-Hierarchie, FZ2.3)."""
    cluster_uri: str                   # http://hr-qde.org/harmonised/cluster/{id}
    label: str
    parent_cluster_uri: str | None = None
    member_uris: list[str]             # kanonische Konzept-URIs
```

### Task 0.2 — `DisjointStrategy` und `DisjointConceptDecision` hinzufügen

Direkt nach `HarmonisedCluster` einfügen:

```python
class DisjointStrategy(str, Enum):
    """Drei zulässige Integrationsstrategien für disjunkte Konzepte (FZ3.3)."""
    STANDALONE_CLASS = "standalone_class"
    # Konzept wird als eigenständige hrqde:HarmonisedConcept-Klasse übernommen.
    ANCHOR_TO_ROOT   = "anchor_to_root"
    # Konzept wird als rdfs:subClassOf einer HR-QDE-Top-Level-Klasse eingehängt.
    EXCLUDED         = "excluded"
    # Konzept gehört nicht zur harmonisierten Ontologie (begründungspflichtig).


class DisjointConceptDecision(BaseModel):
    """Dokumentierte Integrationsentscheidung für ein disjunktes Konzept (FA4)."""
    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    concept_id: str
    concept_label: str
    kqr_id: str
    strategy: DisjointStrategy
    anchor_class: str | None = None    # bei ANCHOR_TO_ROOT: Zielklassen-URI
    justification: str                 # verpflichtend (Accountability-Prinzip)
    author: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## Phase 1 — Prototyp 2 (FZ2.3): Kernstrukturableitung

**Forschungsziel FZ2.3:** Prototypische Implementierung eines Verfahrens
zur Erzeugung harmonisierter Teilstrukturen aus der Menge K, einschließlich
zentraler Klassen, Relationen und Strukturprinzipien als Kern einer neuen Ontologie.

### Task 1.1 — HDBSCAN implementieren

**Datei:** `app/pipeline/step2_embedding_prefilter/clustering.py`

Signatur beibehalten, Stub ersetzen:

```python
import hdbscan
import numpy as np
from app.models.schemas import ClusterResult

def cluster_concepts(
    embeddings: dict[str, np.ndarray],
    min_cluster_size: int = 5,   # vorläufig (VH2.3), empirische Bestimmung Kap. 5
) -> list[ClusterResult]:
    """
    Clustert alle Konzepte beider KQR im gemeinsamen Embedding-Raum per HDBSCAN.
    Gibt eine Liste von ClusterResult zurück; Cluster-ID -1 = Noise/Ausreißer.
    Der Kondensationsbaum (clusterer.condensation_tree_) wird als Attribut
    des Rückgabeobjekts NICHT mitgegeben — er wird in dag_builder.py separat
    aus dem hdbscan.HDBSCAN()-Objekt gezogen. Die Funktion daher so gestalten,
    dass clusterer als zweiter Rückgabewert mitgegeben wird, damit dag_builder
    darauf zugreifen kann:

        return results, clusterer

    Noise-Konzepte (cluster_id == -1) werden in der Liste mitgeführt, damit
    disjoint_service.py sie als Kandidaten für die Integrationsstrategie
    verwenden kann (Phase 2).
    """
```

Implementierungshinweise:
- `hdbscan` ist bereits in `requirements.txt` enthalten (`.venv/Scripts/` zeigt kein `hdbscan`-Binary, aber das Paket ist als Python-Import vorhanden — prüfen via `import hdbscan`).
- `gen_min_span_tree=True` setzen, damit der Kondensationsbaum verfügbar ist.
- `metric="euclidean"` (Vektoren sind bereits L2-normalisiert aus `embed.py`).
- `auto_label`: häufigstes `prefLabel` im Cluster bestimmen via `concept_lookup`; `concept_lookup` als Parameter ergänzen.
- `centroid_uri`: Konzept mit kleinstem L2-Abstand zum Clusterzentroid (Durchschnitt der Clustervektoren).

**Aktualisierte Signatur:**

```python
def cluster_concepts(
    embeddings: dict[str, np.ndarray],
    concept_lookup: dict[str, dict],  # uri -> {"pref_label": ..., "kqr_id": ...}
    min_cluster_size: int = 5,
) -> tuple[list[ClusterResult], "hdbscan.HDBSCAN"]:
```

### Task 1.2 — DAG-Builder erstellen

**Datei:** `app/pipeline/step2_embedding_prefilter/dag_builder.py` (neu)

```python
"""
Überführt den HDBSCAN-Kondensationsbaum in einen gerichteten azyklischen
Graphen (DAG) mit rdfs:subClassOf-Semantik (FZ2.3, Abschnitt 4.4.2).

Abhängigkeit: hdbscan.HDBSCAN-Objekt aus clustering.cluster_concepts().
Kein LLM-Aufruf in condensation_tree_to_dag() und name_clusters_auto()
— beide Funktionen sind ohne Mock testbar (vgl. CLAUDE.md-Prinzip
"Pipeline-Schritte sind unabhängig testbar").
"""

from app.models.schemas import ClusterResult, HarmonisedCluster

HRQDE_CLUSTER_BASE = "http://hr-qde.org/harmonised/cluster/"


def condensation_tree_to_dag(
    clusterer: "hdbscan.HDBSCAN",
) -> dict[int, int | None]:
    """
    Extrahiert die Eltern-Kind-Beziehungen aus dem Kondensationsbaum.
    Rückgabe: {cluster_id: parent_cluster_id | None (= Wurzel)}.
    """


def name_clusters_auto(
    clusters: list[ClusterResult],
    concept_lookup: dict[str, dict],
) -> dict[int, str]:
    """
    Benennt jeden Cluster deterministisch durch das häufigste prefLabel
    seiner Mitgliedskonzepte. Kein LLM-Aufruf. Grundlage für Schicht 1
    der zweistufigen Benennung (Abschnitt 4.4.2).
    """


def name_clusters_llm(
    clusters: list[ClusterResult],
    concept_lookup: dict[str, dict],
    provider: "LLMProvider",
) -> dict[int, str]:
    """
    Verfeinert die auto-Labels per LLM (Schicht 2). Kurzer Prompt:
    Liste der prefLabels im Cluster → prägnanter Oberbegriff.
    Modellwahl vorläufig (VH1.6), als Parameter freilegen.
    Fehler (Timeout, Parse-Fehler) führen zu Fallback auf auto_label,
    niemals zu NotImplementedError oder stiller None-Rückgabe.
    """


def build_harmonised_clusters(
    clusters: list[ClusterResult],
    dag: dict[int, int | None],
) -> list[HarmonisedCluster]:
    """
    Kombiniert ClusterResult + DAG zu HarmonisedCluster-Objekten.
    URI-Schema: {HRQDE_CLUSTER_BASE}{cluster_id}
    Noise-Cluster (id == -1) werden nicht als HarmonisedCluster ausgegeben —
    ihre Konzepte sind Kandidaten für disjoint_service.py (Phase 2).
    """
```

### Task 1.3 — OWL-Export implementieren

**Datei:** `app/pipeline/step4_export/ontology_export.py`

Beide Stub-Funktionen implementieren. Abhängigkeiten: `rdflib` (bereits installiert).

```python
from rdflib import OWL, RDF, RDFS, SKOS, Graph, Literal, Namespace, URIRef

HRQDE = Namespace("http://hr-qde.org/harmonised/")
OWL_NS = OWL  # rdflib built-in


def export_ontology(
    mappings: list[Mapping],
    clusters: list[HarmonisedCluster],   # neu gegenüber Stub
    fmt: str,
    output_path: Path,
) -> Path:
    """
    Baut einen rdflib-Graphen aus Mappings + Cluster-DAG und serialisiert ihn.
    fmt: "turtle" | "xml" | "json-ld"

    Reihenfolge des Graph-Aufbaus:
    1. Namespace-Präfixe binden (hrqde, skos, owl, rdfs).
    2. Jeden HarmonisedCluster als owl:Class eintragen
       + rdfs:label + optional rdfs:subClassOf (aus parent_cluster_uri).
    3. Mitgliedskonzepte als owl:NamedIndividual mit rdf:type -> Cluster-URI.
    4. Mappings als SKOS-Prädikate zwischen Konzept-URIs:
       RelationType.to_skos_predicate() liefert das korrekte Prädikat.
    """


def export_audit_report(
    mappings: list[Mapping],
    unresolved: list[Mapping],
    output_path: Path,
) -> Path:
    """
    Erzeugt eine Markdown-Datei mit drei Abschnitten:
    1. Automatische Mappings (Shortcut + LLM) — Anzahl, Konfidenzverteilung.
    2. Manuell bestätigte/korrigierte Mappings (mapping_source == "manual").
    3. Offene UNRESOLVED-Fälle mit subject_label, object_label, Begründung.

    Entspricht dem Accountability-Prinzip (Abschnitt 3.8.3, FA5).
    """
```

**Hinweis zur Signatur:** `export_ontology` bekommt `clusters` als neuen Parameter.
Die bestehende API-Route muss entsprechend angepasst werden (Task 1.5).

### Task 1.4 — Ontologie-Service erstellen

**Datei:** `app/services/ontology_service.py` (neu)

```python
"""
Orchestriert FZ2.3: Embeddings laden → HDBSCAN → DAG → Persistenz.
Analog zu classification_service: keine direkten Pipeline-Importe
in api/routes/, Orchestrierung ausschließlich hier.

Persistenz: data/clusters.json (ClusterResult-Liste als JSON),
analog zu data/mappings.json.
"""

from app.models.schemas import ClusterResult, HarmonisedCluster
from app.pipeline.step2_embedding_prefilter.clustering import cluster_concepts
from app.pipeline.step2_embedding_prefilter.dag_builder import (
    condensation_tree_to_dag, name_clusters_auto, build_harmonised_clusters,
)
from app.services import kqr_service

CLUSTERS_PATH = DATA_DIR / "clusters.json"


def run_clustering(
    kqr_ids: list[str],
    min_cluster_size: int = 5,
) -> list[ClusterResult]:
    """
    Führt HDBSCAN über alle Konzepte der angegebenen KQR aus.
    Embeddings werden aus kqr_service.get_embeddings() geladen
    (analog zu _run_job in classification_service).
    Ergebnis wird in data/clusters.json persistiert.
    """


def get_cluster_results() -> list[ClusterResult]:
    """Lädt persistierte ClusterResults; leere Liste wenn noch nicht berechnet."""


def get_harmonised_clusters() -> list[HarmonisedCluster]:
    """
    Baut HarmonisedCluster aus den gespeicherten ClusterResults + DAG.
    Noise-Cluster (id == -1) werden herausgefiltert.
    name_clusters_auto() wird hier aufgerufen (kein LLM in der kritischen
    Anzeigepfad — LLM-Verfeinerung ist ein separater optionaler Schritt).
    """


def reset() -> None:
    """Leert den In-Memory-Store (primär für Tests)."""
```

### Task 1.5 — Export-API entstubbern

**Datei:** `app/api/routes/export.py`

- `POST /export/ontology`: 501-Exception entfernen, stattdessen:
  1. `ontology_service.get_harmonised_clusters()` aufrufen.
  2. Wenn leer → HTTP 409 mit Hinweis „Clustering noch nicht ausgeführt, POST /clusters/run zuerst".
  3. Sonst `export_ontology(mappings, clusters, fmt, output_path)` aufrufen → `FileResponse`.

- `POST /export/audit-report`: 501-Exception entfernen:
  1. `mapping_service.list_mappings()` und UNRESOLVED-Mappings übergeben.
  2. `export_audit_report(mappings, unresolved, output_path)` aufrufen → `FileResponse`.

- Neuer Endpunkt `GET /clusters` — gibt `get_cluster_results()` zurück (für UI-Statusanzeige).
- Neuer Endpunkt `POST /clusters/run` — startet `ontology_service.run_clustering(kqr_ids)`.
  `kqr_ids` als Query-Parameter (kommagetrennt) oder Request-Body.

### Task 1.6 — Seite 5 aktualisieren

**Datei:** `ui/pages/5_Export.py`

- `st.info("...folgt mit FZ2.2-Ausbau...")` in Spalte 1 ersetzen durch:
  - Status-Check via `GET /clusters` (neuer `api_client`-Call).
  - Wenn keine Cluster: Schaltfläche „Clustering starten" (ruft `POST /clusters/run` auf).
  - Wenn Cluster vorhanden: Format-Selectbox + „Ontologie exportieren"-Button → `POST /export/ontology` → `st.download_button`.
- Analoges Vorgehen für Prüfbericht (Spalte 3).

**Datei:** `ui/api_client.py`

Neue Funktionen ergänzen (analog zu `export_sssom`):
```python
def get_clusters() -> dict: ...
def run_clustering(kqr_ids: list[str]) -> dict: ...
def export_ontology(fmt: str) -> tuple[bytes, str]: ...
def export_audit_report() -> tuple[bytes, str]: ...
```

### Task 1.7 — Tests

**Datei:** `tests/test_clustering.py` (neu)

```python
"""
Synthetische Embeddings (4 klar trennbare Cluster à 10 Konzepte,
2D-Vektoren, kein echtes Embedding-Modell nötig).
Tests:
- cluster_concepts() gibt 4 ClusterResults zurück (kein Noise bei
  klaren Clustern).
- ClusterResult.cluster_id ist eindeutig je Result.
- condensation_tree_to_dag() gibt Dict mit korrekten Eltern-Beziehungen.
- name_clusters_auto() gibt für jeden Cluster einen nicht-leeren String zurück.
- build_harmonised_clusters() filtert Noise heraus.
- Noise-Konzepte (cluster_id == -1) erscheinen NICHT in HarmonisedCluster.member_uris.
"""
```

**Datei:** `tests/test_ontology_export.py` (neu)

```python
"""
Verwendet tests/fixtures/hub_kqr.ttl + satellite_kqr.ttl als Eingabe
(analog test_formalize.py). Keine Netzwerk-Calls.
Tests:
- export_ontology() erzeugt eine gültige Turtle-Datei (rdflib.parse() schlägt nicht fehl).
- Alle HarmonisedCluster-URIs erscheinen als owl:Class im exportierten Graphen.
- rdfs:subClassOf-Beziehungen stimmen mit dem Input-DAG überein.
- export_audit_report() erzeugt eine Markdown-Datei mit den drei Pflicht-Abschnitten.
- fmt="xml" und fmt="json-ld" erzeugen keine Exception.
"""
```

---

## Phase 2 — Prototyp 3 (FZ3.3): Integrationsstrategie für D1/D2

**Forschungsziel FZ3.3:** Prototypische Implementierung der Integrationsstrategie
für die disjunkten Mengen D1 und D2, einschließlich einer Benutzeroberfläche
zur Unterstützung manueller Entscheidungen (Mixed-Initiative-Prinzip).

### Task 2.1 — Disjoint-Service erstellen

**Datei:** `app/services/disjoint_service.py` (neu)

```python
"""
Verwaltet Integrationsstrategien für disjunkte Konzepte (D1 ∪ D2).

Disjunktes Konzept = Konzept, das in keinem Mapping mit predicate_id
skos:exactMatch / skos:broadMatch / skos:narrowMatch vorkommt.
RELATED/UNRESOLVED-Mappings sind Kandidaten für diese Service-Schicht.

Persistenz: data/disjoint_decisions.json, analog zu mappings.json.
"""

from app.models.schemas import Concept, DisjointConceptDecision, DisjointStrategy
from app.services import mapping_service, kqr_service

DISJOINT_PATH = DATA_DIR / "disjoint_decisions.json"


def list_disjoint_concepts() -> list[Concept]:
    """
    Alle Konzepte aus allen registrierten KQR, die in keinem
    K-Mapping (exactMatch/broadMatch/narrowMatch) auf Subject- oder
    Object-Seite vorkommen.
    Reihenfolge: zuerst Konzepte aus D1 (Nicht-Hub-KQR), dann D2 (Hub).
    """


def suggest_strategy(concept: Concept) -> DisjointStrategy:
    """
    Heuristik ohne LLM-Aufruf (Mixed Initiative: System schlägt vor,
    Nutzer entscheidet):
    - Hat das Konzept ein RELATED-Mapping → ANCHOR_TO_ROOT
      (es gibt eine semantische Nähe, aber keine Äquivalenz).
    - Sonst (UNRESOLVED oder kein Mapping) → STANDALONE_CLASS.
    Bewusst konservativ: EXCLUDED wird nie automatisch vorgeschlagen.
    """


def decide(
    concept_id: str,
    strategy: DisjointStrategy,
    justification: str,
    author: str,
    anchor_class: str | None = None,
) -> DisjointConceptDecision:
    """
    Persistiert eine Entscheidung. Justification ist verpflichtend
    (Accountability-Prinzip). Eine bestehende Entscheidung für dasselbe
    concept_id wird überschrieben (kein stilles Duplizieren).
    """


def get_decision(concept_id: str) -> DisjointConceptDecision | None:
    """None wenn noch keine Entscheidung für concept_id vorliegt."""


def list_decisions() -> list[DisjointConceptDecision]: ...

def get_summary() -> dict:
    """
    Zähler: {total_disjoint, decided, open, by_strategy: {standalone, anchor, excluded}}.
    Wird in export_summary() (Gatekeeping, Seite 5) eingebaut.
    """

def reset() -> None: ...  # für Tests
```

### Task 2.2 — Disjoint-API-Route erstellen

**Datei:** `app/api/routes/disjoint.py` (neu)

```
GET  /disjoint/concepts
     → disjoint_service.list_disjoint_concepts()
     Query-Parameter: kqr_id (optional, filtert auf ein KQR)

GET  /disjoint/concepts/{concept_id}/suggest
     → {"concept_id": ..., "suggested_strategy": DisjointStrategy}

POST /disjoint/concepts/{concept_id}/decide
     Body: {strategy, justification, author, anchor_class?}
     → DisjointConceptDecision

GET  /disjoint/decisions
     → list[DisjointConceptDecision]

GET  /disjoint/summary
     → disjoint_service.get_summary()
```

**Datei:** `app/api/main.py`

```python
from app.api.routes import disjoint as disjoint_router
app.include_router(disjoint_router.router, prefix="/disjoint", tags=["disjoint"])
```

### Task 2.3 — Entscheidungs-UI erstellen

**Datei:** `ui/pages/3b_Integrationsstrategie.py` (neu)

Aufbau:
1. **Kopfzeile:** Kurze Erklärung, was disjunkte Konzepte sind, und Zähler
   (offen / entschieden) via `GET /disjoint/summary`.
2. **Filterkontrolle:** Selectbox KQR-Filter + Radio „Alle / Nur offen / Nur entschieden".
3. **Konzeptkarten** (eine je disjunktem Konzept):
   - Oben: `concept_label` (fett), `kqr_id` als Badge, URI als `st.caption`.
   - Mitte: Vorgeschlagene Strategie als vorausgewählter Radio-Button
     (via `GET /disjoint/concepts/{id}/suggest`, gecacht).
   - Unten: Textfeld Begründung (verpflichtend, `st.text_area`),
     Eingabefeld Autor, Schaltfläche „Entscheiden".
   - Nach Klick: `POST /disjoint/concepts/{id}/decide` → grüner `st.success`.
4. **Entscheidungstabelle:** Bereits entschiedene Konzepte darunter,
   gefiltert nach Strategie via `st.dataframe`.

UCSD-Prinzipien, die hier umgesetzt werden:
- **Mixed Initiative:** System schlägt Strategie vor (Radio vorausgewählt), Nutzer überschreibt.
- **Transparency:** URI und Quell-KQR immer sichtbar.
- **Accountability:** Begründung + Autor sind Pflichtfelder.
- **Progressive Disclosure:** Entschiedene Konzepte in ausklappbarer `st.expander`.

**Datei:** `ui/api_client.py`

Neue Funktionen ergänzen:
```python
def list_disjoint_concepts(kqr_id: str | None = None) -> list[dict]: ...
def suggest_disjoint_strategy(concept_id: str) -> dict: ...
def decide_disjoint(concept_id: str, strategy: str, justification: str,
                    author: str, anchor_class: str | None = None) -> dict: ...
def list_disjoint_decisions() -> list[dict]: ...
def disjoint_summary() -> dict: ...
```

### Task 2.4 — Seite 5 Gatekeeping erweitern

**Datei:** `ui/pages/5_Export.py`

`export_summary()` ruft jetzt zusätzlich `disjoint_summary()` auf.
Die Gatekeeping-Warnung zeigt drei Zähler:
- UNRESOLVED-Paare (aus `mapping_service`)
- Disjunkte Konzepte ohne Entscheidung (aus `disjoint_service`)
- Low-Confidence-Mappings (aus `mapping_service`)

**Datei:** `app/api/routes/export.py`

`GET /summary` importiert `disjoint_service.get_summary()` und ergänzt
das Rückgabe-Dict um `{"disjoint_open": N}`.

### Task 2.5 — Tests

**Datei:** `tests/test_disjoint_service.py` (neu)

```python
"""
Verwendet isolated_services-Fixture aus conftest.py (tmp_path-basiert).
Tests:
- list_disjoint_concepts() gibt Konzepte zurück, die in keinem K-Mapping vorkommen.
- suggest_strategy() gibt ANCHOR_TO_ROOT für Konzepte mit RELATED-Mapping zurück.
- suggest_strategy() gibt STANDALONE_CLASS für Konzepte ohne jedes Mapping zurück.
- decide() persistiert und überschreibt korrekt (kein Duplikat bei zweitem Aufruf).
- get_decision() gibt None zurück, wenn keine Entscheidung vorliegt.
- get_summary() zählt korrekt (total, decided, open, by_strategy).
- EXCLUDED wird nie von suggest_strategy() zurückgegeben.
"""
```

---

## Checkliste (Gesamtübersicht)

### Phase 0 — Schemas
- [x] Task 0.1: `ClusterResult` + `HarmonisedCluster` in `schemas.py`
- [x] Task 0.2: `DisjointStrategy` + `DisjointConceptDecision` in `schemas.py`

### Phase 1 — Prototyp 2 (FZ2.3)
- [x] Task 1.1: `clustering.py` implementieren
- [x] Task 1.2: `dag_builder.py` erstellen
- [x] Task 1.3: `ontology_export.py` implementieren
- [x] Task 1.4: `ontology_service.py` erstellen
- [x] Task 1.5: Export-API (`export.py`) entstubbern + neue Endpunkte
- [x] Task 1.6: Seite 5 und `api_client.py` aktualisieren
- [x] Task 1.7: `test_clustering.py` + `test_ontology_export.py` schreiben

### Phase 2 — Prototyp 3 (FZ3.3)
- [x] Task 2.1: `disjoint_service.py` erstellen
- [x] Task 2.2: `disjoint.py`-Route + `main.py` Router-Einbindung
- [x] Task 2.3: `3b_Integrationsstrategie.py` + `api_client.py` ergänzen
- [x] Task 2.4: Seite 5 Gatekeeping + `GET /summary` erweitern
- [x] Task 2.5: `test_disjoint_service.py` schreiben

---

## Invarianten (nicht ändern ohne Rücksprache)

1. **Pydantic an Modulgrenzen** — Rohe Dicts dürfen keine Pipeline-Schritte
   überschreiten. Neue Services folgen dem Muster von `mapping_service.py`.

2. **Tests laufen ohne Netzwerk** — Kein echter LLM-Aufruf, kein Neo4j,
   kein HTTP in Unit-Tests. Mock-Fixtures analog zu `conftest.py`.

3. **VH-Werte nicht hart codieren** — `min_cluster_size` (VH2.3) und
   LLM-Modellwahl in `name_clusters_llm` (VH1.6) sind als Parameter
   freigelegt und als vorläufig kommentiert. Empirische Bestimmung in Kap. 5.

4. **Noise-Cluster (id == -1) nicht in OWL exportieren** — Sie fließen
   in `disjoint_service.list_disjoint_concepts()` ein, nicht in die
   harmonisierte Ontologie.

5. **Keine stillen Fallbacks bei LLM-Fehlern** — `name_clusters_llm` fällt
   bei Fehler auf `auto_label` zurück (explizites Logging), nicht auf `None`.
   Provenance im `ClusterResult` vermerken (ob auto oder llm-Label aktiv ist).

6. **`DisjointStrategy.EXCLUDED` nie automatisch vorschlagen** — Die Strategie
   erfordert eine explizite Nutzerbegründung (Accountability-Prinzip).

7. **HTTP 409 statt 501 für fehlende Vorbedingungen** — Wenn Clustering
   noch nicht ausgeführt wurde, ist das ein Zustandsproblem (409 Conflict),
   kein dauerhaft unimplementierter Endpunkt (501 Not Implemented).
