# Evaluation – Aufgabe für Claude Code

> **Ziel:** Alle fünf Experimente aus Kapitel 5 der Masterarbeit
> ausführen, Ergebnisse aufzeichnen und die Platzhalter (`\ldots`)
> in den zugehörigen LaTeX-Dateien automatisch befüllen.
>
> **Arbeitsverzeichnis:** Immer vom Repo-Root aus starten.
> **Python:** `.venv\Scripts\python.exe` (Windows-venv).
> **API:** Für E2 und E3 muss `uvicorn app.api.main:app` laufen.
> **LaTeX-Pfad:** Relativ zu `../Vorlage/chapters/chapter_5/`
> (OneDrive-Pfad aus `CLAUDE.md` ableiten, falls abweichend).

---

## Phase 0 – Voraussetzungen prüfen

Führe diese Checks als erstes aus. Bei Fehlern: beheben, nicht
weitermachen.

```bash
# 0a: Python-Version
.venv\Scripts\python.exe --version
# Erwartet: Python 3.10 oder neuer

# 0b: Wichtige Pakete
.venv\Scripts\python.exe -c "
import faiss, hdbscan, sentence_transformers
from sklearn.metrics import silhouette_score
from rdflib import Graph
print('Alle Pakete vorhanden.')
"

# 0c: KQR-Status (alle benötigten KQR müssen Status 'bereit' haben)
.venv\Scripts\python.exe -c "
from app.services import kqr_service
for kqr in kqr_service.list_kqr():
    print(f'{kqr.id:<20} {kqr.status:<15} concepts={kqr.concept_count}')
"
# Benötigt: esco_ict, ecf -- beide 'bereit'
# Optional für E1: elm (mit elm:relatedEscoSkill-Prädikaten)

# 0d: Vorhandene Klassifikationsergebnisse prüfen
.venv\Scripts\python.exe -c "
import json; from pathlib import Path
results = json.loads(Path('data/classification_results.json').read_text())
print(f'ClassificationResults: {len(results)} Paare gespeichert')
mappings = json.loads(Path('data/mappings.json').read_text())
print(f'Mappings (Menge K):    {len(mappings)} Einträge')
"
```

**Entscheidung nach 0c:**
- Fehlt `elm`: E1 läuft gegen G_struct aus `data/raw/ELM.rdf` direkt
  (Skript handhabt das). Kein Stopp nötig.
- Fehlt `esco_ict` oder `ecf`: API starten, KQR über
  `ui/pages/1_KQR_Auswahl.py` registrieren, dann neu prüfen.

---

## Phase 1 – E1: Recall@k (VH₁.₅)

Keine API nötig. Nur FAISS und gecachte Embeddings.

```bash
.venv\Scripts\python.exe eval\E1_recall_k.py \
  --k-values 5 10 15 20 30 \
  --elm-kqr-id elm \
  --esco-kqr-id esco_ict \
  --output eval/results/E1_recall_k.json
```

**Falls ELM nicht als KQR registriert ist** (elm-ID fehlt):
Das Skript lädt `data/raw/ELM.rdf` direkt. Starte es mit
`--elm-kqr-id` auf den tatsächlichen KQR-ID-Wert oder
passe den Fallback im Skript an.

**Nach Ausführung: Ausgabe lesen und Tabelle befüllen.**

```bash
.venv\Scripts\python.exe eval\E1_recall_k.py --report \
  --output eval/results/E1_recall_k.json
```

Trage die Werte in die LaTeX-Tabelle ein:

```
Datei: chapters/chapter_5/exp1_recall_k.tex
Tabelle: tab:exp1_recall_k
Schema:  k | Recall@k | Neu gefundene Paare | Kumulativ
```

Ersetze jede `\ldots`-Zeile durch den tatsächlichen Wert aus dem
JSON-Feld `results[i]["recall"]`, `results[i]["new_found"]`,
`results[i]["found"]`.

Füge nach der Tabelle ein:
```latex
% k* = X (Recall@k >= 0.90 erstmals erreicht bei k=X)
```
Und passe den Fließtext im `\paragraph{Interpretation}`-Block
entsprechend an.

