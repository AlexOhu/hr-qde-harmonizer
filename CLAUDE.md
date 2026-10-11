# CLAUDE.md: Projektanleitung für Coding-Agenten

Prototyp zur Masterarbeit „Harmonisierung von Kompetenz- und
Qualifikationsrahmenwerken im HR-QDE-Ökosystem“ (FernUniversität in Hagen).
Dieses Repo realisiert die Systementwicklung (Kapitel 4 nach Nunamaker),
`eval/` die Evaluation (Kapitel 5). Das Repo befindet sich im Übergabestand.

Weiterführende Dokumente:

- `README.md`: Setup, Daten, Reproduktion der Lieferung
- `docs/ARCHITECTURE.md`: Schichten, Parameter von v0.4, ADR-1 bis ADR-27
- `eval/README.md` und `eval/PROTOKOLL.md`: Experimente, Abweichungen, Zahlenstände
- `frontend/README.md`: React-Oberfläche, Routen, dokumentierte API-Lücken

## 1. Schnellstart

```bash
.venv\Scripts\activate                 # Windows; Linux/macOS: source .venv/bin/activate
uvicorn app.api.main:app --reload      # Backend, Port 8000
cd frontend && npm install && npm run dev   # UI, Port 5173
pytest tests/ -v                       # kein Netzwerk, kein Neo4j nötig
```

Neo4j ist optional (ADR-5, `docker compose up -d`). Stand Oktober 2026 umfasst
die Backend-Suite 235 Tests (223 bestanden, 12 übersprungen, weil optionale
Experimentdaten fehlen).

## 2. Projektstruktur

```
app/
  api/main.py, api/routes/    FastAPI, Routen: kqr, classification, mappings,
                              export, disjoint, projects
  pipeline/
    step1_formalization/      formalize.py: KQR-Quelle -> SKOS/Turtle
    step2_embedding_prefilter/ embed.py, prefilter.py (Shortcut, FAISS),
                              clustering.py, dag_builder.py
    step3_classification/     classify.py (Dreifachlauf, Mehrheitsentscheid),
                              llm_provider/ (anthropic, openai, gemini, mistral)
    step4_export/             sssom_writer.py, ontology_export.py,
                              saeule_d_delivery.py (drei Lieferartefakte)
  services/                   Orchestrierung, Datei-Store, Projekte
  models/schemas.py           alle Pydantic-Modelle
  graph/neo4j_client.py       optionale Neo4j-Materialisierung
  config.py                   Settings aus .env
frontend/                     React/TypeScript-SPA (Vite)
scripts/                      nummerierte Datenaufbau- und Lieferskripte
eval/                         Experimente E1 bis E5, Baselines, Goldmengen, Protokolle
prompts/                      Klassifikations-Prompt-Template
data/                         formalisierte KQR, Lieferung v0.4
tests/                        Backend-Tests, fixtures/ mit minimalem Hub- und Satelliten-KQR
docs/                         ARCHITECTURE.md
```

Bezugsdokumente von Adrian Vogler im Repo-Root: `hrqde-harmonisation-schema.ttl`,
`hrqde-shape-harmonisation.ttl`, `hrqde-shapes-all.ttl`,
`esco-skeleton-for-oberhuber.ttl`.

## 3. Domänenbegriffe

| Begriff | Bedeutung |
|---|---|
| **KQR** | Kompetenz-, Qualifikations- und Berufsrahmenwerk (ESCO, e-CF, EQF, DQR) |
| **Hub-KQR** | Ankerpunkt der Pipeline, in der Lieferung das ESCO-Skelett (1302 Skills, ADR-25) |
| **Satellit-KQR** | Zu integrierender Rahmen (e-CF, DQR, EQF) |
| **K** | Konjunkte Menge: Konzeptpaare mit Äquivalenz oder Subsumtion |
| **D1, D2** | Disjunkte Mengen: Konzepte, die nur in einem KQR vorkommen |
| **mapping_justification** | Verfahrensnachweis als SEMAPV-CURIE, z. B. `semapv:LLMBasedMatching` (ersetzt `match_type`, ADR-17) |
| **review_status** | `open`, `conjunct` oder `disjunct` |
| **predicate_id** | `MappingPredicate`-CURIE (`skos:exactMatch` bis `skos:relatedMatch`), `null` bei offenem Paar ohne Mehrheitsentscheid (ADR-27) |
| **KQR-Status** | `roh`, `formalisiert`, `bereit` (Voraussetzung für Klassifikation) |
| **VH1.x** | Verbleibende Herausforderung aus Kapitel 2, in Kapitel 5 empirisch bearbeitet |

