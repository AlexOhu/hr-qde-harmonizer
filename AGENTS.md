# AGENTS.md – Projektanleitung für Codex

Dies ist der Prototyp zur Masterarbeit „Harmonisierung von Kompetenz- und
Qualifikationsrahmenwerken im HR-QDE-Ökosystem" (FernUniversität in Hagen).
Dieses Dokument ist die primäre Orientierung für Codex.

---

## 1. Schnellstart

```bash
# Virtuelle Umgebung aktivieren (Windows)
.venv\Scripts\activate

# Backend starten (FastAPI, Port 8000)
uvicorn app.api.main:app --reload

# React-UI starten (separates Terminal, Vite, Port 5173)
cd frontend && npm install && npm run dev

# Tests ausführen (kein Netzwerk, kein Neo4j nötig)
pytest tests/ -v
```

Neo4j ist optional. API und Tests laufen ohne erreichbare Datenbankinstanz
(ADR-5). Wenn Neo4j benötigt wird: `docker compose up -d`.

---

## 2. Worum geht es

Ziel ist die algorithmische Harmonisierung mehrerer Kompetenz-, Qualifikations-
und Berufsrahmenwerke (KQR) zu einer gemeinsamen Basis-Ontologie. Die Pipeline
vergleicht zwei KQR semantisch, klassifiziert Konzeptpaare per LLM und exportiert
das Ergebnis als SSSOM-Mapping und OWL-Ontologie.

Die Arbeit folgt Nunamaker (Observation → Theoriebildung → Systementwicklung
→ Experimentieren). Dieses Repository realisiert die Systementwicklungsphase
(Kapitel 4). Kapitel 5 enthält empirische Evaluationen (Experimente E1–E5).

---

## 3. Projektstruktur