---

## Phase 2 – G_manual aufbauen (Goldstandard für E2/E3)

### 2a: Review-CSV erzeugen

```bash
.venv\Scripts\python.exe eval\build_gold_manual.py \
  --kqr-a ecf \
  --kqr-b esco_ict
```

Ausgabe: `eval/gold/G_manual_review.csv`
Öffne die CSV und befülle die Spalte `gold_relation`.

### 2b: Semi-automatische Annotation (Claude Code kann das übernehmen)

Wenn keine manuellen Labels vorliegen, verwende diesen Ansatz:
Lese `eval/gold/G_manual_review.csv`. Für jede Zeile mit leerem
`gold_relation`-Feld: Beurteile die Relation anhand von
`subject_label` und `object_label` eigenständig nach diesen Regeln:

| Kriterium | Relation |
|---|---|
| Nahezu identische Bezeichnung, gleicher Bedeutungsumfang | `EQUIVALENT` |
| Subject ist Oberbegriff von Object | `A_SUBSUMES_B` |
| Object ist Oberbegriff von Subject | `B_SUBSUMES_A` |
| Verwandt, aber kein klares Subsumtionsverhältnis | `RELATED` |

Schreibe die Labels in die CSV-Spalte `gold_relation` und setze
in `comment` eine kurze Begründung (max. 1 Satz).

Stelle sicher, dass die Verteilung annähernd balanciert ist:
je 20 Paare pro Klasse (Abweichung ±3 ist akzeptabel).

### 2c: G_manual finalisieren

```bash
.venv\Scripts\python.exe eval\build_gold_manual.py --finalize \
  --review eval/gold/G_manual_review.csv \
  --output eval/gold/G_manual.json
```

Erwartete Ausgabe:
```
G_manual: 80 Paare (0 übersprungen)
  EQUIVALENT:   20
  A_SUBSUMES_B: 20
  B_SUBSUMES_A: 20
  RELATED:      20
```

Falls die Verteilung unbalanciert ist (mehr als ±5 von 20):
Prüfe die CSV und korrigiere einzelne Labels, dann nochmals
finalisieren.

---

## Phase 3 – E2: Few-Shot-Ablation (VH₁.₆)

Benötigt: laufende API (`uvicorn app.api.main:app --reload`)

```bash
.venv\Scripts\python.exe eval\E2_few_shot.py \
  --gold eval/gold/G_manual.json \
  --n-fs-values 0 1 3 5 \
  --output eval/results/E2_few_shot.json
```

Laufzeit: ca. 80 × 4 × 3 = 960 LLM-Aufrufe (3 Läufe × 4 n_FS-Werte).
Fortschrittsanzeige: je Paar ein Punkt (`.`).

```bash
.venv\Scripts\python.exe eval\E2_few_shot.py --report \
  --output eval/results/E2_few_shot.json
```

**Tabelle befüllen:**

```
Datei: chapters/chapter_5/exp2_few_shot.tex
Tabelle: tab:exp2_few_shot
Schema:  n_FS | F1[EQUIV] | F1[SUBS] | F1[REL] | Macro-F1 | Acc.
```

Quelle: `results[i]["per_class"]` und `results[i]["macro_f1"]`.
F1[SUBS] = Mittelwert aus F1[A_SUBSUMES_B] und F1[B_SUBSUMES_A].

Optimales n_FS* aus dem Report ablesen und im Fließtext
(`\paragraph{Interpretation}`) einsetzen.

---

## Phase 4 – E3: Confidence-Schwellen (VH₁.₇)

Benötigt: laufende API, G_manual aus Phase 2.

```bash
.venv\Scripts\python.exe eval\E3_confidence.py \
  --gold eval/gold/G_manual.json \
  --output eval/results/E3_confidence.json
# n_FS wird automatisch aus E2-Ergebnis gelesen (n_FS*)
```

```bash
.venv\Scripts\python.exe eval\E3_confidence.py --report \
  --output eval/results/E3_confidence.json
```