`RelationType` (`EQUIVALENT`, `A_SUBSUMES_B`, `B_SUBSUMES_A`, `RELATED`) ist
klassifikationsschritt-intern. Persistiert und über die API ausgetauscht wird
ausschließlich `MappingPredicate`. Offene Paare werden mit stabiler
`mapping_id` gespeichert und über `PUT /mappings/{id}/review` entschieden.

Integrationsstrategien für disjunkte Konzepte: `own_class`,
`attach_to_skeleton`, `map_to_nearest` (Kontextverlust-Vermerk verpflichtend),
`out_of_scope`.

## 4. KQR-Daten

Beim Registrieren legt `kqr_service` die Datei als `data/formalized/<kqr_id>.ttl`
ab. Die KQR-IDs sind kleingeschrieben, die versionierten Dateien tragen teils
`1D`/`2D` im Namen.

| KQR-ID | Versionierte Datei | Konzepte | Rolle |
|---|---|---|---|
| `esco_skeleton_oberhuber` | `esco_skeleton_oberhuber.ttl` | 1302 | Hub der Lieferung v0.4 |
| `esco_v1_2_ict_ausschnitt` | `esco_v1_2_ict_ausschnitt.ttl` | 956 | früherer Hub, Grundlage von E4 |
| `ecf` | `ecf.ttl` | 45 | Satellit (Dimension 2) |
| `ecf_level` | `ecf_level.ttl` | 146 | Satellit (Dimension 3) |
| `dqr_1d` | `dqr_1D.ttl` | 8 | DQR-Niveauanker |
| `dqr_2d`, `eqf_1d`, `eqf_2d` | `dqr_2D.ttl`, `eqf_1D.ttl`, `eqf_2D.ttl` | 40, 8, 32 | Granularitätsvarianten für Kapitel 5 |

Herkunft der Dateien: nummerierte Skripte `scripts/00` bis `scripts/22`. Die
e-CF-Formalisierung lief LLM-gestützt mit manueller Kuration und ist nicht
deterministisch reproduzierbar. Das Skelett stammt von Adrian Vogler und wird
über `scripts/19_ingest_esco_skeleton.py` eingetragen. Rohquellen unter
`data/raw/` sind nicht versioniert (Lizenz, Größe).

## 5. Experimente und Goldmengen

| Experiment | Skript | Ergebnisse |
|---|---|---|
| E1 Recall@k | `eval/E1_recall_k.py` | `eval/results/E1_recall_k.json`, `E1_recall_k_levels.json` |
| E2 Few-Shot-Ablation | `eval/E2_few_shot.py`, `eval/R_rerun.py` | `eval/results/E2_few_shot.json`, `eval/results/rerun_2026-10/` |
| E3 Confidence-Schwelle | `eval/E3_confidence.py`, `eval/scripts/e3_isolation_run.py` | `E3_confidence.json`, `E3_neukalibrierung.json` |
| E4 HDBSCAN | `eval/E4_hdbscan.py` | `E4_hdbscan.json`, `E4_hdbscan_prod1302.json` |
| E5 Kompetenzfragen CQ1 bis CQ4 | `eval/E5_cq_evaluation.py` | `E5_cq_evaluation.json`, `rerun_2026-10/E5_cq_v0.4.json` |
| Baselines, Zweitannotation | `eval/B_baselines.py`, `eval/S_sample.py`, `eval/S_analyze.py` | `B_baselines.json`, `eval/annotation/` |