```
app/
  api/
    main.py                       # FastAPI-App, Router-Registrierung
    routes/
      kqr.py                      # Funktionsgruppe 1: KQR einpflegen/Status
      classification.py           # Funktionsgruppe 2: Klassifikation steuern
      mappings.py                 # Funktionsgruppe 3+4: Ergebnisse, SSSOM-Vorschau
      export.py                   # Funktionsgruppe 5: Export (SSSOM, OWL, Audit)
      disjoint.py                 # Funktionsgruppe 3b: Integrationsstrategie D1/D2
  pipeline/
    step1_formalization/
      formalize.py                # Schritt 1: KQR → SKOS/Turtle
    step2_embedding_prefilter/
      embed.py                    # Schritt 2a: Embeddings berechnen
      prefilter.py                # Schritt 2b: Vorfilter + FAISS-ANN-Suche
      clustering.py               # HDBSCAN-Clustering
      dag_builder.py              # Kondensationsbaum → DAG
    step3_classification/
      classify.py                 # Schritt 3: LLM-Dreifachklassifikation
      llm_provider/
        base.py                   # LLMProvider-Abstraktion
        anthropic_provider.py     # Anthropic-Implementierung
        mistral_provider.py       # Mistral-Implementierung (Retry/Backoff)
    step4_export/
      sssom_writer.py             # Schritt 4a: SSSOM-TSV
      ontology_export.py          # Schritt 4b: OWL/Turtle-Ontologie + Prüfbericht (API-Route /export)
      saeule_d_delivery.py        # Schritt 4c: drei Lieferartefakte nach MASTERAND_OBERHUBER.md v0.2
                                  #   (write_ontology / write_mappings / write_integration_strategy);
                                  #   validiert gegen hrqde-shape-harmonisation.ttl + hrqde-harmonisation-schema.ttl
  services/
    kqr_service.py                # Orchestrierung Funktionsgruppe 1
    classification_service.py     # Job-Steuerung, Pause/Resume
    mapping_service.py            # Mapping-Persistenz, Review-Summary
    disjoint_service.py           # Disjunkt-Vorschlag und Entscheidung
    ontology_service.py           # Cluster-Ergebnis, DAG
    project_service.py            # Projekt-CRUD, Snapshot, Fork, Migration
  models/
    schemas.py                    # Alle Pydantic-Datenmodelle
  graph/
    neo4j_client.py               # Optionale Neo4j-Materialisierung (ADR-5)
  config.py                       # Settings via .env

frontend/                         # React-Oberfläche (primäre UI)
  src/
    api/                          # Typisierter API-Layer, einzige fetch-Stelle
    app/                          # Provider und Routenbaum
    components/layout|common|ui/  # Rahmen, Master-Detail, Basiskomponenten
    features/
      projects/                   # Projektkontext und Projektdialoge
      frameworks/                 # Framework-Status, Upload-Dialog
      pairs/                      # Paar-Ableitung, Pair-Workspace
      mappings/                   # Mapping-Review (Master-Detail)
      integration/                # Nicht zugeordnete Konzepte
      export/                     # Readiness, SSSOM-Vorschau
    hooks/ lib/ pages/ test/
  README.md                       # Setup, Routen, dokumentierte API-Gaps

data/
  raw/                            # Hochgeladene Originaldateien
  formalized/                     # Validierte SKOS-Turtle-Dateien
  projects/
    default/                      # Projektverzeichnis (Migrationsziel für Legacy-Daten)
      project.json
      mappings.json
      classification_jobs.json
      sssom/                      # Exportierte SSSOM-TSV
      ontology/                   # Exportierte OWL-Ontologien
  kqr_registry.json               # KQR-Metadaten und Status (global)

eval/
  E1_recall_k.py                  # Experiment E1: Recall@k (VH1.5) → GESCHLOSSEN
  E2_few_shot.py                  # Experiment E2: Few-Shot-Ablation (VH1.6) → GESCHLOSSEN
  E3_confidence.py                # Experiment E3: Confidence-Schwellen (VH1.7) → GESCHLOSSEN
  E4_hdbscan.py                   # Experiment E4: HDBSCAN-Parameter (VH2.3) → GESCHLOSSEN
  E5_cq_evaluation.py             # Experiment E5: Kompetenzfragen CQ1–CQ4 → TEILWEISE
  G_struct.json                   # Strukturelle Goldmenge (DQR↔EQF, 32 Paare)
  G_manual_seed.json              # Seed für manuelle Goldmenge (e-CF A.8 ↔ ESCO)
  gold/                           # Erweitertes Goldmaterial
  results/                        # Experiment-Ergebnisse als JSON
  PROTOKOLL.md                    # Methodische Entscheidungen und Abweichungen

tests/
  fixtures/
    hub_kqr.ttl                   # Minimales Hub-KQR (6 Konzepte)
    satellite_kqr.ttl             # Minimales Satelliten-KQR (4 Konzepte,
                                  #   ecf:level_5 mit esco:isPartOf → Shortcut-Test)
  conftest.py                     # FakeSentenceTransformer, FakeLLMProvider,
                                  #   mock_anthropic, isolated_services
  test_api.py                     # FastAPI-Endpunkte, HTTP-Statuscodes (7)
  test_classify.py                # majority_vote, kein-Konsens-Logik (3)
  test_classify_call.py           # Provider-Prompt-Parsing, Fehlerbehandlung (6)
  test_clustering.py              # HDBSCAN, DAG-Bau, Noise-Filterung (8)
  test_disjoint_service.py        # Vorschlag, Persistenz, Vollständigkeit (7)
  test_e1_recall_k.py             # recall_at_k()-Hilfsfunktion (3)
  test_embed.py                   # Embedding, Determinismus, Normalisierung (3)
  test_formalize.py               # Parsing, Validierung, Pflichtfelder (5)
  test_mistral_provider.py        # Retry/Backoff gegen 503/429 (3)
  test_ontology_export.py         # OWL-Aufbau, subClassOf-DAG, Prüfbericht (10)
  test_prefilter.py               # Vorfilter, FAISS-ANN-Suche (8)
  test_project_service.py         # Projekt-CRUD, Snapshot, Fork, Migration (12)
  test_service_integration.py     # End-to-End-Fluss, Pause/Resume (7)
  test_sssom_writer.py            # Confidence-Filter, TSV-Serialisierung (5)
```

  test_mapping_review.py          # Review-Weiche, "pending"-Ablehnung,
                                  #   Kontextverlust-Pflicht, Coverage-Quote (23)

