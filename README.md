# HR-QDE Harmonizer — Prototyp

Prototypische Implementierung der in Kapitel 3 (Theoriebildung/Konzeption)
entworfenen Harmonisierungspipeline für Kompetenz-, Qualifikations- und
Berufsrahmenwerke (KQR). Dient der Umsetzung von FZ1.3, FZ2.3 und FZ3.3
(Systementwicklungs-Ziele) nach Nunamaker.

**Implementierungsstand:** Der **Pipeline-Kern** (Schritte 1–3: Formalisierung,
Embedding & Vorfilter, LLM-Klassifikation) sowie SSSOM-Export, API-Routes und
die React-SPA unter `frontend/` sind lauffähig implementiert und getestet.
Für Detailstand und offene Punkte siehe `CLAUDE.md` §10.

## Architekturüberblick

Die Pipeline setzt die dreistufige Harmonisierung aus Kapitel 3 um:

```
Schritt 1: Formalisierung        Schritt 2: Embedding & Vorfilter        Schritt 3: Pair-Matching & Klassifikation
------------------------        ---------------------------------       -------------------------------------------
PDF/RDF/Turtle-KQR                Sentence-Embeddings je Konzept          LLM klassifiziert Kandidatenpaare
     |                                    |                                     |
     v                                    v                                     v
skos:ConceptScheme (Turtle)  -->  Struktur-Shortcut (regelbasiert)   -->  3x Majority-Vote (EQUIVALENT /
                                   + FAISS-ANN-Suche -> Kandidatenpaare   A_SUBSUMES_B / B_SUBSUMES_A /
                                   Struktur-Treffer (confidence=1.0)      RELATED; kein Mehrheits-
                                   umgehen Schritt 3 (Shortcut-Pfad)      entscheid -> predicate_id=None)
                                                                                  |
                                                                                  v
                                                                         SSSOM-Export (TSV) + Neo4j (n10s,
                                                                         optional/best-effort) + React-SPA
```

Die HDBSCAN-Kernstruktur-Ableitung (FZ2.2, Cluster → `rdfs:subClassOf`-DAG)
ist konzeptionell der nächste Schritt nach der Klassifikation, aber in
diesem Ausbau noch nicht implementiert (`clustering.py` bleibt Stub).

## Tech-Stack

| Bereich | Wahl | Status |
|---|---|---|
| Backend | Python 3.11+, FastAPI | implementiert |
| Persistenz (KQR-Registry, Mappings, Jobs) | In-Prozess-/Datei-Store (`app/services/`) | implementiert; bewusste Abweichung von Neo4j-als-alleiniger-Datenhaltung (siehe unten) |
| Graph-Store | Neo4j 5.x + Neosemantics (n10s) | implementiert als **optionale** Materialisierung, kein Hard-Requirement für die API |
| ANN-Suche (Schritt 2) | FAISS | implementiert; bewusste Abweichung von der aktuellen Konzeptionstext-Fassung, die einen nativen Neo4j-Vektorindex vorsieht (siehe unten) |
| Embeddings | sentence-transformers (`paraphrase-multilingual-mpnet-base-v2`, Default) | implementiert; Modellwahl weiterhin vorläufig (VH1.4) |
| Clustering (FZ2.2) | hdbscan | **nicht implementiert** — `pipeline/step2_embedding_prefilter/clustering.py` bleibt Stub |
| LLM-Klassifikation | Anthropic SDK (Default: `claude-haiku-4-5-20251001`) | implementiert; Modellwahl weiterhin vorläufig (VH1.6) |
| RDF/SKOS-Handling | rdflib | implementiert (Parsing, Validierung) |
| PDF-Formalisierung | pypdf + Anthropic SDK | implementiert (Textextraktion + LLM-Entwurf, manuell zu validieren) |
| UI (Review-Oberfläche) | React/TypeScript-SPA (`frontend/`, Vite) | implementiert |

### Bewusste Abweichungen von der aktuellen Konzeptionstext-Fassung

