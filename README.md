# HR-QDE Harmonizer

Prototyp zur Masterarbeit „Harmonisierung von Kompetenz- und
Qualifikationsrahmenwerken im HR-QDE-Ökosystem“ (FernUniversität in Hagen,
Säule D). Die Pipeline vergleicht Kompetenz- und Qualifikationsrahmenwerke
(KQR) mit ESCO als Hub und erzeugt die Lieferartefakte für das
HR-QDE-Gesamtsystem: eine harmonisierte Ontologie, SSSOM-Mappings und eine
Integrationsstrategie für Konzepte ohne Entsprechung.

**Stand:** Übergabestand (Oktober 2026). Die aktuelle Lieferung v0.4 liegt
unter `data/deliverables/v0.4-20261004/`. Architekturentscheidungen
(ADR-1 bis ADR-27) und die Parameter der Lieferung stehen in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), Domänenbegriffe und offene
Punkte in [`CLAUDE.md`](CLAUDE.md), die Experimente in
[`eval/README.md`](eval/README.md).

## Pipeline

```
Schritt 1  Formalisierung        KQR-Quelle (RDF, Turtle, PDF) -> SKOS/Turtle
Schritt 2  Embedding/Vorfilter   Sentence-Embeddings, Struktur-Shortcut,
                                 FAISS-ANN-Suche -> Kandidatenpaare
Schritt 3  Klassifikation        LLM, drei Durchläufe, Mehrheitsentscheid
Schritt 4  Export                SSSOM (TTL/TSV), OWL-Ontologie,
                                 Integrationsstrategie, optional Neo4j (n10s)
```

Die Kernstruktur-Ableitung per HDBSCAN (`clustering.py`) ist implementiert,
liefert für den Skill-Raum aber keine navigierbare Hierarchie
(Negativbefund, siehe Kapitel 5 und 6 der Arbeit sowie `CLAUDE.md`, Abschnitt 7).

## Tech-Stack

| Bereich | Wahl |
|---|---|
| Backend | Python 3.11+, FastAPI |
| Persistenz | Datei-Store unter `data/` (ADR-5), Neo4j 5 + n10s optional |
| Embeddings | sentence-transformers, `paraphrase-multilingual-mpnet-base-v2` |
| ANN-Suche | FAISS |
| Klassifikation | Anthropic, OpenAI, Gemini oder Mistral über `LLM_PROVIDERS` (v0.4: `mistral-small-2603`, T = 0) |
| Clustering | hdbscan |
| RDF/SHACL | rdflib, pyshacl |
| UI | React/TypeScript-SPA unter `frontend/` (Vite) |

## Setup

```bash
# 1. Virtuelle Umgebung
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Abhängigkeiten
pip install -r requirements.txt

# 3. Neo4j + Neosemantics starten (optional)
docker compose up -d

# 4. Umgebungsvariablen setzen
cp .env.example .env
# .env editieren: LLM_PROVIDERS und den API-Schlüssel des gewählten
# Providers (zwingend für Schritt 3), NEO4J_PASSWORD (optional)

# 5. API starten
uvicorn app.api.main:app --reload

# 6. Review-UI starten (separates Terminal, React/Vite auf Port 5173)
cd frontend
npm install
npm run dev

# 7. Tests laufen ohne Netzwerk und ohne Neo4j (LLM und Embedding-Modell gemockt)
pytest                       # Backend
cd frontend && npm run test  # Frontend
```

Die React-Oberfläche ist die primäre UI. Setup, Routen und dokumentierte
API-Einschränkungen stehen in [`frontend/README.md`](frontend/README.md).
Sie greift als eigener Browser-Origin auf die API zu, die zugelassenen
Origins stehen in `CORS_ALLOW_ORIGINS` (`.env`, Standard
`http://localhost:5173`).

Ohne API-Schlüssel lassen sich KQR einpflegen und die UI durchklicken.
Schritt 3 schlägt dann beim Start fehl, was `GET /classification/preconditions`
vorab als Statuszeile anzeigt.

Stand Oktober 2026 umfasst die Backend-Suite 235 Tests (223 bestanden,
12 übersprungen). Fehlen optionale Experimentdaten wie die
Granularitätsvarianten unter `data/formalized/`, überspringen die
betroffenen Tests, statt fehlzuschlagen.

## Daten