**Tabelle befüllen:**

```
Datei: chapters/chapter_5/exp3_confidence.tex
Tabelle: tab:exp3_confidence
Schema:  θ | Precision | Recall | F1 | Übernommene Mappings
Zeilen:  0,33 / 0,67 / 1,00
```

Wähle θ_op (Precision-biased Empfehlung) aus dem Report und
aktualisiere `app/config.py`:

```python
# app/config.py – nach Auswertung anpassen:
mapping_confidence_threshold: float = X.XX  # θ_op aus E3
```

Dokumentiere die Änderung als Code-Kommentar:
`# empirisch bestimmt, E3 (Kapitel 5, Tab. tab:exp3_confidence)`

---

## Phase 5 – E4: HDBSCAN-Parametersweep (VH₂.₃)

Keine API nötig. Läuft lokal auf gecachten Embeddings.

```bash
.venv\Scripts\python.exe eval\E4_hdbscan.py \
  --m-values 3 5 8 10 15 \
  --output eval/results/E4_hdbscan.json
```

Laufzeit: ca. 2–10 min (abhängig von Gesamtkonzeptzahl).

```bash
.venv\Scripts\python.exe eval\E4_hdbscan.py --report \
  --output eval/results/E4_hdbscan.json
```

**Tabelle befüllen:**

```
Datei: chapters/chapter_5/exp4_hdbscan.tex
Tabelle: tab:exp4_hdbscan
Schema:  m | S | DB | Cluster-Anzahl | η
```

Quelle: `results[i]` mit Feldern `silhouette`, `davies_bouldin`,
`n_clusters`, `noise_rate`.

Wenn m* ≠ 5: `cluster_concepts()`-Defaultparameter in
`app/pipeline/step2_embedding_prefilter/clustering.py` anpassen:

```python
def cluster_concepts(
    embeddings: dict[str, np.ndarray],
    concept_lookup: dict[str, dict],
    min_cluster_size: int = X,  # m* aus E4 (empirisch bestimmt, Kap. 5)
```

---

## Phase 6 – E5: Kompetenzfragen-Evaluation (CQ₁–CQ₄)

### 6a: Ontologie exportieren

Stelle sicher, dass die API läuft und alle KQR klassifiziert wurden.

```bash
# Ontologie-Export via API
curl -s -X POST http://localhost:8000/export/ontology \
  -H "Content-Type: application/json" \
  -d "{\"format\": \"turtle\"}" \
  -o data/ontology/harmonised_ontology.ttl

# Alternativ: Streamlit-UI > Seite 5_Export.py > "OWL-Ontologie"
```

Prüfe den Export:
```bash
.venv\Scripts\python.exe -c "
from rdflib import Graph
g = Graph()
g.parse('data/ontology/harmonised_ontology.ttl', format='turtle')
print(f'Tripel: {len(g)}')
# Erwartet: > 500 Tripel
"
```

### 6b: Abfragen ausführen

```bash
.venv\Scripts\python.exe eval\E5_cq_evaluation.py \
  --ontology data/ontology/harmonised_ontology.ttl \
  --output eval/results/E5_cq_evaluation.json
```

```bash
.venv\Scripts\python.exe eval\E5_cq_evaluation.py --report \
  --output eval/results/E5_cq_evaluation.json
```

**Tabelle befüllen:**

```
Datei: chapters/chapter_5/cq_evaluation.tex
Tabelle: tab:exp5_cq_uebersicht
Schema:  CQ | Treffer | Erfüllt
```

Quelle: `results[i]["n_results"]` und `results[i]["fulfilled"]`.
"Erfüllt" = `JA` wenn `fulfilled == true`, sonst `NEIN`.

In den vier Unterabschnitten (CQ1–CQ4) ergänze nach dem
`\textit{Befund:}`-Placeholder:
- Tatsächliche Trefferzahl
- 1–2 konkrete Beispielpaare aus `results[i]["examples"]`
- 1 Satz Einschätzung (erfüllt / nicht erfüllt, warum)

---