- **FAISS statt nativem Neo4j-Vektorindex:** `fz12_formalisierung.tex` beschreibt
  einen nativen Neo4j-Vektorindex für die ANN-Suche ("ein separater
  FAISS-Index entfällt"). Diese Implementierung nutzt bewusst weiterhin
  FAISS, damit Schritt 2 ohne laufende Neo4j-Instanz unit-testbar bleibt
  (Architekturprinzip "Pipeline-Schritte sind unabhängig testbar").
- **Neo4j ist optionale Materialisierung, nicht die primäre Datenhaltung:**
  KQR-Registry, Mappings und Klassifikations-Jobs leben in einem
  In-Prozess-/Datei-Store (`app/services/kqr_service.py`,
  `mapping_service.py`, `classification_service.py`). Der Neo4j-Client
  (`app/graph/neo4j_client.py`) ist vollständig implementiert und wird
  best-effort beim KQR-Upload aufgerufen — ein nicht erreichbares Neo4j
  blockiert die API nicht.

## Setup

```bash
# 1. Virtuelle Umgebung
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Abhängigkeiten
pip install -r requirements.txt

# 3. Neo4j + Neosemantics starten (optional, siehe "Bewusste Abweichungen" oben)
docker compose up -d

# 4. Umgebungsvariablen setzen
cp .env.example .env
# .env editieren: ANTHROPIC_API_KEY (zwingend für Schritt 3), NEO4J_PASSWORD (optional)

# 5. API starten
uvicorn app.api.main:app --reload

# 6. Review-UI starten (separates Terminal, React/Vite auf Port 5173)
cd frontend
npm install
npm run dev

# 7. Tests laufen ohne Netzwerk/Neo4j (LLM & Embedding-Modell sind gemockt)
pytest                       # Backend
cd frontend && npm run test  # Frontend
```

Die React-Oberfläche unter `frontend/` ist die primäre UI. Setup, Routen und
dokumentierte API-Einschränkungen stehen in [`frontend/README.md`](frontend/README.md).
Sie greift als eigener Browser-Origin auf die API zu; die zugelassenen Origins
stehen in `CORS_ALLOW_ORIGINS` (`.env`, Standard `http://localhost:5173`).

Ohne gesetzten `ANTHROPIC_API_KEY` lassen sich KQR einpflegen und die UI
durchklicken, aber Schritt 3 (Klassifikation) schlägt beim tatsächlichen
Start fehl — der Fehler wird über `GET /classification/preconditions`
(Statuszeile in Funktionsgruppe 2) vorab sichtbar gemacht, nicht erst beim
Absturz des Jobs.

## Ordnerstruktur

```
hrqde-harmonizer/
├── app/
│   ├── models/              # Pydantic-Schemas (Concept, KQR, Mapping, SSSOMRecord)
│   ├── pipeline/
│   │   ├── step1_formalization/       # KQR -> SKOS/Turtle (rdflib-Parsing, PDF via Anthropic)
│   │   ├── step2_embedding_prefilter/ # Embeddings (sentence-transformers), Struktur-Shortcut,
│   │   │                              # FAISS-ANN-Suche; clustering.py (FZ2.2) noch Stub
│   │   ├── step3_classification/      # LLM-Klassifikation, Majority-Vote
│   │   └── step4_export/              # SSSOM-Writer (implementiert); ontology_export.py (FZ2.2) noch Stub
│   ├── graph/                # Neo4j-Client (n10s-Import/-Konfiguration), optionale Materialisierung
│   ├── api/                  # FastAPI-Routen (dünne Schicht über services/)
│   └── services/             # Orchestrierung: kqr_service, classification_service, mapping_service
├── frontend/                 # React/TypeScript-SPA (primäre Review-UI), siehe frontend/README.md
├── data/
│   ├── raw/                  # Original-KQR-Quellen (hochgeladene Dateien)
│   ├── formalized/           # SKOS-Turtle je KQR nach Schritt 1
│   ├── sssom/                # Exportierte Mapping-Tabellen (TSV)
│   └── kqr_registry.json     # KQR-Registry-Metadaten (Status, concept_count, is_hub)
├── prompts/                  # Klassifikations-Prompt-Template (Vier-Block-Schema)
└── tests/
    ├── fixtures/              # Kleine, selbst erstellte SKOS-Turtle-Fixtures (Hub- + Satelliten-KQR)
    └── conftest.py            # Gemeinsame Test-Fixtures (Mock-LLM, Mock-Embedding-Modell, Service-Isolation)
```

## Zuordnung zu den Forschungszielen

| Forschungsziel | Modul | Status |
|---|---|---|
| FZ1.3 (Prototyp: 2 KQR verarbeiten, Teilmengen ausgeben) | `pipeline/step1_formalization`, `pipeline/step2_embedding_prefilter`, `pipeline/step3_classification` | implementiert |
| FZ2.3 (Kernstrukturen aus K erzeugen) | `pipeline/step2_embedding_prefilter/clustering.py` | **nicht implementiert** |
| FZ3.3 (Harmonisierungs-UI, Mixed Initiative) | `ui/` | implementiert (Seiten 1–4, Seite 5 teilweise) |
| FA1–FA5 (funktionale Anforderungen) | `app/api/routes/*`, `ui/pages/*` | FA1–FA4 implementiert; FA5 (Export) nur SSSOM-TSV, OWL-Export ausstehend |

## Implementierungsstand im Detail

**Implementiert und getestet** (siehe `tests/`, 31 Tests):

- Formalisierung: rdflib-Parsing/Validierung gegen die SKOS-Pflichtfelder,
  PDF-Formalisierung via pypdf + Anthropic (Entwurf, manuell zu validieren).
- Embedding (sentence-transformers) + regelbasierter Struktur-Vorfilter
  (bekannte KQR-Cross-Referenzen → direktes Mapping mit `confidence=1.0`,
  umgeht Schritt 3) + FAISS-ANN-Suche für die übrigen Kandidatenpaare.
- LLM-Klassifikation (Anthropic SDK, Dreifach-Klassifikation +
  Mehrheitsentscheid, strikte Antwortformat-Validierung).
- SSSOM-Export (TSV) inkl. Struktur-/Confidence-Filterregel.
- Neo4j-Client (n10s-Init, Turtle-Import, Status-Query) als optionale
  Materialisierung.
- API-Routes und React-SPA für alle 5 Funktionsgruppen.

**Bewusst nicht implementiert** (nächste Ausbaustufen):

- FZ2.2: HDBSCAN-Clustering der Konzepte im Embedding-Raum zu einer
  `rdfs:subClassOf`-Kernstruktur (DAG), inkl. zweistufiger Cluster-Benennung.
- FZ3.2: Experten-Entscheidungs-UI für disjunkte Konzepte ($C_{gap}$/$C_{conf}$,
  Optionen A/B/C). `GET /export/summary` zählt offene Fälle bereits
  (`no_consensus_pairs`, `related_pairs`; Gatekeeping-Anzeige).
- OWL-/Turtle-/JSON-LD-Ontologie-Export und Prüfbericht
  (`app/pipeline/step4_export/ontology_export.py`) — an die FZ2.2-Kernstruktur
  gekoppelt; die entsprechenden API-Routes liefern `501`.
- Optionaler Branchen-Filter (Ontology Views).
- `formalize_from_xml` (kein integriertes KQR benötigt aktuell den XML-Pfad).
