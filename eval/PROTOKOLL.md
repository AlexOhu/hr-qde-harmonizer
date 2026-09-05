# Evaluationsprotokoll (Kapitel 5)

Datum: 2026-07-29
Ausführendes System: Claude Code (Sonnet 5), im Rahmen von `eval/EVAL_TASK.md`.

Dieses Protokoll entspricht der Aufzeichnungspflicht aus
`eval/EVAL_TASK.md` und dokumentiert Ergebnisse, Abweichungen vom
ursprünglichen Plan sowie vorgenommene Code-Korrekturen.

---

## Vorbemerkung: Setup-Korrekturen vor Ausführung

Vor Beginn der eigentlichen Experimente wurden folgende Diskrepanzen
zwischen `eval/EVAL_TASK.md` und dem tatsächlichen Code-Stand
festgestellt und korrigiert:

1. **KQR-ID-Mismatch**: Die Aufgabe geht von `esco_ict` aus; registriert
   ist tatsächlich `esco_v1_2_ict_ausschnitt`. `elm` ist nicht als KQR
   registriert (nur `data/raw/ELM.rdf` liegt vor).
2. **`build_gold_manual.py` befüllte `subject_label`/`object_label` nie**
   (immer `""`), obwohl ein Kommentar Labelauflösung suggerierte.
   Behoben: Labels werden jetzt über `kqr_service` aufgelöst.
3. **`E2_few_shot.py` und `E3_confidence.py` riefen `classify_pair()`
   mit einer Signatur auf, die nicht mit der echten Funktion in
   `app/pipeline/step3_classification/classify.py` übereinstimmte**
   (fehlende `providers`, `runs_per_pair`; falsche Positionsparameter).
   Beide Skripte wären mit `TypeError` abgestürzt. Behoben durch
   Wiederverwendung von `get_providers_from_config()` und
   `settings.classification_runs_per_pair`, analog zu
   `app/services/classification_service.py::_run_job`.
4. **Windows-Konsolenencoding**: `E4_hdbscan.py` und `E3_confidence.py`
   stürzten beim Ausgeben von `η`/`θ` unter `cp1252` ab
   (`UnicodeEncodeError`). Workaround: Aufruf mit `PYTHONIOENCODING=utf-8`
   (keine Code-Änderung an den Skripten selbst nötig).
5. **Git-Sicherheitsnetz**: Weder `hrqde-harmonizer` noch das
   Thesis-Repo (`Vorlage`) standen unter Versionskontrolle. Beide wurden
   initialisiert und mit einem Baseline-Commit versehen, bevor
   produktiver Code oder LaTeX-Dateien verändert wurden.

---

## Phase 2 – G_manual (Goldstandard)

**Wichtiger Befund vor dem eigentlichen Goldstandard-Aufbau:**
Über sämtliche 4820 zum Startzeitpunkt gespeicherten
`ClassificationResult`-Objekte (alle KQR-Kombinationen: ecf↔esco,
dqr_2013↔esco, sowie Altbestände aus einer früheren KQR-Registrierung)
hat das Klassifikations-LLM **kein einziges Mal** `EQUIVALENT` oder
`A_SUBSUMES_B` vorhergesagt. Verteilung: `B_SUBSUMES_A: 3629,
RELATED: 843, UNRESOLVED: 348`. Das in `build_gold_manual.py`
vorgesehene Verfahren (Stichprobe je `model_relation`-Bucket, 20 pro
Klasse) kann unter dieser Verteilung strukturell niemals ein
balanciertes `G_manual` erzeugen — zwei der vier Buckets sind leer.

**Gewähltes Vorgehen** (in Abstimmung mit dem Nutzer): Statt nach
Modellvorhersage wurde nach der **wahren, unabhängig vom Modell
beurteilten Relation** gebucketet. Kandidatenpaare wurden aus dem
gesamten Pool klassifizierter ecf↔esco- und dqr_2013↔esco-Paare
gezogen (1540 Paare mit auflösbaren Labels), anhand von
Label-Ähnlichkeit vorsortiert und von Claude Code nach der
Kriterientabelle aus `EVAL_TASK.md` beurteilt.

**Ergebnis**: `G_manual` enthält **74 Paare** (nicht 80):

| Relation | Anzahl | Ziel | Abweichung |
|---|---|---|---|
| EQUIVALENT | 11 | 20 | −9 |
| A_SUBSUMES_B | 22 | 20 | +2 |
| B_SUBSUMES_A | 20 | 20 | 0 |
| RELATED | 21 | 20 | +1 |