**Gesamtanzahl Tests: 120 Backend (15 Dateien), 44 Frontend. Alle bestehen
(Stand 2026-08-25, pytest 9.1.1, vitest 4.1.11).**

---

## 4. Domänenbegriffe (immer konsistent verwenden)

| Begriff | Bedeutung |
|---|---|
| **KQR** | Kompetenz-, Qualifikations- und Berufsrahmenwerk (ESCO, e-CF, EQF, DQR, …) |
| **Hub-KQR** | Ankerpunkt der Pipeline; derzeit ESCO v1.2 (ICT-Ausschnitt) |
| **Satellit-KQR** | Zu integrierender Rahmen (e-CF, EQF, DQR, …) |
| **K** | Konjunkte Menge: Konzeptpaare mit Äquivalenz/Subsumtion zwischen zwei KQR |
| **D1, D2** | Disjunkte Mengen: Konzepte, die nur in einem KQR vorkommen |
| **SSSOM** | Simple Standard for Sharing Ontology Mappings (Exportformat, TSV) |
| **mapping_justification** | Verfahrensnachweis eines Mappings als SEMAPV-CURIE: `semapv:StructuralMatching`, `semapv:LLMBasedMatching`, `semapv:MappingReview`. Ersetzt das entfernte Feld `match_type` (ADR-19) |
| **review_status** | Entscheidungsstand eines Mappings: `open` (RELATED oder ohne LLM-Mehrheitsentscheid, wartet auf Entscheidung), `conjunct`, `disjunct` |
| **predicate_id** | Das eine Mapping-Relationsvokabular: `MappingPredicate`-CURIE (`skos:exactMatch`, `skos:closeMatch`, `skos:broadMatch`, `skos:narrowMatch`, `skos:relatedMatch`). Persistiert und über die API ausgetauscht. `null` genau bei einem offenen Paar ohne LLM-Mehrheitsentscheid (ADR-30) |
| **KQR-Status** | `roh` → `formalisiert` → `bereit` (Voraussetzung für Klassifikation) |
| **VH1.x** | Verbleibende Herausforderung aus Kapitel 2, empirisch in Kapitel 5 gelöst |

`RelationType` (`EQUIVALENT`, `A_SUBSUMES_B`, `B_SUBSUMES_A`, `RELATED`) ist
klassifikationsschritt-intern: die Ausgabe eines LLM-Laufs und der
Mehrheitsentscheid (`ClassificationResult.final_relation`). Kein Endpunkt nimmt
oder liefert diese Werte. Ein fehlender Mehrheitsentscheid ist
`final_relation = None`, kein eigener Relationswert (ADR-30). Das persistierte
und über die API ausgetauschte Vokabular ist ausschließlich `MappingPredicate`
(`predicate_id`); `RelationType.to_skos_predicate()` bildet die vier Werte
darauf ab. Offene Paare (RELATED oder ohne Mehrheitsentscheid) werden mit
stabiler `mapping_id` persistiert und über `PUT /mappings/{id}/review` als
konjunkt oder disjunkt entschieden (ADR-20); bei offenen Paaren unterscheidet
`predicate_id` (`skos:relatedMatch` bzw. `null`) die beiden Fälle.

Integrationsstrategien für disjunkte Konzepte: `own_class`, `attach_to_skeleton`,
`map_to_nearest` (Kontextverlust-Vermerk verpflichtend), `out_of_scope`.

---

## 5. Architekturprinzipien (nicht umgehen ohne Rücksprache)

**Pipeline-Isolation:** Schritte 1–4 in `app/pipeline/` kennen einander nicht.
Orchestrierung ausschließlich über `app/services/`. Keine direkten Importe
zwischen Pipeline-Schritten.

