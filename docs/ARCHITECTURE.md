# Architektur, Parameter und Entscheidungen

Dieses Dokument fasst die Architektur des HR-QDE Harmonizers, die Parameter
der Lieferung v0.4 und alle Architecture Decision Records (ADR-1 bis ADR-27)
zusammen. Die ausführliche Begründung steht in Kapitel 4 der Masterarbeit
(Abschnitt „Architecture Decision Records“), die empirische Herleitung der
Parameter in Kapitel 5 und in `eval/PROTOKOLL.md`.

## 1. Schichten und Regeln

| Schicht | Ort | Aufgabe |
|---|---|---|
| Pipeline | `app/pipeline/step1_formalization` bis `step4_export` | Vier voneinander unabhängige, einzeln testbare Verarbeitungsschritte |
| Services | `app/services/` | Orchestrierung der Schritte, Zustand von KQR, Jobs und Mappings (Datei-Store unter `data/`) |
| API | `app/api/` | FastAPI-Routen als dünne Schicht über den Services, keine eigene Geschäftslogik |
| UI | `frontend/` | React/TypeScript-SPA, spricht ausschließlich mit der API |
| Graph | `app/graph/neo4j_client.py` | Optionale Materialisierung in Neo4j mit n10s (ADR-5) |

Regeln, die für Änderungen gelten:

- **Pipeline-Isolation:** Die Schritte importieren einander nicht. Die
  Verbindung entsteht ausschließlich in `app/services/`.
- **Schema-zentrierte Schnittstellen:** Daten an Modulgrenzen laufen über die
  Pydantic-Modelle in `app/models/schemas.py`, nicht über rohe Dicts.
- **Provenance:** Jedes Mapping trägt `mapping_tool`, `mapping_date`,
  `mapping_justification` und `mapping_confidence`. Entscheidungen werden
  nicht stillschweigend überschrieben.
- **Projekt-Isolation (ADR-13):** Pfade für Mappings, Jobs und Ausgaben
  entstehen über `project_service.get_project_data_dir(project_id)`.
- **Neo4j optional (ADR-5):** API und Tests laufen ohne Datenbank, Neo4j-Aufrufe
  sind gekapselt und werfen nicht.
- **Frontend spiegelt Backend-Regeln:** Export-Readiness, Konfidenzschwelle und
  Paar-Metriken kommen aus der API. Fehlende Information wird in
  `frontend/README.md` als API-Lücke dokumentiert.

## 2. Parameter der Lieferung v0.4

Die Werte stammen aus `app/config.py` und aus
`data/deliverables/v0.4-20261004/run_config.json`.

| Parameter | Wert | Quelle und Herleitung |
|---|---|---|
| Embedding-Modell | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | ADR-6 |
| ANN k | 20 | E1 (`eval/E1_recall_k.py`), `eval/PROTOKOLL.md` |
| Klassifikations-LLM | `mistral-small-2603` über `LLM_PROVIDERS=mistral` | `run_config.json`, ADR-7 und ADR-12 |
| Temperatur | 0 | `run_config.json` |
| Läufe je Paar | 3, Mehrheitsentscheid | ADR-12 |
| Few-Shot-Beispiele | 0 (Primärkonfiguration der Lieferung v0.4) | `run_config.json`, Ablation E2 in `eval/PROTOKOLL.md` und `eval/results/rerun_2026-10/` |
| Confidence-Schwelle | 0,33 | E3-Neukalibrierung, `eval/results/E3_neukalibrierung.json` |
| HDBSCAN `min_cluster_size` | 3, Negativbefund | E4, lief auf dem 956er-Ausschnitt (`eval/E4_hdbscan.py`) |
| Prompt-Template | `prompts/classification_prompt_template.txt` | SHA-256 (gekürzt) in `run_config.json`; Vorgängerfassung als `*.pre-revision.txt` |

Der Standardwert von `LLM_PROVIDERS` in `app/config.py` ist `anthropic`,
`.env.example` setzt `mistral`. Die Lieferung v0.4 entstand mit Mistral.

## 3. Architecture Decision Records

Mit „Abw.“ gekennzeichnete Einträge weichen von der Konzeption in Kapitel 3 ab.
ADR-16 bis ADR-18 sind nur in diesem Repo dokumentiert, die ADR-Tabelle der
Arbeit führt sie nicht auf.