**Befund/Limitation**: Echte `EQUIVALENT`-Relationen zwischen
e-CF-Kompetenzbereichen (Framework-Granularität, z. B. "Risk
Management") und ESCO-ICT-Skills (Skill-Granularität, z. B. "risk
management") sind inhärent selten — die beiden KQR operieren
überwiegend auf unterschiedlichen Abstraktionsebenen. Trotz erweiterter
Suche (Label-Jaccard-Ähnlichkeit über den gesamten Kandidatenpool)
konnten nur 11 belastbare Paare gefunden werden, ohne die
Bedeutung von "nahezu identische Bezeichnung, gleicher
Bedeutungsumfang" überzustrapazieren. Diese Differenz (11 statt 20)
wird als dokumentierte Limitation behandelt, nicht künstlich
aufgefüllt.

Für `B_SUBSUMES_A` wurde überwiegend die Lesart "ESCO-Berufsbild
verlangt/umfasst die jeweilige e-CF/DQR-Kompetenz als Teilanforderung"
verwendet (ESCO-Beruf als Objekt, ecf/dqr-Kompetenz als Subjekt) —
eine pragmatische, im Kommentarfeld je Zeile dokumentierte
Interpretation, da im untersuchten KQR-Paar echte Fälle von
"ESCO-Konzept ist im klassischen Ist-eine-Unterart-von-Sinn breiter
als e-CF/DQR" praktisch nicht vorkommen.

Datei: `eval/gold/G_manual.json` (74 Paare Ausgangs-CSV in
`eval/gold/G_manual_review.csv` mit Begründung je Zeile in Spalte
`comment`).

---

## E1 – Recall@k

**Architektur-Korrektur (Nutzerhinweis)**: ELM ist per ADR-14
(Kapitel 4) ausschließlich Serialisierungsziel des Ausgabe-Artefakts,
kein Vergleichs-KQR — es hält selbst keine mit ESCO vergleichbaren
Instanzen. Die ursprüngliche E1-Idee (Recall@k zwischen ELM- und
ESCO-Embeddings über `elm:relatedEscoSkill`) ist damit hinfällig,
nicht nur "ELM noch nicht registriert". E1 wurde daraufhin komplett
neu implementiert nach `eval/E1_spec.md` (separates Briefing),
mit zwei ELM-unabhängigen Goldmengen:

- `eval/G_struct.json`: 8 normative DQR↔EQF-Niveaupaare (German EQF
  Referencing Report 2012/2013).
- `eval/G_manual_seed.json`: 14 e-CF A.8↔ESCO-Skill-Paare aus
  Zare et al. (2025), Applied Sciences 15(17):9634, Table 6.

**URI-Auflösung** (Teilaufgabe 1 aus E1_spec.md):
- G_struct: EQF ist nicht formalisiert (kein `eqf.ttl`) → alle 8 Paare
  bleiben `PLACEHOLDER`, 0 evaluierbar.
- G_manual_seed: `subject_id` (K3/S4-Illustrationsbeispiele) haben in
  `ecf.ttl` keine eigene URI → auf e-CF A.8 (Elternkonzept) gesetzt,
  wie im Spec für diesen Fall vorgesehen. 9 von 14 ESCO-Objekt-Labels
  gegen `esco_v1_2_ict_ausschnitt` aufgelöst; 5 nicht gefunden. Von
  diesen 5 existieren 3 im vollständigen ESCO-Dump
  (`data/raw/esco-v1.2.1.ttl`), wurden aber durch den ICT-Filterschritt
  aus dem eingebetteten Korpus ausgeschlossen (Befund, nicht Bug); 1
  Label ist auch dort nicht auffindbar (vermutlich Paraphrase in
  Zare et al. statt wörtlichem ESCO-Label). Details in
  `eval/G_manual_seed.json` → `uri_lookup_log`.

**Ergebnis** (`eval/E1_recall_k.py`, neu implementiert, mit Unit-Tests
in `tests/test_e1_recall_k.py`):

| Goldmenge | evaluierbar | Recall@5 | Recall@10 | Recall@15/20/30 |
|---|---|---|---|---|
| G_struct (DQR↔EQF) | 0/8 | n/a | n/a | n/a |
| G_manual (e-CF A.8↔ESCO) | 9/14 | 0,667 | 1,000 | 1,000 |

- G_struct liefert mangels EQF-Formalisierung keine Aussage.
- G_manual erreicht Recall@10 = 1,000 (k\*=10 auf dieser kleinen,
  domänenspezifischen Stichprobe). Produktiver Wert `settings.ann_top_k
  = 20` wird als konservativerer, generalisierbarerer Wert beibehalten
  (n=9 ist keine querschnittliche Stichprobe über alle 41
  e-CF-Kompetenzen).
- `chapters/chapter_5/exp1_recall_k.tex` und `summary.tex` (VH₁.₅:
  "teilweise geschlossen") entsprechend befüllt.

---

## E2 – Few-Shot-Ablation

- Modell: `mistral-small-latest` (Provider Mistral AI,
  `LLM_PROVIDERS=mistral`), `temperature=0`, 3 Läufe/Paar (Mehrheitsentscheid).
- 74 Paare × 4 `n_FS`-Werte × 3 Läufe = 888 reale LLM-Aufrufe.

| n_FS | F1[EQ] | F1[SUBS] | F1[REL] | Macro-F1 | Acc. |
|---|---|---|---|---|---|
| 0 | 0,0000 | 0,2405 | 0,7778 | 0,3147 | 0,4459 |
| 1 | 0,1667 | 0,2500 | 0,7647 | 0,3578 | 0,4595 |
| 3 | 0,0000 | 0,2500 | 0,8000 | 0,3250 | 0,4595 |
| 5 | 0,0000 | 0,2375 | 0,7429 | 0,3045 | 0,4324 |

- **n_FS\* = 1** (Macro-F1 = 0,3578) → `prompts/classification_prompt_template.txt`
  unverändert (n_FS\* ≤ 3), Few-Shot-Anzahl auf 1 konfiguriert.
- Bestätigt die Richtungsverzerrung aus Phase 2: F1[EQUIV] ist bei
  n_FS ∈ {0,3,5} exakt 0 (Modell sagt praktisch nie `EQUIVALENT`
  voraus); F1[SUBS] bleibt durchgehend niedrig (~0,24), während
  F1[REL] hoch ist (~0,74–0,80).
- Datum: 2026-07-29

---

## E3 – Confidence-Schwellen

- `n_FS=1` (automatisch aus E2 übernommen). 74 reale LLM-Aufrufe (3 Läufe/Paar).

| θ | Precision | Recall | F1 | Übernommene Mappings |
|---|---|---|---|---|
| 0,33 | 0,8667 | 0,9811 | 0,9204 | 60 |
| 0,67 | 0,9057 | 0,9057 | 0,9057 | 53 |
| 1,00 | 0,9057 | 0,9057 | 0,9057 | 53 |

- θ\* (F1-Optimum) = 0,33; **θ_op (Precision-biased, gewählt) = 0,67**.
- `app/config.py` und `.env`/`.env.example`:
  `mapping_confidence_threshold` von 0,40 auf **0,67** gesetzt.
- Hinweis: P/R hier messen nur grobe K-Mitgliedschaft
  (`EQUIVALENT`/`A_SUBSUMES_B`/`B_SUBSUMES_A` vs. `RELATED`), nicht
  die exakte Relationsklasse — daher deutlich höher als der
  klassenweise Macro-F1 aus E2.
- Datum: 2026-07-29

---

## E4 – HDBSCAN-Parametersweep

- 1033 Konzepte (esco_v1_2_ict_ausschnitt: 956, ecf: 45, dqr_2013: 32).

| m | S | DB | Cluster | η |
|---|---|---|---|---|
| 3 | 0,0380 | 1,4777 | 4 | 28,75 % |
| 5 | 0,0814 | 1,8834 | 2 | 43,56 % |
| 8 | 0,1029 | 1,8783 | 3 | 63,99 % |
| 10 | 0,0994 | 1,8629 | 2 | 59,05 % |
| 15 | 0,0960 | 1,7939 | 2 | 65,44 % |

- **Kein getesteter Wert erfüllt η < 0,20.**
- m\* = 3 gewählt (bester Kompromiss: niedrigste Noise-Rate, bester
  DB-Index, wenn auch nicht bester Silhouette-Wert).
- `min_cluster_size`-Default in
  `app/pipeline/step2_embedding_prefilter/clustering.py` und
  `app/services/ontology_service.py::run_clustering` von 5 auf **3**
  geändert.
- Interpretation: Durchgehend schwache Silhouette-Werte (≤ 0,103)
  deuten auf eine insgesamt schwache Clusterstruktur hin, vermutlich
  Folge der starken Größenasymmetrie der drei KQR (956 vs. 45 vs. 32).
  Als offene Limitation dokumentiert.
- Datum: 2026-07-29

---

## E5 – Kompetenzfragen-Evaluation

**Vorgelagerter Befund**: `export_ontology()`
(`app/pipeline/step4_export/ontology_export.py`) emittierte bislang
weder `skos:prefLabel` noch `rdf:type hrqde:HarmonisedConcept` noch
`hrqde:integrationStrategy` noch Sprachtags auf Label-Literalen —
alle vier CQ-SPARQL-Abfragen hätten dadurch strukturell immer 0
Treffer geliefert, unabhängig von der Datenqualität. Behoben:

- `export_ontology()` erhält neuen Parameter `disjoint_decisions` und
  schreibt je referenziertem Konzept `skos:prefLabel` (Sprache "en")
  + `rdf:type hrqde:HarmonisedConcept`, sowie je Disjoint-Entscheidung
  `hrqde:integrationStrategy`.
- Cluster-`rdfs:label` erhält ebenfalls Sprachtag "en" (nicht "de" wie
  ursprünglich in CQ4 vorgesehen — alle drei KQR-Quellen liegen nach
  Formalisierung ausschließlich englisch vor, vgl.
  `scripts/12_dqr_translate_en.py`). CQ4-Sprachfilter in
  `E5_cq_evaluation.py` und `cq_evaluation.tex` entsprechend von "de"
  auf "en" korrigiert.
- API-Route `/export/ontology` reicht jetzt `disjoint_service.list_decisions()`
  durch.
- `tests/test_ontology_export.py` aktualisiert (neuer Fixture-Parameter,
  zwei neue Tests für prefLabel/HarmonisedConcept/integrationStrategy).
  Vollständige Testsuite (65 Tests) läuft grün.
- Vor dieser Runde lagen **0** Disjoint-Entscheidungen vor (491
  disjunkte ESCO-Konzepte ohne Entscheidung). Für die Evaluation wurden
  alle 491 automatisiert per `suggest_strategy()` entschieden (Autor
  `eval_e5_automated`, Begründung dokumentiert) — **keine manuelle
  Einzelprüfung**, siehe Limitation unten.
- Clustering neu ausgeführt mit m=3 (s. E4): 4 Cluster + Noise.
- Export: `data/ontology/harmonised_ontology.ttl`, **7994 Tripel**.

| CQ | Treffer | Erfüllt |
|---|---|---|
| CQ1 (exactMatch) | 0 | NEIN |
| CQ2 (narrowMatch e-CF→ESCO) | 732 | JA |
| CQ3 (disjunkt, integrationStrategy) | 491 | JA |
| CQ4 (subClassOf+, Cluster-Hierarchie) | 0 | NEIN |

- CQ1 scheitert nicht an der Ontologie-Struktur, sondern an der in E2
  dokumentierten Klassifikationsverzerrung (nie `EQUIVALENT`).
- CQ4 scheitert daran, dass der m=3-Kondensationsbaum nur 4 flache
  Top-Level-Cluster ohne Verschachtelung erzeugt (0
  `rdfs:subClassOf`-Kanten zwischen Cluster-URIs) — direkte Konsequenz
  der in E4 dokumentierten schwachen Clusterstruktur.
- **Status: 2/4 CQ erfüllt ("teilweise erfüllt"), nicht alle 4 wie
  ursprünglich in `summary.tex` vorgesehen.**
- Datum: 2026-07-29

---

## Phase 7 – LaTeX-Summary

`chapters/chapter_5/summary.tex` aktualisiert:
- VH₁.₅: **offen** (E1 nicht ausgeführt), statt der zuvor
  bereits (verfrüht, ohne reale Werte) auf "Geschlossen" gesetzten
  Zeile.
- VH₁.₆: geschlossen, n_FS\* = 1.
- VH₁.₇: geschlossen, θ_op = 0,67.
- VH₂.₃: geschlossen *als Randbedingung* (η<0,20 von keinem m erreicht), m\* = 3.
- CQ₁–CQ₄: *teilweise erfüllt* (CQ2, CQ3 ja; CQ1, CQ4 nein), statt
  pauschal "geschlossen".

---

## Nicht von dieser Sitzung verursacht (zur Information)

Während der Bearbeitung wurden in `../Vorlage` drei Dateien
(`chapters/chapter_2/kqr/elm.tex`, `chapters/chapter_3/infm.tex`,
`chapters/chapter_4/architektur.tex`) durch einen anderen Prozess
verändert (Zeitstempel ~16:49–16:50, kurz nach dem Baseline-Commit
16:45; diese Sitzung hat zu diesem Zeitpunkt nachweislich nur
Python-Dateien im hrqde-harmonizer-Repo gelesen). Diese Änderungen
wurden **nicht committet und nicht angerührt** — vermutlich
zeitgleiche Bearbeitung durch den Nutzer oder OneDrive-Sync eines
anderen Geräts.

---

## Offene Punkte für Kapitel 6 (Conclusion) / Folgearbeiten

1. E1 (Recall@k) querschnittlich validieren: G_struct erst nach
   EQF-Formalisierung möglich; G_manual auf weitere e-CF-Kompetenzen
   ausweiten (Option B in `eval/G_manual_seed.json`), da die aktuellen
   n=9 nur den Green-ICT/Nachhaltigkeitsbereich abdecken.
2. Klassifikations-Richtungsverzerrung (nie `EQUIVALENT`, praktisch nie
   korrekt `A_SUBSUMES_B`) — Prompt-Design-Thema, nicht durch
   Few-Shot-Anzahl allein lösbar (vgl. E2).
2a. G_manual mit 11 statt 20 EQUIVALENT-Paaren — Limitation der
    Stichprobengröße für diese Klasse, thesis-seitig zu benennen.
3. HDBSCAN-Clusterstruktur bleibt schwach (η nie < 0,20) und flach
   (CQ4 nicht erfüllbar) — evtl. anderes Embedding-Modell oder
   Distanzmetrik für stark größenasymmetrische KQR-Kombinationen prüfen.
4. 491 Disjoint-Entscheidungen wurden automatisiert (nicht manuell)
   getroffen, um CQ3 zu evaluieren — vor Produktivbetrieb durch
   manuelle Review in Prototyp 6 ersetzen/bestätigen.

---

## Hopkins-Statistik (VH₂.₄, Ergänzung zu E4)

**Datum:** 2026-08-04
**Methode:** Hopkins-Statistik auf L2-normalisierten Vektoren (768d),
n_samples = max(50, n//10), random_state=42, scipy KDTree (euclidean).
Referenzpunkte uniform auf der Einheitshypersphäre (normalisierter Gauß).

**Ergebnis:** H = 0.6493 (n=1065 Konzepte: 956 ESCO + 45 e-CF + 32 DQR +
32 EQF; n_samples=max(50, n//10)=106)

**Interpretation:** H liegt zwischen den beiden im Plan definierten
Schwellenwerten (0.55 / 0.75) und fällt damit in die Zwischenkategorie
„schwaches Clustering-Signal". Der Embedding-Raum ist weder eindeutig
zufällig verteilt (H≈0.5) noch klar geclustert (H≥0.75). Es besteht eine
messbare, aber schwache Tendenz zu Ballungen.

**Konsequenz für VH₂.₄:**
- H < 0.55: Bestätigt negativen Befund. Der Embedding-Raum hat keine
  Clustering-Tendenz; flache HDBSCAN-Topologie ist strukturell erklärbar.
- H >= 0.75: Widerspricht der bisherigen Interpretation. Clustering-Tendenz
  ist vorhanden, aber HDBSCAN mit Euclidean-Metrik auf der Hypersphäre
  konnte sie nicht erschließen. VH₂.₄-Interpretation in E4 und Kapitel 6
  muss entsprechend angepasst werden (Limitation betrifft dann Algorithmus/
  Metrik, nicht die Datenstruktur).
- **Tatsächlich (0.55 ≤ H < 0.75):** Zwischenbefund. Der Raum weist eine
  schwache, aber von reiner Zufallsverteilung unterscheidbare Struktur auf
  (H=0.6493 vs. H≈0.5 für Uniform-Referenz). Das erklärt, warum HDBSCAN
  überhaupt Cluster findet (m=3: 26 Cluster), aber die durchgehend hohe
  Noise-Rate (η nie < 0.20, siehe Sweep-Tabelle oben) zeigt, dass diese
  schwache Tendenz nicht ausreicht, um eine navigierbare, überschneidungsfreie
  Hierarchie zu erzeugen. VH₂.₄ bleibt damit ein offener Befund: nicht durch
  fehlende Datenstruktur erklärbar (H > 0.55), aber auch nicht stark genug
  für CQ4. Limitation für Kapitel 6: vermutlich eine Kombination aus
  Algorithmus/Metrik-Wahl und einer inhärent schwachen (nicht fehlenden)
  Cluster-Tendenz im kombinierten Embedding-Raum.

**Hinweis zur Konzeptanzahl:** Der Lauf ergab 1065 statt der in CLAUDE.md
Abschnitt 7 dokumentierten 1033 Konzepte (956+45+32). Ursache: `eqf_2017`
lud 32 statt der erwarteten 8 Niveau-Knoten. Dies deckt sich mit dem in
CLAUDE.md vermerkten offenen Punkt „EQF (8 Niveau-Knoten) muss nach
Serverneustart ggf. erneut in `kqr_registry.json` eingetragen werden" —
vermutlich ein veralteter/falsch reregistrierter EQF-Datensatz. Nicht Teil
dieses Hopkins-Plans; wird hier nur dokumentiert, nicht korrigiert.

---

### Korrektur: Konzeptanzahl auf 1033 zurückgeführt (2026-08-04)

**Ursachenanalyse:**
`data/formalized/eqf_2017.ttl` enthält tatsächlich und korrekt 32
SKOS-Konzepte (8 EQF-Niveau-Knoten × [`Level` + `Knowledge` + `Skills` +
`ResponsibilityAutonomy`] = 32) — kein Datenfehler, sondern die für die
E1-G_struct-Evaluation (DQR-Dimensionskonzepte ↔ EQF-Deskriptoren)
notwendige granulare Formalisierung. Die TTL-Datei war nicht die Ursache
und wurde nicht verändert.

Die eigentliche Ursache war ein Registrierungsproblem: `eqf_2017` fehlte
im zuletzt committeten `data/kqr_registry.json` vollständig
(`git diff HEAD` bestätigt den Eintrag als rein lokale, unkommittete
Ergänzung). Sein Status stand auf `bereit`, weil `kqr_service.get_embeddings()`
beim ersten Aufruf automatisch `formalisiert` → `bereit` hochstuft
(`app/services/kqr_service.py:209-210`) — ausgelöst als Nebeneffekt von
`eval/E1_recall_k.py::_load_all_embeddings()`, das `get_embeddings()`
unabhängig vom Status für alle registrierten KQR aufruft. `E4_hdbscan.py`
ist das einzige Skript, das beim Laden des Embedding-Raums strikt auf
`KQRStatus.BEREIT` filtert (`load_all_embeddings()`); dadurch flossen die
32 EQF-Konzepte unbeabsichtigt in den E4-Clustering-Raum ein, obwohl EQF
laut CLAUDE.md Abschnitt 7 dort nie vorgesehen war (dokumentierte Summe:
1033 = 956 + 45 + 32, ohne EQF). Der committete Baseline-Stand von
`eval/results/E4_hdbscan.json` (vor dieser Sitzung) bestätigt n_total=1033
als historisch korrekten Wert.

**Fix (kleinstmöglicher Eingriff):** In `data/kqr_registry.json` den
Status von `eqf_2017` von `"bereit"` auf `"formalisiert"` zurückgesetzt.
`eqf_2017` bleibt damit registriert und für `E1_recall_k.py`,
`E2_few_shot.py` und `build_gold_manual.py` weiter nutzbar (diese filtern
nicht nach Status), wird von `E4_hdbscan.py::load_all_embeddings()`
jetzt aber korrekt übersprungen. Keine Quelldaten (TTL) verändert.

**Verifikation:** `python eval/E4_hdbscan.py` gibt jetzt
`Gesamt: 1033 Konzepte im gemeinsamen Embedding-Raum` aus. Die
Sweep-Ergebnisse (m=3: S=0.038, DB=1.4777, 4 Cluster, η=28.75%; m=5, m=8
analog) stimmen exakt mit dem zuvor committeten Baseline-Ergebnis überein
— bestätigt, dass die Korrektur den historisch referenzierten Zustand
(Kapitel 5, Tabelle „Bestätigt (neg. Befund)") reproduziert.

**Korrigierter Hopkins-Wert:** H = 0.6490 (n=1033; zuvor H=0.6493 bei
n=1065 — die Differenz von 32 EQF-Punkten verändert den Wert nur
marginal, da EQF selbst keine ausgeprägte separate Ballung bildet).
Interpretation unverändert: schwaches Clustering-Signal
(0.55 ≤ H < 0.75).

**Vollständige Konsolenausgabe (`python eval/E4_hdbscan.py`):**

```
Lade kombinierte Embeddings ...
  'esco_v1_2_ict_ausschnitt': 956 Vektoren geladen
  'ecf': 45 Vektoren geladen
  'dqr_2013': 32 Vektoren geladen
  Überspringe 'eqf_2017' (Status: formalisiert)
Gesamt: 1033 Konzepte im gemeinsamen Embedding-Raum

Berechne Hopkins-Statistik ...
Hopkins H = 0.6490  → schwaches Clustering-Signal

m=3 ... S=0.0380  DB=1.4777  Cluster=4  η=28.75%
m=5 ... S=0.0814  DB=1.8834  Cluster=2  η=43.56%
m=8 ... S=0.1029  DB=1.8783  Cluster=3  η=63.99%
m=10 ... S=0.0994  DB=1.8629  Cluster=2  η=59.05%
m=15 ... S=0.0960  DB=1.7939  Cluster=2  η=65.44%

Hopkins H = 0.6490  (schwaches Signal)

--- E4: HDBSCAN-Parametersweep ---
   m   Silhouette   Davies-Bouldin  Cluster        η  Kriterium
--------------------------------------------------------------
   3       0.0380           1.4777        4   28.75%  ✗ η≥0.20
   5       0.0814           1.8834        2   43.56%  ✗ η≥0.20
   8       0.1029           1.8783        3   63.99%  ✗ η≥0.20
  10       0.0994           1.8629        2   59.05%  ✗ η≥0.20
  15       0.0960           1.7939        2   65.44%  ✗ η≥0.20

Kein m erfüllt η < 0.20. Grenzwert überdenken.
```


---

# Re-Run 2026-08-31 (aktueller Code + KQR-Daten + v0.3-Artefakt)

Ausfuehrendes System: Claude Code (Sonnet 5). Anlass: Kapitel 3/4 wurden um
`harm:conceptRole` (CompetenceConcept/LevelConcept), die Typ-1/Typ-2-Taxonomie,
Aggregationsknoten mit abgeleitetem `skos:broadMatch`
(`semapv:LogicalReasoning`), die 135 e-CF-Dimension-3-LevelMappings
(`semapv:ManualMappingCuration`) und ein neues Ontologie-Artefakt
(`oberhuber-harmonised-ontology-v0.3.ttl`) erweitert. Der
Klassifikationsprompt (`prompts/classification_prompt_template.txt`) wurde um
eine explizite Subsumtionsrichtungs- und EQUIVALENT-Definition ergaenzt.

## Abgestimmte Vorentscheidungen (mit Nutzer, vor den Laeufen)

| Punkt | Entscheidung |
|---|---|
| LLM-Provider/Modell E2/E3 | `mistral-small-latest` (`LLM_PROVIDERS=mistral`), identisch zum Lauf 2026-07-29. Vorbehalt: der `-latest`-Tag kann serverseitig verschoben sein -- als Stoervariable vermerkt. |
| E1 k-Wert | k=20 beibehalten (volle Abdeckung, CLAUDE.md Abschn. 6 unveraendert). |
| E4-Clusterraum | DQR zusaetzlich aus dem HDBSCAN-Raum entfernt (analog EQF): nur `harm:CompetenceConcept`-KQR, **1001** Konzepte (956 ESCO + 45 e-CF). |
| E5-Datenbasis | Frischer Export via `export_ontology()` aus Projekt "IKT Slice V0.7" (neuer Prompt, = v0.3-Seed) fuer CQ1-CQ4; v0.3-Artefakt separat fuer SHACL. |
| E2-Few-Shot-Pool | `eval/G_struct.json` (32 DQR<->EQF-Crosswalks) als Anker-Quelle (siehe E2 unten). |

## Setup-Korrekturen vor Ausfuehrung

1. **`eval/E2_few_shot.py::_few_shot_text_for_n_fs`** referenzierte `MatchType`
   / `Mapping.match_type` -- beide nach ADR-19 entfernt (`ImportError`). Der
   urspruengliche Anker-Pool (persistierte Struktur-Shortcut-Mappings) ist nicht
   mehr vorhanden; `find_structural_shortcuts()` liefert auf den aktuellen
   Formalisierungen 0 Treffer (Praedikate `esco:isPartOf` /
   `elm:relatedEscoSkill` fehlen). Neu: Anker werden aus `eval/G_struct.json`
   gebaut (normative DQR<->EQF-Crosswalk-Goldmenge). Deckt den Prompt-Wortlaut
   "aus der Crosswalk-Goldmenge (Schritt 2)" ab, deterministisch, 32 Paare
   (reicht fuer n_FS <= 5). **Methodische Abweichung vom Original**, dort waren
   die Anker e-CF/ESCO-naeher; Domain-Mismatch (Niveau- statt Kompetenzkonzepte)
   ist zu benennen.
2. **`eval/E4_hdbscan.py`** um eine explizite `--kqr-ids`-Allowlist ergaenzt
   (Default `esco_v1_2_ict_ausschnitt ecf`). `load_all_embeddings()` nahm bis
   dahin **alle** KQR mit Status `bereit`; `data/kqr_registry.json` enthaelt
   inzwischen zusaetzlich `dqr_2`, `dqr_3`, `eqf_2017` und zwei
   Walkthrough-Slices auf `bereit` -> Raum waere ~1324 statt 1033 gewesen. Die
   Allowlist macht den Sweep vom Registrierungsstand unabhaengig.
3. `scripts/17_ecf_add_dimension3.py` / `scripts/18_annotate_concept_roles.py`
   sind idempotent und bereits gelaufen: `ecf.ttl` traegt 40x
   `hrqde:proficiencyLevel` und 40x `harm:conceptRole harm:CompetenceConcept`,
   `esco_v1_2_ict_ausschnitt.ttl` 956x `harm:conceptRole`. `dqr_2013.ttl` traegt
   **keine** `conceptRole` (Skript 18 annotiert das separate `dqr_3.ttl`).

## E1 -- Recall@k

- Skript unveraendert. 3 Laeufe, deterministisch identisch, reproduzieren den
  Stand vom 2026-07-30 exakt.
- Kombinierter Embedding-Raum beim Lauf: 1237 Konzepte (alle registrierten
  KQR); die Recall-Messung sucht nur im Raum der Gold-Objekt-URIs, die
  Registry-Verschmutzung beeinflusst die Kennzahlen daher nicht.

| Goldmenge | evaluierbar | R@5 | R@10 | R@15 | R@20 | R@30 |
|---|---|---|---|---|---|---|
| G_struct (DQR<->EQF, 32 Dim.-Paare) | 32/32 | 0,844 | 0,906 | 0,938 | **1,000** | 1,000 |
| G_manual (e-CF A.8<->ESCO) | 9/14 | 0,667 | 1,000 | 1,000 | 1,000 | 1,000 |

- k* (erstes k mit Recall >= 0,90): G_struct k=10, G_manual k=10.
- **k=20 bleibt gesetzt** (Entscheidung): volle Abdeckung auf G_struct
  (Recall@20 = 1,00), konservativ gegenueber der kleinen G_manual-Stichprobe.
  CLAUDE.md Abschn. 6 unveraendert.
- **Vorbehalt (in den Thesistext):** G_struct bettet DQR- (`dqr_2`) und
  EQF-Niveaukonzepte nur zur Messung in den FAISS-Raum ein. Der Produktivpfad
  bettet `harm:LevelConcept`-Knoten nicht ein (Skelett-Import statt
  ANN/Matching). E1 misst hier also eine Eigenschaft des Embedding-Modells,
  nicht des Produktiv-Retrievals.
- alt (2026-07-29): G_struct 0/8 evaluierbar ("keine Aussage"); neu: 32/32,
  k=20 -> 1,00. `eval/results/E1_recall_k.json` (bereits vor dieser Sitzung neu
  befuellt) durch den Re-Run bestaetigt, `_meta` ergaenzt.
- Datum: 2026-08-31

## E4 -- HDBSCAN-Parametersweep + Hopkins

- Clusterraum **1001** (956 ESCO + 45 e-CF; DQR entfernt). 3 Laeufe,
  deterministisch identisch (HDBSCAN deterministisch, Hopkins random_state=42).

| m | Silhouette | Davies-Bouldin | Cluster | eta | Kriterium |
|---|---|---|---|---|---|
| 3 | 0,0370 | 1,7596 | 20 | **71,53 %** | X eta >= 0,20 |
| 5 | 0,1009 | 1,6978 | 3 | 76,82 % | X |
| 8 | 0,0988 | 1,9266 | 2 | 65,23 % | X |
| 10 | 0,1000 | 2,2099 | 2 | 84,72 % | X |
| 15 | nan | nan | 0 | 100,00 % | X |

- Hopkins **H = 0,6514** (n=1001; vorher 0,6490 bei n=1033). Interpretation
  unveraendert: schwaches Clustering-Signal (0,55 <= H < 0,75).
- **Vergleich zur committeten Baseline (1033, inkl. DQR):** m=3 eta **28,75 % ->
  71,53 %**; Clusterzahl 4 -> 20; m=15 faellt von 2 Clustern auf 0 (alles Noise).
- **Interpretation / Befundverschaerfung:** Die 32 DQR-Dimensionskonzepte sind
  textlich stark selbstaehnlich ("Wissen -- Niveau 1" ... "Wissen -- Niveau 8")
  und bildeten im 1033-Raum einen kompakten Cluster, der die Noise-Rate drueckte.
  Auf dem reinen Kompetenzkonzeptraum (ESCO-Skills + e-CF-Bereiche) erzeugt
  HDBSCAN bei jedem getesteten m >= 65 % Noise. VH2.3 (eta < 0,20) wird damit
  **deutlicher** verfehlt als zuvor. Die niedrigste Noise-Rate liegt bei m=8
  (65,23 %), der beste Silhouette-/DB-Wert bei m=5; m=8 und m=10 erzeugen aber
  nur je 2 Cluster, m=5 drei. Allein m=3 liefert mit 20 Clustern eine fuer
  eine Hierarchieableitung ueberhaupt brauchbare Aufteilung, bei einer
  Noise-Rate (71,53 %) nur wenige Prozentpunkte ueber dem Minimum -> m*=3
  bleibt gesetzt. CQ4 (navigierbare Hierarchie) bleibt unerfuellbar (siehe E5).
- `min_cluster_size`-Default (=3) in `clustering.py` /
  `ontology_service.run_clustering` bleibt.
- `eval/results/E4_hdbscan.json` neu geschrieben (Backup:
  `E4_hdbscan.json.bak_20260831`), `_meta` ergaenzt.
- Datum: 2026-08-31

## E5 -- Kompetenzfragen CQ1-CQ4

- **Datenbasis:** Projekt `hr_qde_basisontologie_ikt_slice_v0_7_20260830T183521Z`
  (neuer Prompt, e-CF<->ESCO `scope=all`, dqr_3 `container_only`, = Seed von
  `oberhuber-harmonised-ontology-v0.3.ttl`). Frischer Export via
  `app/pipeline/step4_export/ontology_export.py::export_ontology`
  (`eval/e5_export_v07.py`), **kein LLM-Aufruf**.
- **Prefix-Pruefung (ADR-19):** Der Namensraum `http://hr-qde.org/harmonised/`
  ist unveraendert; nur das Praefix wechselte von `hrqde:` zu `harm:`. Die
  E5-SPARQL-Queries adressieren diesen Namensraum als vollstaendige URI bzw.
  ueber den Query-eigenen `hrqde:`-Prefix (`hrqde:HarmonisedConcept` ->
  `http://hr-qde.org/harmonised/HarmonisedConcept`, identische URI). **Keine
  Query-Anpassung noetig.** Der `export_ontology()`-Pfad emittiert die von den
  Queries erwartete Struktur.
- Clustering: HDBSCAN m*=3 ueber ESCO+e-CF, 21 ClusterResults (20 ohne Noise).
  DAG flach -> **0 `rdfs:subClassOf`-Kanten**.
- Disjunkte Konzepte: 730, automatisiert per `suggest_strategy()` entschieden
  (Autor `eval_e5_rerun_20260831`) -- **keine manuelle Einzelpruefung**
  (Limitation, wie 2026-07-29).
- Artefakt: `eval/results/e5_v07_harmonised.ttl`, **4069 Tripel**.

| CQ | Treffer 2026-07-29 | Treffer 2026-08-31 | Erfuellt |
|---|---|---|---|
| CQ1 (exactMatch, `@en`) | 0 | **0** | NEIN |
| CQ2 (narrowMatch e-CF->ESCO) | 732 | **283** | JA |
| CQ3 (disjunkt + integrationStrategy) | 491 | **730** | JA |
| CQ4 (`rdfs:subClassOf+` Cluster) | 0 | **0** | NEIN |

- **CQ1 unveraendert nicht erfuellt.** Auch mit dem geaenderten Prompt erzeugt
  die Klassifikation ueber den gesamten V0.7-Datensatz **kein** `EQUIVALENT` /
  `skos:exactMatch`. Der Prompt-Fix hat die *Richtung* der Subsumtion korrigiert
  (siehe Nebenbefund), nicht die Faehigkeit, Aequivalenz zu erkennen.
- **CQ2 erfuellt, andere Groessenordnung.** 283 statt 732 -- nicht vergleichbar:
  Der V0.7-Lauf klassifiziert nach Aggregationsknoten-Filterung nur 800
  Blatt-zu-Blatt-Paare (2026-07-29: 1540 Paare, kein Aggregationsfilter). Alle
  283 `skos:narrowMatch` zeigen jetzt in die semantisch erwartete Richtung
  (e-CF-Bereich >= ESCO-Skill).
- **CQ3 erfuellt.** 730 statt 491 disjunkte Konzepte im V0.7-Lauf; enthaelt auch
  die 8 `dqr_3`-Niveauknoten (`own_class`).
- **CQ4 unveraendert nicht erfuellt.** 20 Cluster, aber der
  HDBSCAN-Kondensationsbaum ist flach (0 Cluster-zu-Cluster-`rdfs:subClassOf`).
  Direkte Konsequenz der in E4 dokumentierten (jetzt verschaerften) schwachen
  Clusterstruktur.
- **Status: 2/4 CQ erfuellt ("teilweise erfuellt"), unveraendert gegenueber
  2026-07-29.**
- Datum: 2026-08-31

## SHACL-Validierung des v0.3-Artefakts

- `pyshacl` 0.40.1 (jetzt in `requirements.txt`). Shapes:
  `hrqde-shape-harmonisation.ttl` (156 Tripel, Repo-Root).
- `validate(oberhuber-harmonised-ontology-v0.3.ttl, shacl_graph=shapes,
  inference="rdfs", advanced=True)` -> **Conforms: True, 0 Violations**,
  7482 Datentripel. Bestaetigt die Vorgabe.
- Datum: 2026-08-31

## Nebenbefund: Richtungsverzerrung der Klassifikation (Prompt-Fix)

Vergleich der `source_relation`-Verteilung e-CF<->ESCO:

| Relation | alt (Prompt 07/2026, Default-Projekt, 4820) | neu (Prompt-Fix, V0.7, 800 LLM-Mappings) |
|---|---|---|
| `A_SUBSUMES_B` (e-CF >= ESCO) | 0 | **283** |
| `B_SUBSUMES_A` (ESCO >= e-CF) | 3629 | 104 |
| `RELATED` | 843 | 392 |
| `UNRESOLVED` | 348 | 21 |
| `EQUIVALENT` | 0 | **0** |

- Die in E2 (2026-07-29) dokumentierte Verzerrung "Modell sagt fast immer
  `B_SUBSUMES_A`" ist **umgekehrt**: die Subsumtion zeigt jetzt ueberwiegend in
  die erwartete Richtung (e-CF-Kompetenzbereich breiter als ESCO-Skill).
  `UNRESOLVED` faellt von 348 auf 21.
- **`EQUIVALENT` bleibt vollstaendig aus.** Der Befund "nie EQUIVALENT"
  (CQ1, VH1.6-Kontext) besteht fort und ist damit **nicht** allein ein
  Prompt-Formulierungsproblem -> bleibt offene Limitation fuer Kapitel 6.

## E2 -- Few-Shot-Ablation (VH1.6)

- Modell: `mistral/mistral-small-latest` (`LLM_PROVIDERS=mistral`),
  `temperature=0`, 3 Laeufe/Paar (Mehrheitsentscheid).
  74 Paare x 4 n_FS-Werte x 3 Laeufe = 888 reale LLM-Aufrufe.
  Few-Shot-Anker: `eval/G_struct.json` (siehe Setup-Korrektur 1).
- Rate-Limit-Schutz: `MISTRAL_MIN_REQUEST_INTERVAL_S=0.8`,
  `MISTRAL_MAX_ATTEMPTS=10`, `MISTRAL_RETRY_BACKOFF_SECONDS=6.0`.

| n_FS | F1[EQ] | F1[SUBS] | F1[REL] | Macro-F1 | Acc. |
|---|---|---|---|---|---|
| 0 | 0,0000 | 0,3767 | 0,8372 | 0,3181 | 0,5135 |
| 1 | 0,0000 | 0,4333 | 0,7500 | 0,3233 | 0,5000 |
| 3 | 0,0000 | 0,3963 | 0,6250 | **0,3544** | 0,4324 |
| 5 | 0,0000 | 0,4451 | 0,6875 | 0,3155 | 0,4730 |

- **n_FS\* = 3** (Macro-F1 = 0,3544).

**Vergleich zum Lauf 2026-07-29:**

| n_FS | Macro-F1 alt | Macro-F1 neu |
|---|---|---|
| 0 | 0,3147 | 0,3181 |
| 1 | 0,3578 | 0,3233 |
| 3 | 0,3250 | 0,3544 |
| 5 | 0,3045 | 0,3155 |
| n_FS\* | 1 | 3 |

- **Der Verschiebung von n_FS\*=1 auf n_FS\*=3 ist mit Vorsicht zu begegnen:**
  Die Few-Shot-Anker-Quelle hat gewechselt (G_struct-Crosswalks statt der
  nicht mehr vorhandenen persistierten struct-Mappings). Die Macro-F1-Spanne
  ueber alle n_FS liegt zwischen 0,316 und 0,354 -- klein und verrauscht.
- **Robuster, quellunabhaengiger Befund:** `F1[EQUIVALENT] = 0,0000 bei
  *allen* vier n_FS-Werten` (2026-07-29: nur bei n_FS in {0,3,5}). Auch mit dem
  geaenderten Prompt (explizite EQUIVALENT-Definition) und variabler
  Few-Shot-Anzahl sagt das Modell praktisch nie korrekt `EQUIVALENT` voraus.
  Die Richtungsverzerrung bei Subsumtion ist dagegen behoben (Nebenbefund
  oben): F1[SUBS] steigt von ~0,24 (2026-07-29) auf 0,38-0,45.
- **Empfehlung:** Die Produktions-Few-Shot-Anzahl (`_build_few_shot_text(...,
  limit=3)`, entspricht bereits n_FS=3 = ADR-7-Initialwert) **nicht** auf Basis
  dieses Re-Runs aendern. CLAUDE.md Abschn. 6: „Few-Shot-Anzahl 1" auf
  **3** korrigieren, Herkunft E2-Re-Run 2026-08-31, Vorbehalt Anker-Quelle.
- `eval/results/E2_few_shot.json` neu geschrieben, `_meta` ergaenzt.
- Datum: 2026-08-31

## E3 -- Confidence-Schwellen (VH1.7)

- `n_FS=3` (aus E2 uebernommen). Modell `mistral/mistral-small-latest`,
  `temperature=0`, 3 Laeufe/Paar. 74 x 3 = 222 reale LLM-Aufrufe.
  Few-Shot-Anker: `eval/G_struct.json`.

| theta | Precision | Recall | F1 | Uebernommene Mappings |
|---|---|---|---|---|
| 0,33 | 0,8387 | 0,9811 | **0,9043** | 62 |
| 0,67 | 0,9630 | 0,4906 | 0,6500 | 27 |
| 1,00 | 0,9630 | 0,4906 | 0,6500 | 27 |

- theta\* (F1-Optimum) = **0,33**. theta_op (Precision-biased) = **0,33**
  (der Selektor kann theta=0,67 nicht mehr waehlen: F1=0,65 < 0,9 x 0,9043).

**Vergleich zum Lauf 2026-07-29 (n_FS=1):**

| theta | P alt | R alt | F1 alt | P neu | R neu | F1 neu |
|---|---|---|---|---|---|---|
| 0,33 | 0,8667 | 0,9811 | 0,9204 | 0,8387 | 0,9811 | 0,9043 |
| 0,67 | 0,9057 | 0,9057 | 0,9057 | 0,9630 | **0,4906** | **0,6500** |
| 1,00 | 0,9057 | 0,9057 | 0,9057 | 0,9630 | 0,4906 | 0,6500 |
| theta_op | 0,67 | | | **0,33** | | |

- **Kernbefund:** Bei theta=0,67 bricht der Recall von 0,9057 auf **0,4906** ein
  (F1 0,9057 -> 0,6500). Nur **27 statt 53** Paare erreichen ueberhaupt eine
  Konfidenz >= 0,67 (2-von-3-Mehrheit). Der geaenderte Prompt senkt also die
  **Self-Consistency** des Dreifach-Mehrheitsentscheids: die drei Laeufe stimmen
  seltener ueberein, viele wahre K-Paare fallen unter die 0,67-Schwelle und
  werden zu False Negatives. Die Precision bei theta=0,67 *steigt* dabei
  (0,9057 -> 0,9630) -- die akzeptierten Mappings sind fast alle korrekt, es
  werden nur zu wenige akzeptiert.
- **Konfundierung:** Prompt, Few-Shot-Quelle (G_struct) und n_FS (1 -> 3) haben
  sich gleichzeitig geaendert; der Einbruch ist nicht sauber auf eine Ursache
  zurueckfuehrbar. Kleine Goldmenge (74 Paare, davon ~53 in K).
- **Empfehlung / offener Punkt:** `mapping_confidence_threshold` in
  `app/config.py` / `.env(.example)` steht auf **0,67**. Dieser Re-Run legt
  theta_op=0,33 nahe, widerspricht damit CLAUDE.md Abschn. 6 („bestaetigt:
  theta_op=0,67"). **Nicht eigenmaechtig geaendert** -- Optionen in
  `eval/RERUN_2026-08-31.md`, Abschnitt 3. Vor einer Umstellung sollte E3 mit
  entkoppelten Faktoren (alter Few-Shot-Pool bzw. n_FS=1) wiederholt werden.
- `eval/results/E3_confidence.json` neu geschrieben, `_meta` ergaenzt.
- Datum: 2026-08-31

## pytest tests/

- `.venv\Scripts\python.exe -m pytest tests/ -q` -> **152 passed**, 1 Warning
  (`StarletteDeprecationWarning`, unabhaengig), 319 s. Stand 2026-08-31.
  (CLAUDE.md Abschn. 3 nennt 120 Backend-Tests; im Arbeitsbaum liegen inzwischen
  zusaetzliche, noch nicht committete Testdateien -- `test_harmonised_ontology.py`,
  `test_mapping_review.py`, `test_project_service.py` u. a.)

# Nachzug 2026-08-31 (Saeule-D-Abgabe, ESCO-Skelett 1302)

Kontext: Umstellung des ESCO-Hubs von `esco_v1_2_ict_ausschnitt` (956) auf
die gelieferte Referenzmenge `esco_skeleton_oberhuber` (1302,
`esco-skeleton-for-oberhuber.ttl`, Lieferspezifikation Saeule D §1, ADR-27).
E2 und E4 sind vom Wechsel nicht betroffen (Few-Shot-Anzahl bzw.
HDBSCAN-Parameter haengen nicht am ESCO-Hub) und wurden nicht wiederholt.

## E1 -- Recall@k (nachgezogen)

- Aufruf: `python eval/E1_recall_k.py --kqr esco_skeleton_oberhuber ecf dqr_3
  dqr_2 eqf_2017`. Neuer Parameter `--kqr` beschraenkt den Embedding-Raum;
  der abgeloeste 956er-Ausschnitt wird nicht mitgemischt. `dqr_2` und
  `eqf_2017` bleiben nur zur Messung von G_struct im Raum (1583 Konzepte).
- 956er-Stand gesichert als `eval/results/E1_recall_k.json.bak_956_20260831`.

| Goldmenge | evaluierbar | R@5 | R@10 | R@15 | R@20 | R@30 |
|---|---|---|---|---|---|---|
| G_struct (DQR<->EQF) | 32 | 0,844 | 0,906 | 0,938 | **1,00** | 1,00 |
| G_manual (e-CF A.8<->ESCO) | 8 (vorher 9) | 0,875 | **1,00** | 1,00 | 1,00 | 1,00 |

- **G_struct identisch zum 956er-Lauf** -- DQR<->EQF haengt nicht am ESCO-Hub.
- **G_manual**: 8 statt 9 evaluierbare Paare. Die Skelettdatei ist eine
  andere ESCO-Auswahl (Vereinigung ISCED-06-Wissenszweig + Schema "Digital")
  als der 956er-Ausschnitt: zwei Zare-URIs kommen hinzu, drei fallen weg.
  Recall@10 weiterhin 1,00; Recall@5 0,875 statt 0,667.
- **k* (erstes k mit Recall >= 0,90):** G_struct k=10, G_manual k=10.
- **Entscheidung: k=20 unveraendert bestaetigt** (Recall@20 = 1,00 auf beiden
  Goldmengen, konservativ gegenueber der kleinen G_manual-Stichprobe).
  CLAUDE.md Abschn. 6 bleibt unveraendert.

## E3 -- Confidence-Schwellen (wiederholt)

E3 ist **korpusunabhaengig**: klassifiziert werden feste Goldpaare
(`eval/gold/G_manual.json`, 74 Paare), der ESCO-Hub-Wechsel beruehrt E3
nicht. Wiederholung dennoch, um Regressionen im aktuellen Code
auszuschliessen. `n_FS=3`, `mistral/mistral-small-latest`, `temperature=0`,
74 x 3 = 222 reale LLM-Aufrufe. 956er-Stand als
`eval/results/E3_confidence.json.bak_956_20260831`.

| theta | Precision | Recall | F1 | Uebernommene Mappings |
|---|---|---|---|---|
| 0,33 | 0,8644 | 0,9623 | **0,9107** | 59 |
| 0,67 | 0,9118 | 0,5849 | 0,7126 | 34 |
| 1,00 | 0,9118 | 0,5849 | 0,7126 | 34 |

- theta\* (F1-Optimum) = **0,33**. theta_op (Precision-biased) = **0,33**
  (Selektor kann theta=0,67 nicht waehlen: F1 0,713 < 0,9 x 0,9107).
- **Kernbefund des Laufs vom selben Tag bleibt bestehen:** bei theta=0,67
  liegt der Recall weiterhin deutlich unter 0,90 (0,585); nur 34 Paare
  erreichen die 2/3-Mehrheit. Die leichte Verschiebung gegenueber dem
  frueheren Lauf (acc 27 -> 34, F1@0,67 0,650 -> 0,713) ist API-Drift des
  `-latest`-Modells, **kein** Effekt des ESCO-Wechsels.
- **Offener Punkt unveraendert:** `mapping_confidence_threshold` = 0,67 in
  `app/config.py` / `.env`; die E3-Zahlen legen theta_op=0,33 nahe und
  widersprechen CLAUDE.md Abschn. 6. Ursache konfundiert (Prompt +
  Few-Shot-Quelle + n_FS gleichzeitig geaendert). Nicht eigenmaechtig
  geaendert.

## E5 -- Kompetenzfragen CQ1-CQ4 (nachgezogen gegen die Lieferartefakte)

- Aufruf: `python eval/E5_cq_evaluation.py --delivery . --output
  eval/results/E5_cq_evaluation.json`. Neuer `--delivery`-Modus parst
  `oberhuber-harmonised-ontology-v0.2.ttl` + `oberhuber-mappings-v0.2.ttl`
  und laedt `esco_skeleton_oberhuber.ttl` als Label-Quelle (ESCO ist im
  Artefakt selbst nicht annotiert). Die CQ-Queries wurden an die
  reifizierten `harm:HubMapping`-Records angepasst (`sssom:subject_id` /
  `object_id` / `predicate_id`), Prefix `harm:` statt `hrqde:`.
- v0.3-Stand gesichert als `eval/results/E5_cq_evaluation.json.bak_v03_20260831`.

| CQ | Treffer | Erfüllt | vorher (v0.3) |
|---|---|---|---|
| CQ1 Äquivalenz (exactMatch HubMapping) | 0 | nein | 0 |
| CQ2 ESCO-Skills unter e-CF (narrowMatch) | 156 | ja | 283 |
| CQ3 disjunkte Konzepte + Strategie | 5 | ja | 730 |
| CQ4 navigierbare Hierarchie | 0 | nein | 0 |

- **Verdikt unveraendert:** CQ2 und CQ3 erfuellt, CQ1 und CQ4 nicht --
  E5 teilweise erfuellt.
- **CQ1 = 0:** kein `EQUIVALENT` im 800-Paar-Lieferlauf. Die 8
  `skos:exactMatch`-Kanten sind `harm:LevelMapping` (DQR<->EQF, normativ)
  und zaehlen nicht zu CQ1.
- **CQ2 = 156:** `harm:HubMapping` mit `skos:narrowMatch` (A_SUBSUMES_B).
  Die 208 container-abgeleiteten `skos:broadMatch` tragen die Gegenrichtung
  und zaehlen nicht. Niedriger als v0.3 (283), weil eigenstaendiger
  Klassifikationslauf (LLM-Nichtdeterminismus).
- **CQ3 = 5:** spec-konformer Scope. `harm:HarmonisedConcept` nur fuer die
  disjunkten e-CF-Blaetter (A.2, D.5, D.6, D.8, D.9, alle `own_class`);
  DQR-Niveaus sind Skelett-Referenzen, ESCO wird referenziert statt
  annotiert. Das v0.3-Ergebnis (730) zaehlte ESCO-Skills, ESCO-Berufe und
  DQR-Knoten mit.
- **CQ4 = 0:** das Lieferartefakt enthaelt kein
  `harm:HarmonisedCluster` und keine `rdfs:subClassOf`-Kante
  (HDBSCAN-Negativbefund, E4).
- Kapitel 5 (`chapters/chapter_5/cq_evaluation.tex`) und der SPARQL-Anhang
  (`frontbackmatter/AppendixSPARQL.tex`) sind auf diese Werte und die
  reifizierte Query-Form synchronisiert. Datum: 2026-08-31.

## Kapitel-5-Stand nach dem Nachzug

Synchronisiert: `exp1_recall_k.tex`, `exp3_confidence.tex`,
`cq_evaluation.tex`, `summary.tex` (E3-Recall 0,49->0,58),
`AppendixSPARQL.tex`, `chapters/chapter_4/architektur.tex`
(ADR-24 bis ADR-28), `frontbackmatter/Acronyms.tex` (SHACL).
E2 und E4 sind vom ESCO-Wechsel nicht betroffen und unveraendert.

---

# Nachtrag 2026-09-02: Container-Kanten-Praedikatrichtung + E5-Re-Run

## Anlass

`prefilter.derive_container_mappings()` praegte fuer jeden
Aggregationsknoten (e-CF-Konzept mit `skos:broader`-Kindern, z. B. PLAN
ueber A.1--A.9) ein abgeleitetes Mapping mit hartkodiertem
`predicate_id = "skos:broadMatch"`. Subjekt ist der Container, Objekt das
ESCO-Zielkonzept; der Container ist der **breitere** Begriff. Nach W3C
SKOS und Kapitel 2 (`sssom.tex`: „`skos:narrowMatch` = Subject ist weiter
als Object") ist das `skos:narrowMatch` -- dieselbe Richtung wie die
Kindmappings (`A_SUBSUMES_B` -> `skos:narrowMatch`, korrigiert in
`RelationType.to_skos_predicate()`). Die Container-Ableitung war beim
`to_skos_predicate()`-Fix nicht mitgezogen worden. Folge: LLM-Kind-Kante
und daraus abgeleitete Eltern-Kante trugen entgegengesetzte Praedikate
fuer denselben Sachverhalt („e-CF-Seite breiter"); `cq_evaluation.tex`
schloss die Container-Kanten deshalb aus CQ2 aus („tragen die
Gegenrichtung").

## Aenderung im Code

- `app/pipeline/step2_embedding_prefilter/prefilter.py`
  `derive_container_mappings()`: `predicate_id` `skos:broadMatch` ->
  `skos:narrowMatch`; Docstring und `justification`-Text nachgezogen.
- `app/services/classification_service.py`: Kommentar an der
  Container-Ableitung nachgezogen.
- `tests/test_prefilter.py::test_derive_container_mappings_averages_child_confidences`:
  erwartetes Praedikat `skos:broadMatch` -> `skos:narrowMatch`. Der
  Struktur-Shortcut-Test (`ecf:level_5` isPartOf `eqf_level_6` ->
  `skos:broadMatch`) bleibt unveraendert (dort ist das Subjekt das
  engere Konzept, W3C-konform).

## Re-Run (ohne erneute LLM-Klassifikation)

Der Fix betrifft nur die abgeleiteten Kanten, nicht die
LLM-Klassifikation. Um LLM-Nichtdeterminismus als Stoervariable
auszuschliessen, wurden die 800 Klassifikationsergebnisse
**unveraendert** wiederverwendet und nur die 165 Container-Mappings
(`semapv:LogicalReasoning`, alle `conjunct`, alle vorher
`skos:broadMatch`) auf `skos:narrowMatch` umetikettiert -- was mit einer
Re-Ableitung durch den korrigierten Code identisch ist, weil das
Praedikat dort unbedingt gesetzt wird.

- Projekt `saeule_d_lieferung_informatik_korridor_20260831T171750Z`,
  `mappings.json`-Backup:
  `mappings.json.bak_broadmatch_containeredges_20260902T075329Z`.
- `python scripts/run_saeule_d_delivery.py --export-only` erzeugt die drei
  v0.2-Artefakte neu. SHACL (kanonisch): `conforms=True`, 0 Violations
  fuer Ontologie und Mappings.
- Praedikatverteilung im Mappings-Artefakt (364 `harm:HubMapping`):
  vorher `{broadMatch: 208, narrowMatch: 156}`, nachher
  `{narrowMatch: 321, broadMatch: 43}`. Die 43 verbleibenden
  `broadMatch` sind LLM-`B_SUBSUMES_A`-Klassifikationen.

## E5 CQ1--CQ4 (Delivery-Modus, `python eval/E5_cq_evaluation.py --delivery .`)

| CQ | Treffer | Erfuellt | vorher (v0.2, 2026-08-31) |
|---|---|---|---|
| CQ1 Aequivalenz (exactMatch HubMapping) | 0 | nein | 0 |
| CQ2 ESCO-Skills unter e-CF (narrowMatch) | 321 | ja | 156 |
| CQ3 disjunkte Konzepte + Strategie | 5 | ja | 5 |
| CQ4 navigierbare Hierarchie | 0 | nein | 0 |

- **Verdikt unveraendert:** CQ2 und CQ3 erfuellt, CQ1 und CQ4 nicht --
  E5 teilweise erfuellt.
- **CQ2 = 321:** die 165 aus Kindmappings abgeleiteten
  Container-/Bereichs-Kanten tragen jetzt `skos:narrowMatch`
  (e-CF-Aggregationsknoten subsumiert ESCO-Skill) und zaehlen zu CQ2.
  156 + 165 = 321. Kein Widerspruch mehr zwischen Kind- und
  Eltern-Kanten.
- CQ1, CQ3, CQ4 unveraendert (der Fix beruehrt weder EQUIVALENT noch die
  Disjunkt-Menge noch das fehlende Clustering).
- v0.2-Stand vor dem Fix gesichert als
  `eval/results/E5_cq_evaluation.json.bak_v02_broadmatch_20260902T075355Z`.

## Synchronisiert (Vorlage)

`chapters/chapter_5/cq_evaluation.tex` (CQ2 156 -> 321, „Gegenrichtung"-
Klausel entfaellt), `chapters/chapter_4/fz13_embedding.tex`
(Container-Praedikat), `chapters/chapter_5/exp4_hdbscan.tex`
(Einhaengeregel-Absatz). CLAUDE.md §13 nachgezogen.

`chapters/chapter_5/evaluationsdesign.tex` (Abschnitt
„Evaluationszonen"): Praedikat der Aggregationskanten korrigiert **und**
die Datenbasis auf dasselbe Artefakt wie E5 umgestellt (vorher V0.7-
IKT-Slice-Zahlen 283/104/392/21 + 324 Aggregationskanten; jetzt die
v0.2-Lieferung: 199 Subsumtionsmappings mit 156 e-CF>=ESCO / 43
umgekehrt, 568 RELATED, 33 UNRESOLVED, 165 Aggregationskanten, 8
harm:LevelMapping DQR<->EQF, 135 narrative e-CF-Dim.-3-Crosswalk-Zeilen).
Zone-2/3/4-Zahlen entsprechend nachgezogen.