**Schema-zentrierte Schnittstellen:** Datenübergabe zwischen Modulen immer über
Pydantic-Schemas aus `app/models/schemas.py`. Keine rohen Dicts an Modulgrenzen.

**Provenance-Pflicht:** Jede Klassifikationsentscheidung braucht `mapping_tool`,
`mapping_date`, `match_type` und `mapping_confidence`. Niemals stillschweigend
überschreiben.

**FAISS statt Neo4j-Vektorindex (ADR-4):** Die ANN-Suche läuft über
`faiss.IndexFlatIP`. Schritt 2 ist dadurch ohne laufende Datenbankinstanz testbar.

**Neo4j optional (ADR-5):** API und Tests müssen ohne erreichbares Neo4j
lauffähig sein. Neo4j-Aufrufe immer in `try/except` kapseln;
Fehlschläge werden geloggt, nicht geworfen.

**Projekt-Isolation (ADR-01/02):** Alle Dateipfade für Mappings, Jobs und
Ontologie-Ausgaben leiten sich ausschließlich über `project_service.get_project_data_dir(project_id)`
ab. Ein einzelnes `monkeypatch` von `project_service.DATA_DIR` isoliert damit
alle abhängigen Services gleichzeitig. Nie Dateipfade hart in Services codieren.

**Gestaltungsprinzipien der UI:** Änderungen an der Oberfläche (`frontend/src/`)
müssen die den Funktionsgruppen in Kapitel 3 zugeordneten Gestaltungsprinzipien
achten (Herkunft: Normans Gulf-Modell, Nielsen-Heuristiken,
Mensch-KI-Interaktionsprinzipien): Visibility of System Status, Gulf of
Evaluation, Mixed-Initiative, Transparency, Accountability, Error Prevention.

**Frontend spiegelt Backend-Regeln, definiert sie nicht neu:** Export-Readiness,
Konfidenzschwelle, Paar-Metriken und Projektstatus stammen aus der API. Fehlt
eine Information, wird das in `frontend/README.md` als API-Gap dokumentiert,
statt im Frontend eine eigene Logik zu etablieren. Einzige Ableitung ist
`frontend/src/features/pairs/status.ts` (Job-Einträge → Framework-Paare).

---

## 6. Parameterwerte (empirisch bestätigt durch Kapitel-5-Experimente)

Die folgenden Werte sind durch E1–E4 empirisch geschlossen und im Code gesetzt.
Nicht ohne entsprechende Dokumentation ändern.

| Parameter | Wert | Experiment | Status |
|---|---|---|---|
| Embedding-Modell | `paraphrase-multilingual-mpnet-base-v2` | ADR-6 | Strukturell begründet |
| ANN k | **20** | E1: k*=10 auf G_struct (Recall=0,906), k=20 für volle Abdeckung | **Bestätigt** |
| Klassifikations-LLM | via `LLM_PROVIDERS` in `.env` | ADR-7 | Konfigurierbar |
| Few-Shot-Anzahl | **1** | E2: n_FS*=1, Macro-F1=0,3578 | **Bestätigt** |
| Confidence-Schwelle | **0,67** | E3: θ_op=0,67, P=R=F1=0,9057 | **Bestätigt** |
| HDBSCAN min_cluster_size | **3** | E4: m*=3 als Kompromiss, η<0,20 nicht erreicht | **Bestätigt (neg. Befund)** |

Konfigurationsdatei: `app/config.py`. Werte werden aus `.env` geladen.

---

## 7. KQR-Daten (aktueller Stand)

| KQR-ID | Datei | Konzepte | Rolle |
|---|---|---|---|
| `esco_skeleton_oberhuber` | `formalized/esco_skeleton_oberhuber.ttl` | 1302 | Hub (Lieferung, ADR-27) |
| `esco_v1_2_ict_ausschnitt` | `formalized/esco_v1_2_ict_ausschnitt.ttl` | 956 | Hub (Alt-Stand E1–E5) |
| `ecf` | `formalized/ecf.ttl` | 45 | Satellit |
| `dqr_3` | `formalized/dqr_3.ttl` | 8 | Satellit (Niveaus, ADR-25) |
| `eqf_2017` | `formalized/eqf_2017.ttl` | 8 | Satellit (nicht mehr im Lauf) |