| Ort | Inhalt | Versioniert |
|---|---|---|
| `data/formalized/` | formalisierte KQR der Lieferung (siehe unten) | ja |
| `data/deliverables/` | Snapshot der Lieferung v0.4 | ja |
| `data/raw/` | Originalquellen (u. a. e-CF-PDF, ESCO-Dump) | nein, Lizenz bzw. Größe |
| `data/projects/`, `data/kqr_registry.json` | Laufzeitzustand | nein |

Versioniert sind die vier KQR der Lieferung v0.4:
`esco_skeleton_oberhuber.ttl` (Hub, 1302 Skills des Informatik-Korridors),
`ecf.ttl` (e-CF 3.0, Dimension 2), `ecf_level.ttl` (e-CF 3.0, Dimension 3)
und `dqr_1D.ttl` (DQR-Niveaus). Hinzu kommen die Experimentdaten aus
Kapitel 5: die Granularitätsvarianten `dqr_2D.ttl`, `eqf_1D.ttl` und
`eqf_2D.ttl` sowie der frühere ESCO-Ausschnitt
`esco_v1_2_ict_ausschnitt.ttl` (956 Konzepte). Wie sie aus den Rohquellen entstanden sind,
dokumentieren die nummerierten Skripte `scripts/00` bis `scripts/22`. Die
e-CF-Formalisierung lief LLM-gestützt mit manueller Kuration und ist daher
nicht deterministisch reproduzierbar.

### Hinweis zum European e-Competence Framework (e-CF)

Die Dateien `data/formalized/ecf.ttl` und `data/formalized/ecf_level.ttl`
sowie die daraus erzeugten Lieferartefakte unter `data/deliverables/`
beruhen auf dem kostenlos veröffentlichten Dokument „European
e-Competence Framework (e-CF) Version 3.0 (CWA 16234-1:2014)“. Sie
enthalten eine abgeleitete, maschinenlesbare Darstellung (SKOS/Turtle) der
e-CF-Kompetenzen (Dimension 2) und ihrer Kompetenzniveaus (Dimension 3),
die im Rahmen dieser Masterarbeit erstellt wurde. Da die Formalisierung
LLM-gestützt erfolgte, kann sie vom Originaldokument abweichen. Maßgeblich
ist allein der veröffentlichte Text.

Auch die normative Zuordnung der e-CF-Kompetenzniveaus zu DQR- bzw.
EQF-Niveaus (`harm:LevelMapping`, Goldmenge `eval/G_levels.json`) stammt
aus e-CF 3.0 (CWA 16234-1:2014).

Dieses Repository und die enthaltenen Artefakte stehen in keinerlei
offizieller Verbindung zum Europäischen Komitee für Normung (CEN). Sie
wurden von CEN weder geprüft noch autorisiert. Die Rechte am e-CF
verbleiben bei den jeweiligen Rechteinhabern.

## Lieferung reproduzieren

1. API starten und die vier KQR über die UI oder `POST /kqr/` registrieren:
   `esco_skeleton_oberhuber` (Hub), `ecf`, `ecf_level`, `dqr_1d`.
2. `python scripts/run_saeule_d_delivery.py --plan-only` zur Kontrolle,
   danach mit `--version <V>` für den vollen Lauf.
3. Ergebnis unter `data/projects/<id>/delivery/`, inklusive
   SHACL-Validierung gegen die Bezugsdokumente im Repo-Root. Eine Kopie samt
   `run_config.json` landet unter `data/deliverables/v<V>-<JJJJMMTT>/`.

## Ordnerstruktur

```
app/            Backend: models, pipeline (step1 bis step4), graph, api, services
frontend/       React-SPA, siehe frontend/README.md
data/           siehe Abschnitt Daten
scripts/        Datenaufbau, Kapitel-5-Läufe, Lieferung
eval/           Experimente E1 bis E5, Baselines, Goldmengen, PROTOKOLL.md
prompts/        Klassifikations-Prompt-Template
tests/          Backend-Tests mit Fixtures
docs/           ARCHITECTURE.md (ADRs, Parameter)
```

Bezugsdokumente von Adrian Vogler im Repo-Root:
`hrqde-harmonisation-schema.ttl`, `hrqde-shape-harmonisation.ttl`,
`hrqde-shapes-all.ttl` und `esco-skeleton-for-oberhuber.ttl`.