## Phase 7 – LaTeX-Zusammenfassung aktualisieren

Nachdem alle fünf Experimente abgeschlossen sind, befülle die
VH-Abschlussstatus-Tabelle in der Summary.

```
Datei: chapters/chapter_5/summary.tex
Tabelle: tab:kap5_vh_abschluss
```

Ändere den Status jeder VH:
- `VH₁.₅`: Wert `\textbf{Geschlossen} (E1, Tab.~\ref{tab:exp1_recall_k})`
  bleibt. Füge dahinter in Klammern `$k^* = X$` ein.
- `VH₁.₆`: Ergänze `$n_{\mathrm{FS}}^* = X$`.
- `VH₁.₇`: Ergänze `$\theta^* = X{,}XX$`.
- `VH₂.₃`: Ergänze `$m^* = X$`.
- `CQ₁–CQ₄`: Ändere Status zu `\textbf{Erfüllt}` oder
  `\textit{Teilweise erfüllt}` je nach E5-Ergebnis.

---

## Phase 8 – Verifikation (Gesamtcheck)

```bash
# 8a: Alle JSON-Ergebnisse vorhanden?
.venv\Scripts\python.exe -c "
from pathlib import Path
files = [
    'eval/results/E1_recall_k.json',
    'eval/results/E2_few_shot.json',
    'eval/results/E3_confidence.json',
    'eval/results/E4_hdbscan.json',
    'eval/results/E5_cq_evaluation.json',
]
for f in files:
    p = Path(f)
    status = 'OK' if p.exists() else 'FEHLT'
    print(f'{status}  {f}')
"

# 8b: Keine \ldots mehr in den Ergebnistabellen?
grep -n '\\ldots' \
  ../Vorlage/chapters/chapter_5/exp1_recall_k.tex \
  ../Vorlage/chapters/chapter_5/exp2_few_shot.tex \
  ../Vorlage/chapters/chapter_5/exp3_confidence.tex \
  ../Vorlage/chapters/chapter_5/exp4_hdbscan.tex \
  ../Vorlage/chapters/chapter_5/cq_evaluation.tex \
  ../Vorlage/chapters/chapter_5/summary.tex
# Erwartung: keine Ausgabe (alle Platzhalter ersetzt)

# 8c: LaTeX kompilierbar?
cd ..\Vorlage
latexmk -pdf -interaction=nonstopmode thesis.tex 2>&1 | tail -5
cd ..\hrqde-harmonizer
```

---

## Fehlerbehebung

| Problem | Ursache | Lösung |
|---|---|---|
| `KeyError: 'elm'` in E1 | ELM nicht registriert | Skript liest ELM.rdf direkt – prüfe Pfad `data/raw/ELM.rdf` |
| `No module named faiss` | FAISS nicht installiert | `.venv\Scripts\pip install faiss-cpu` |
| `No module named hdbscan` | HDBSCAN fehlt | `.venv\Scripts\pip install hdbscan` |
| E2/E3 hängen | API nicht erreichbar | `uvicorn app.api.main:app --reload` in separatem Terminal |
| E5: 0 Tripel | Ontologie leer | Export prüfen; OWL-Pfad in `export_ontology()` verifizieren |
| LaTeX-Kompilierfehler | Sonderzeichen in Ergebnis | Dezimaltrennzeichen: Komma statt Punkt (`0{,}67` in LaTeX) |

---

## Aufzeichnungspflicht

Nach jeder Phase: Fasse in 2–3 Sätzen zusammen, was das Ergebnis
ist und ob eine Parameterkorrektur vorgenommen wurde. Schreibe das
in eine Datei `eval/PROTOKOLL.md`:

```markdown
## E1 – Recall@k
- k=20: Recall=0.XXXX (>= 0.90: JA/NEIN)
- k* = X → config.py nicht geändert / auf X gesetzt
- Datum: YYYY-MM-DD

## E2 – Few-Shot
...
```

Dieses Protokoll entspricht dem `oberhuber-protokoll-v{version}.md`
aus der Lieferspezifikation und belegt die methodische Sorgfalt.