`esco_skeleton_oberhuber` ist die von Adrian Vogler gelieferte
Referenzmenge (`esco-skeleton-for-oberhuber.ttl`, Informatik-Korridor). Sie
wird per `scripts/19_ingest_esco_skeleton.py` als Hub eingetragen und ist
der ESCO-seitige Vergleichsraum der Abgabe (`scripts/run_saeule_d_delivery.py`).
Der 956er-Ausschnitt bleibt Grundlage der bereits gelaufenen Experimente E1–E5.

EQF (8 Niveau-Knoten) muss nach Serverneustart ggf. über `scripts/` erneut
in `kqr_registry.json` eingetragen werden.

Der E4-Embedding-Raum (Alt-Stand) enthält 1033 Konzepte (956 + 45 + 32).

---

## 8. Evaluations-Goldmengen

**G_struct** (`eval/G_struct.json`): 32 Paare, DQR-Dimensionskonzepte ↔ EQF-Deskriptoren,
normativ aus dem German EQF Referencing Report (2012/2013) abgeleitet.
Pro Niveau: 2 `exactMatch`-Paare (Wissen/Fertigkeiten) + 2 `narrowMatch`-Paare
(Sozialkompetenz/Selbstständigkeit  ↔ Responsibility & Autonomy). Alle 32 sind evaluierbar.

**G_manual_seed** (`eval/G_manual_seed.json`): 14 Paare aus Zare et al. (Tabelle 6),
e-CF A.8 ↔ ESCO (Green ICT). Davon 9 evaluierbar (5 ESCO-URIs nicht im ICT-Ausschnitt
oder nicht auffindbar, dokumentiert in `uri_lookup_log`).

```bash
# Experimente ausführen
python eval/E1_recall_k.py      # Ergebnis: eval/results/E1_recall_k.json
python eval/E2_few_shot.py
python eval/E3_confidence.py
python eval/E4_hdbscan.py
python eval/E5_cq_evaluation.py
```

---

## 9. Häufige Aufgaben

### Neue API-Route hinzufügen

1. Route in `app/api/routes/<datei>.py` definieren
2. Router in `app/api/main.py` einbinden
3. Typ in `frontend/src/api/types.ts` ergänzen (nur real gelieferte Felder)
4. Aufruf in der passenden Datei unter `frontend/src/api/` ergänzen
5. Query-Key in `frontend/src/api/queryKeys.ts`, Hook in `frontend/src/hooks/`
6. Seite bzw. Feature unter `frontend/src/` anpassen
7. Test in `tests/test_api.py` und ggf. `frontend/src/test/` ergänzen

### Pipeline-Schritt isoliert testen

```bash
pytest tests/test_embed.py -v
pytest tests/test_prefilter.py -v
pytest tests/test_classify.py tests/test_classify_call.py -v
```

Tests laufen ohne Netzwerk und ohne Neo4j (Mock-LLM und Mock-Embedding-Modell
über `tests/conftest.py`).

### Neue TTL-Datei validieren (SKOS-Minimalcheck)

```python
from rdflib import Graph, RDF, SKOS
g = Graph()
g.parse("data/formalized/eqf_2017.ttl", format="turtle")
concepts = list(g.subjects(RDF.type, SKOS.Concept))
print(f"{len(concepts)} Konzepte gefunden")
for c in concepts[:3]:
    print(c, list(g.objects(c, SKOS.prefLabel)))
```

### Neuen LLM-Provider konfigurieren

In `.env`:
```
LLM_PROVIDERS=mistral          # oder: anthropic, mistral
MISTRAL_API_KEY=sk-...
```

`app/pipeline/step3_classification/llm_provider/` enthält `anthropic_provider.py`
und `mistral_provider.py`. Neuer Provider: `base.LLMProvider` implementieren,
in `get_providers_from_config()` registrieren.

---

## 10. Was offen ist