Goldmengen: `eval/G_struct.json` (32 Paare DQR ↔ EQF, normativ aus dem
Deutschen EQR-Referenzierungsbericht), `eval/gold/G_manual.json` (e-CF ↔ ESCO), `eval/G_levels.json` (113 Paare
e-CF-Dimension-3 ↔ DQR, Quelle e-CF 3.0, CWA 16234-1:2014). Abweichungen,
Zahlenstände und Reihenfolge der Läufe stehen in `eval/PROTOKOLL.md`.

## 6. Häufige Aufgaben

**Neue API-Route:** Route in `app/api/routes/`, Router in `app/api/main.py`,
Typ in `frontend/src/api/types.ts` (nur real gelieferte Felder), Aufruf unter
`frontend/src/api/`, Test in `tests/test_api.py`.

**Pipeline-Schritt isoliert testen:**

```bash
pytest tests/test_embed.py tests/test_prefilter.py -v
pytest tests/test_classify.py tests/test_classify_call.py -v
```

**LLM-Provider konfigurieren:** `.env` mit `LLM_PROVIDERS` und dem Schlüssel des
Anbieters, Vorlage in `.env.example`. Ein neuer Anbieter implementiert
`llm_provider/base.LLMProvider` und wird in `llm_provider/factory.py`
registriert.

**Lieferung reproduzieren:** siehe `README.md`, Abschnitt „Lieferung
reproduzieren“. Die Konfiguration von v0.4 liegt in
`data/deliverables/v0.4-20261004/run_config.json`.

## 7. Offene Punkte (Lieferung v0.4)

- **HDBSCAN (VH2.3, Negativbefund):** Der Zielwert wird von keinem getesteten
  Parameter erreicht, für den Skill-Raum entsteht keine navigierbare Hierarchie.
  Die Lieferung enthält daher keinen `harm:HarmonisedCluster`.
- **LLM-Richtungsverzerrung:** Nur 1 von 800 klassifizierten Paaren erhält
  `EQUIVALENT`, die Erkennung von Äquivalenz bleibt unzuverlässig (CQ1).
- **Disjunkte Konzepte (CQ3):** Der Vorschlag `own_class` stammt aus
  `disjoint_service.suggest_strategy()`, die manuelle Einzelprüfung steht aus.
- **Offene Reviews:** 559 Paare (RELATED oder ohne Mehrheitsentscheid) sind
  nicht entschieden und fehlen in den Lieferartefakten. Coverage-Quote 440 von
  999 (0,440).
- **`harm:hasLevel` im Formalisierungspfad:** Erzeugt wird es nur durch
  `scripts/17_ecf_add_dimension3.py` und `scripts/18_annotate_concept_roles.py`.
  `formalize.py` kennt es nicht, eine neu formalisierte Quelle braucht diese
  Nachbearbeitung.
- **E4:** lief auf dem früheren 956er-Ausschnitt und wurde für das 1302er-Skelett
  nicht wiederholt.

## 8. Konventionen

- Python 3.11+, Typannotationen verpflichtend, Pydantic v2 an Modulgrenzen
- Keine API-Schlüssel im Code, ausschließlich `.env` und `app/config.py`
- Turtle-Dateien in UTF-8 mit Namensraum-Präfixen im Header
- Kein `print()` in Produktionscode, stattdessen `logging.getLogger(__name__)`
- Commit-Messages auf Deutsch
- Neue Abweichungen von der Konzeption als ADR in `docs/ARCHITECTURE.md`
  eintragen und im Code mit `# ADR-XX: Begründung` kommentieren
- Schreibstil: Beistriche oder neuer Satz statt Hyphen-getrennter Nebensätze

## Agent skills

### Issue tracker

Issues und Spezifikationen liegen in GitHub Issues (`AlexOhu/hr-qde-harmonizer`); PRs sind keine Ticketquelle. Siehe `docs/agents/issue-tracker.md`.

### Triage labels

Die kanonischen Labels `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human` und `wontfix` werden unverändert verwendet. Siehe `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` im Repo-Root und ADRs unter `docs/adr/`. Bis diese Dateien angelegt sind, stehen die bestehenden ADRs in `docs/ARCHITECTURE.md`. Siehe `docs/agents/domain.md`.