| ADR | Entscheidung | Begründung, Alternativen |
|---|---|---|
| 1 | Python 3.11+ | Bibliotheken für NLP, ML und RDF. Alt.: Java, Kotlin |
| 2 | FastAPI | Asynchron, OpenAPI, Pydantic. Alt.: Flask, Django |
| 3 | Neo4j 5 + Neosemantics (n10s) | Turtle-Direktimport. Alt.: Apache Jena, Stardog |
| 4 | `faiss.IndexFlatIP` statt Neo4j-Vektorindex (Abw.) | Exakte Suche ohne HNSW-Parameter, Schritt 2 ohne Datenbank testbar |
| 5 | Neo4j nur als optionale Materialisierung (Abw.) | API und Tests ohne erreichbare Datenbank |
| 6 | Embedding-Modell `paraphrase-multilingual-mpnet-base-v2` | Mehrsprachig, keine Instruktions-Vorverarbeitung, lokal. Alt.: `text-embedding-3-large`, `multilingual-e5-large-instruct` |
| 7 | Provider-agnostische LLM-Abstraktion (`LLMProvider`) | Anbieterwechsel ohne Änderung am Klassifikationscode |
| 8 | `rdflib` | Turtle, RDF/XML, JSON-LD, SKOS und OWL. Alt.: `owlready2` |
| 9 | Pydantic v2 an Modulgrenzen | Validierung und gemeinsames Schema. Alt.: `dataclasses` |
| 10 | Datei-Store für KQR-Registry und Mappings | Keine zusätzliche Infrastruktur. Alt.: SQLite, PostgreSQL |
| 11 | e-CF 3.0 (CWA 16234-1:2014) statt e-CF 4.0 (Abw.) | 4.0 als kostenpflichtige Norm nicht verarbeitbar |
| 12 | Drei Läufe je Paar, ein oder mehrere Anbieter (Abw.) | Ausgleich des LLM-Nicht-Determinismus |
| 13 | Projekt als Isolationseinheit (Abw.) | Parallele Läufe ohne Überschreiben, `data/projects/{id}/` |
| 14 | ESCO-Berufs-URIs aus dem FAISS-Index ausgeschlossen | Die HR-QDE-Säulen arbeiten auf Skill-Ebene |
| 15 | React/TypeScript-SPA statt Streamlit (Abw.) | Master-Detail-Review über tausende Mappings, Navigation nach Funktionsgruppen |
| 16 | `CORSMiddleware`, Origins über `CORS_ALLOW_ORIGINS` | Die SPA ist ein eigener Browser-Origin |
| 17 | `mapping_justification` (SEMAPV) statt `match_type`, Präfix `harm:` statt `hrqde:` | SSSOM verlangt den Slot, `hrqde:` bleibt dem Skelett vorbehalten |
| 18 | RELATED und fehlender Konsens als `review_status="open"` persistiert (Abw.) | Adressierbar über `PUT /mappings/{id}/review`, in der Coverage bilanziert |
| 19 | Coverage-Quote über K ∪ C_conf inklusive offener Reviews | Ein Nenner ohne offene Fälle meldet fälschlich 1,0 |
| 20 | Rollen über RDF-Typen, Shortcut-Prädikate aus `data/structural_shortcut_predicates.json` | Verarbeitungsweg aus Daten statt aus Code lesbar, rollengleiches Pairing |
| 21 | Scope-Parameter je Projekt (`all`, `container_only`, `leaf_only`, `level_only`) | Granularität ist eine Laufzeitentscheidung |
| 22 | e-CF-Dimension 3 als `harm:LevelConcept`-Schicht (`ecf_level`), Crosswalk als `harm:LevelMapping` | Vorgabe der HR-QDE-Shapes, SPARQL-traversierbar |
| 23 | Niveaus nicht neu prägen, `harm-dqr:` mit `owl:sameAs`, Referenz auf `hrqde:DQR1` bis `DQR8` | Das Skelett modelliert die Niveaus bereits |
| 24 | Drei getrennte Lieferartefakte | Auswertung ohne Doppelzählung |
| 25 | ESCO-Vergleichsmenge `esco-skeleton-for-oberhuber.ttl` (1302 Skills) | Verbindliche Referenz des HR-QDE, E4 lief noch auf dem 956er-Ausschnitt |
| 26 | `harm:HubMapping`, `harm:OccupationMapping`, `harm:LevelMapping` in einem `sssom:MappingSet`, `predicate_id` als IRI | Durch die Shapes erzwungen, String-Prädikate sind nicht traversierbar |
| 27 | Ein Relationsvokabular (`MappingPredicate`), `RelationType` nur schrittintern | Kein Schattenfeld, „kein Konsens“ ist keine semantische Relation |