- **HDBSCAN-Clusterstruktur (VH2.3 – neg. Befund):** m*=3 gesetzt, aber
  η<0,20 von keinem getesteten Wert erreicht. CQ4 (navigierbare Hierarchie)
  daher nicht erfüllt. Offene Limitation → Kapitel 6.
- **LLM-Richtungsverzerrung:** Kein einziges `EQUIVALENT`-Mapping im
  Gesamtdatensatz (4820 ClassificationResult-Objekte). CQ1 nicht erfüllt.
  Offene Limitation → Kapitel 6.
- **Manuelle Kuration der 491 disjunkten Konzepte (CQ3):** Automatisiert
  via `suggest_strategy()` mit `own_class`. Vollständige manuelle
  Einzelprüfung noch ausstehend.
- **1191 offene Reviews im Default-Projekt:** 348 Paare ohne
  LLM-Mehrheitsentscheid (`predicate_id = null`) und 843 RELATED-Paare
  (`skos:relatedMatch`, `review_status = open`). Coverage-Quote dadurch 0,753
  (3629 von 4820). Die Einzelentscheidungen stehen aus.
- **SHACL-Validierung:** `pyshacl` ist in `requirements.txt`. Die
  kanonischen Bezugsdokumente `hrqde-shape-harmonisation.ttl` und
  `hrqde-harmonisation-schema.ttl` (Adrian Vogler, v0.2.0) liegen im
  Repo-Root. `tests/test_saeule_d_delivery.py::test_delivery_passes_canonical_shacl`
  prüft die beiden Liefer-TTL gegen diese Shapes (0 Violations). Die
  Eigenfassung liegt als `hrqde-shape-harmonisation.local-abweichend.ttl.bak`.
- **Säule-D-Abgabe:** `scripts/run_saeule_d_delivery.py` erzeugt die drei
  Artefakte aus einem vollen Lauf gegen `esco_skeleton_oberhuber`. Der Lauf
  liefert frische Zahlen für offene Reviews, disjunkte Konzepte und
  Coverage-Quote (die unten genannten Werte stammen vom 956er-Stand). Die
  manuelle Einzelkuration der disjunkten Konzepte und der offenen Reviews
  steht weiterhin aus und ist im Begleitprotokoll als Limitation vermerkt.

---

## 11. Konventionen

- Python 3.10+, Typannotationen verpflichtend
- Pydantic v2 für alle Modulgrenzen-Datenstrukturen
- Keine API-Keys im Code; ausschließlich über `.env` / `app/config.py`
- Turtle-Dateien: UTF-8, Namespace-Präfixe im Header
- Commit-Messages auf Deutsch
- Keine `print()`-Statements in Produktionscode; `logging.getLogger(__name__)`
- Hyphen-getrennte Nebensätze vermeiden: Beistriche oder neuer Satz.
  Schema „X ist (nicht) Y. Es ist Z" vermeiden.

---

## 12. Bekannte Abweichungen von der Konzeption (ADR-Übersicht)

| ADR | Konzeption (Kap. 3) | Implementierung | Grund |
|---|---|---|---|
| ADR-4 | Neo4j-Vektorindex | FAISS IndexFlatIP | Schritt 2 ohne DB testbar |
| ADR-5 | Neo4j als Daten-Layer | Datei-Store + optionale Neo4j | API ohne DB lauffähig |
| ADR-12 | e-CF 4.0 | e-CF 3.0 | 4.0 nicht frei zugänglich |
| ADR-13 | Single-Provider | Multi-Provider (Anthropic + Mistral) via `LLM_PROVIDERS` | Experimentell validiert mit Mistral |
| ADR-14 | ELM als Integrationsschnittstelle zu Säule B | ELM als optionales Exportformat | Integration mit Säule B läuft transitiv über gemeinsame ESCO-Skill-URIs; kein ELM-Vokabular im HR-QDE-Graphen |
| ADR-16 | FAISS-Index enthält alle Hub-Konzepte | Occupation-URIs werden vor Indexaufbau gefiltert | ESCO-Hub enthält sowohl Skills als auch Berufe; HR-QDE-Datensäulen arbeiten ausschließlich auf Skill-Ebene |
| ADR-17 | Streamlit als Review-UI | React/TypeScript-SPA unter `frontend/`, Backend unverändert. Der Streamlit-Prototyp (`ui/`) ist entfernt | Streamlit-Re-Renders zu langsam für Master-Detail-Review über tausende Mappings; Navigation an Funktionsgruppen statt an Arbeitsobjekten ausgerichtet |
| ADR-18 | API nur von serverseitiger UI genutzt | `CORSMiddleware` in `app/api/main.py`, Origins über `CORS_ALLOW_ORIGINS` | Die SPA ist ein eigener Browser-Origin; ohne CORS blockt der Browser jede Antwort |
| ADR-19 | `match_type` (`lex`/`struct`/`llm`) als Herkunftsfeld, Präfix `hrqde:` für die Harmonisierungsschicht | `mapping_justification` als SEMAPV-CURIE; Präfix `harm:` für `http://hr-qde.org/harmonised/`, `hrqde:` reserviert für das Skelett `http://hr-qde.org/ontology/` | SSSOM verlangt `mapping_justification`; das interne Vokabular war eine zusätzliche Übersetzungsschicht ohne Nutzen. Getrennte Präfixe machen Skelett und Harmonisierungsschicht unterscheidbar |
| ADR-20 | RELATED/kein-Konsens sind kein Bestandteil von K und werden verworfen | Persistiert als `Mapping` mit `review_status="open"`, entscheidbar über `PUT /mappings/{id}/review` | Ohne `mapping_id` waren die Fälle weder adressierbar noch entscheidbar; die Coverage-Quote konnte sie nicht bilanzieren |
| ADR-30 | Zwei Relationsvokabulare (`RelationType` inkl. `UNRESOLVED` + SKOS-Prädikate), verbunden über `to_skos_predicate()` und ein Schattenfeld `source_relation` | Ein Vokabular: `MappingPredicate` (SKOS-CURIE) ist persistiert und API-seitig. `RelationType` ist klassifikationsschritt-intern und ohne `UNRESOLVED`; fehlender Mehrheitsentscheid ist `final_relation=None` bzw. `predicate_id=None` bei `review_status=open`. `source_relation` entfällt; `/export/summary` liefert `no_consensus_pairs` statt `unresolved_pairs`. Frontend übersetzt jedes Prädikat konsequent (`predicateLabel`, `null` → „Kein Konsens") | `source_relation` war ein Schattenfeld nur zur Unterscheidung von RELATED und UNRESOLVED (beide → `skos:relatedMatch`); `UNRESOLVED` ist ein Konsens-Ergebnis, keine semantische Relation; die UI zeigte teils rohe Tokens, teils Übersetzungen. Migration: `scripts/20_migrate_relationtype_to_predicate.py` + `Mapping`-Validator |
| ADR-21 | Coverage-Quote über entschiedene Mappings | Nenner ist K ∪ C_conf inklusive offener Reviews; `/export/summary` liefert `coverage_resolved`, `coverage_total`, `coverage_ratio`, `open_review_count` | Ein Nenner ohne offene Paare meldet 1,0 statt des tatsächlichen Bearbeitungsstands |
| ADR-24 | e-CF-Dimension-3-Crosswalk als `harm:LevelMapping` | Erscheint nur narrativ in `oberhuber-integration-strategy-v{V}.md` | Die kanonische `LevelMappingShape` verlangt für Subjekt und Objekt eine Niveau-URI; eine e-CF-Kompetenz ist kein Niveau |
| ADR-25 | Eigene Niveau-Knoten `harm:EQF{n}`/`harm:DQR{n}` im Artefakt | Keine Prägung; `harm:LevelMapping` referenziert `hrqde:DQR{n}` (`http://hr-qde.org/ontology/`) und `http://data.europa.eu/snb/qf-eu-level/{n}` direkt | Lieferspezifikation §4 „Niveaus nicht neu prägen"; das HR-QDE-Skelett modelliert `hrqde:DQR1..8` bereits |
| ADR-26 | Eine kombinierte Ontologiedatei | Drei getrennte Lieferartefakte (`oberhuber-harmonised-ontology`, `oberhuber-mappings`, `oberhuber-integration-strategy`) | Lieferspezifikation §2 |
| ADR-27 | ESCO-Referenz = `esco_v1_2_ict_ausschnitt` (956) | `esco_skeleton_oberhuber` (1302), aus `esco-skeleton-for-oberhuber.ttl` | Lieferspezifikation §1 macht die gelieferte Skelettdatei zur verbindlichen ESCO-seitigen Vergleichsmenge; E1–E5 bleiben auf dem 956er-Stand und werden separat nachgezogen |
| ADR-28 | SSSOM-Records als `sssom:Mapping` mit `sssom:confidence` (`xsd:double`) und `predicate_id` als String | `harm:HubMapping`/`harm:OccupationMapping`/`harm:LevelMapping` aus `hrqde-harmonisation-schema.ttl`; `sssom:mapping_confidence` `xsd:decimal`; `sssom:predicate_id` als IRI; `sssom:MappingSet` als Container | Die kanonischen SHACL-Shapes verlangen diese Formen; String-Prädikate sind weder per SPARQL noch per Cypher traversierbar |

Bei neuen Abweichungen: ADR-Eintrag in `chapters/chapter_4/architektur.tex`
ergänzen und im Code mit `# ADR-XX: Begründung` kommentieren.

---

## 13. LaTeX-Synchronisation

**2026-08-06:** Tabelle `tab:kap4_tests` und Fließtext in
`qualitaetssicherung.tex` auf den Teststand synchronisiert (89 Tests, 14
Dateien). `ontology_export.py` vollständig implementiert; Stub-Satz entfernt.
Gesamtzahl in der Tabelle: 80 (Fußzeile `\textbf{Gesamt}`).

**2026-08-31 (Säule-D-Abgabe):**
- `chapters/chapter_4/architektur.tex`: ADR-24 bis ADR-28 in
  `tab:kap4_adrs` ergänzt (Lieferspezifikation Säule D). `frontbackmatter/Acronyms.tex`:
  `\acro{SHACL}`. Die ADR-Nummern der Arbeit sind nicht deckungsgleich mit
  denen in AGENTS.md §12 (Tabelle endet bei ADR-23, daher 24–28).
- `eval/E1_recall_k.py` gegen den 1302er-Raum nachgezogen
  (`--kqr esco_skeleton_oberhuber ecf dqr_3 dqr_2 eqf_2017`): k=20 bestätigt,
  G_struct unverändert, G_manual 8 statt 9 evaluierbar. `eval/results/E1_recall_k.json`
  neu; 956er-Stand als `.bak_956_20260831`. E3 ebenso wiederholt (Details in
  `eval/PROTOKOLL.md`).
- Kapitel-5-Fließtext nachgezogen: `chapters/chapter_5/exp1_recall_k.tex`
  (G_manual-Tabelle + Durchführung/Interpretation), `exp3_confidence.tex`
  (Tabelle + Interpretation), `summary.tex` (E3-Recall 0,49→0,58). E1
  G_struct-Tabelle unverändert.
- E5/CQ nachgezogen gegen die drei Lieferartefakte: `eval/E5_cq_evaluation.py`
  hat einen `--delivery`-Modus (reifizierte `harm:HubMapping`-Queries).
  Neue Werte: CQ1=0 (nein), CQ2=156 (ja), CQ3=5 (ja), CQ4=0 (nein) — Verdikt
  „teilweise erfüllt" unverändert. `chapters/chapter_5/cq_evaluation.tex`
  und `frontbackmatter/AppendixSPARQL.tex` synchronisiert; v0.3-Stand als
  `eval/results/E5_cq_evaluation.json.bak_v03_20260831`.
- E2 und E4 vom ESCO-Wechsel nicht betroffen, unverändert.
