# Evaluationsprotokoll (Kapitel 5)

> **Hinweis zum Abgabestand:** Verweise in diesem Protokoll auf `data/archive/`, die Lieferstände
> `data/deliverables/v0.2-*` und `v0.3-*`, `eval/results/archive/`, `scripts/archive/`, `docs/archive/`,
> `eval/RERUN_2026-08-31.md`, `eval/E1_spec.md` und die Planungsdokumente `eval/E*_plan.md` betreffen
> Stände der Entwicklungsphase. Sie sind im Abgabestand nicht mehr enthalten und nur über die
> Git-Historie vor den Bereinigungs-Commits vom 9. Oktober 2026 erreichbar.

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

**Architektur-Korrektur (Nutzerhinweis)**: ELM ist per Kapitel 3
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
   / `Mapping.match_type` -- beide nach ADR-15 entfernt (`ImportError`). Der
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
  `eval/results/archive/E4_hdbscan.json.bak_20260831`), `_meta` ergaenzt.
- Datum: 2026-08-31

## E5 -- Kompetenzfragen CQ1-CQ4

- **Datenbasis:** Projekt `hr_qde_basisontologie_ikt_slice_v0_7_20260830T183521Z`
  (neuer Prompt, e-CF<->ESCO `scope=all`, dqr_3 `container_only`, = Seed von
  `oberhuber-harmonised-ontology-v0.3.ttl`). Frischer Export via
  `app/pipeline/step4_export/ontology_export.py::export_ontology`
  (`eval/e5_export_v07.py`), **kein LLM-Aufruf**.
- **Prefix-Pruefung (ADR-15):** Der Namensraum `http://hr-qde.org/harmonised/`
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
`esco-skeleton-for-oberhuber.ttl`, ADR-23).
E2 und E4 sind vom Wechsel nicht betroffen (Few-Shot-Anzahl bzw.
HDBSCAN-Parameter haengen nicht am ESCO-Hub) und wurden nicht wiederholt.

## E1 -- Recall@k (nachgezogen)

- Aufruf: `python eval/E1_recall_k.py --kqr esco_skeleton_oberhuber ecf dqr_3
  dqr_2 eqf_2017`. Neuer Parameter `--kqr` beschraenkt den Embedding-Raum;
  der abgeloeste 956er-Ausschnitt wird nicht mitgemischt. `dqr_2` und
  `eqf_2017` bleiben nur zur Messung von G_struct im Raum (1583 Konzepte).
- 956er-Stand gesichert als `eval/results/archive/E1_recall_k.json.bak_956_20260831`.

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
`eval/results/archive/E3_confidence.json.bak_956_20260831`.

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
- v0.3-Stand gesichert als `eval/results/archive/E5_cq_evaluation.json.bak_v03_20260831`.

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
(ADR-20 bis ADR-24), `frontbackmatter/Acronyms.tex` (SHACL).
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
  `eval/results/archive/E5_cq_evaluation.json.bak_v02_broadmatch_20260902T075355Z`.

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

# Nachtrag 2026-09-05: DQR/EQF-Granularitaetsvarianten, dqr_3 verworfen, G_struct neu aufgebaut

## Anlass

EQF wurde bislang als `eqf_2017.ttl` (32 Konzepte) formalisiert, DQR
parallel als `dqr_2013.ttl` (32, Dimensionsebene), `dqr_2.ttl`
("Reformalisierung v2", 196) und `dqr_3.ttl` (8, Produktionssatellit,
ADR-21). Dazu kamen die PoC-Formalisierungen `dqr_levelProposal.ttl`
und `ecf_levelProposal.ttl`/`ecf_levelproposal_crosswalk.ttl` aus der
`harm:hasLevel`-Arbeit (s. Nachtrag-Kontext in
`docs/archive/handoff-kapitel-3-4-5-harm-haslevel.md`). Das ergab pro Rahmen
mehrere, uneinheitlich benannte KQR-Staende ohne erkennbare
Vorrangregel; `E1_recall_k.py`s eigener Docstring behauptete zeitweise
"EQF ist aktuell nicht formalisiert", obwohl `eqf_2017` zu diesem
Zeitpunkt laengst registriert war (Stand-Drift zwischen Code-Kommentar
und tatsaechlicher Registry).

Nutzerentscheidung: DQR und EQF werden einheitlich ueber
`scripts/22_build_eqf_dqr_granularity_variants.py` neu formalisiert, in
genau zwei Granularitaeten je Rahmen:

- `dqr_1D.ttl` / `eqf_1D.ttl` -- je 8 Grundknoten (ein Niveau = ein
  Konzept), Crosswalk direkt als `skos:exactMatch` in der Quelle.
- `dqr_2D.ttl` / `eqf_2D.ttl` -- 8 Grundknoten plus Dimensionsfacetten
  (DQR: 4 Dimensionen x 8 = 32 Facetten, macht 40; EQF: 3 Dimensionen x
  8 = 24 Facetten, macht 32). Dimensionsdeskriptoren gegen
  https://www.dqr.de bzw. OJ C 189 (EQF) neu verifiziert.

Die 3-vs-4-Kategorien-Asymmetrie zwischen EQF und DQR bleibt in beiden
Granularitaeten erhalten (32 vs. 40 bei `_2D`) -- ein reales Merkmal der
beiden Normen, kein Formalisierungsartefakt, damit bleibt der in E1
dokumentierte Asymmetrie-Befund inhaltlich gueltig.

`dqr_3` wird verworfen: der Liefer-Anker (ADR-21) wird
neu definiert und soll kuenftig auf den `_1D`/`_2D`-Varianten aufbauen.

## Aenderung an den Daten

- **Archiviert** (umbenannt auf `.bak_20260905T192804Z`, nicht
  geloescht): `data/formalized/dqr_3.ttl`, `dqr_2013.ttl`, `dqr_2.ttl`,
  `eqf_2017.ttl`, `eqf_2017_harm.ttl`, `dqr_levelProposal.ttl`,
  `ecf_levelProposal.ttl`, `ecf_levelproposal_crosswalk.ttl`.
- **Registry** (`data/kqr_registry.json`): 17 -> 9 Eintraege. Verworfene
  IDs entfernt, `eqf_1d` (8), `eqf_2d` (32), `dqr_1d` (8), `dqr_2d` (40)
  sind jetzt die einzige DQR/EQF-Quelle. Unangetastet:
  `esco_v1_2_ict_ausschnitt`, `ecf`, `esco_skeleton_oberhuber`,
  `dqr_l6_walkthrough_slice`, `esco_ikt_walkthrough_slice` (Cognitive-
  Walkthrough-Ausnahme).
- **`data/structural_shortcut_predicates.json`**: Eintrag
  `harm:eqfCrosswalkTarget` entfernt (war ausschliesslich fuer
  `ecf_levelproposal_crosswalk` gebaut, jetzt herrenlos). Vorher als
  `.bak_20260905T192804Z` gesichert.
- **Projektordner** `data/projects/levelproposal_20260905T085612Z`,
  `levelproposal_run3_granularitaetstest_e_cf_vs_dqr_3_20260905T120311Z`,
  `levelproposal_run4_crosswalk_shortcut_e_cf_vs_dqr_3_20260905T130918Z`
  nach `data/archive/projects_archive_20260905T192804Z/` verschoben (nicht
  geloescht, aber nicht mehr aus `data/projects/` heraus ausfuehrbar).
- **Lieferstand v0.2 archiviert** (`.bak_v02_20260905T192804Z`,
  Repo-Root): `hrqde-harmonisation-schema.ttl`,
  `hrqde-shape-harmonisation.ttl`, `hrqde-shapes-all.ttl`,
  `oberhuber-harmonised-ontology-v0.2.ttl`,
  `oberhuber-mappings-v0.2.ttl`, `oberhuber-integration-strategy-v0.2.md`
  -- vor der angekuendigten Neudefinition der Liefervorgaben.
  Nachtrag Repo-Cleanup 2026-10-08: Die `.bak_v02`-Dateien liegen jetzt
  ohne Suffix im Snapshot `data/deliverables/v0.2-20260904/`.
  `hrqde-shapes-all.ttl` war mit dem aktuellen Stand identisch und
  wurde nicht gesondert archiviert.

## G_struct neu aufgebaut

`eval/G_struct.json` wurde nicht per Hand editiert, sondern per rdflib
aus `dqr_2D.ttl`/`eqf_2D.ttl` extrahiert (Subjekt/Objekt/Praedikat je
Dimensionsfacette, 4 Paare x 8 Niveaus = 32). URI-Namensraum
unveraendert (`http://data.bmbf.de/dqr/`, `http://data.europa.eu/snb/eqf/`),
daher sind alle 32 `subject_id`/`object_id`-Werte identisch zur
vorherigen, gegen `dqr_2013.ttl`/`eqf_2017.ttl` aufgebauten Fassung.
Einzige inhaltliche Aenderung: ein bereinigtes doppeltes Leerzeichen in
einem Label ("Selbststaendigkeit  -- Niveau 1" -> "Selbststaendigkeit --
Niveau 1"). Alter Stand nicht separat gesichert, da per `git show
HEAD:eval/G_struct.json` jederzeit rekonstruierbar.

## Re-Run E1 (`python eval/E1_recall_k.py --kqr esco_skeleton_oberhuber ecf dqr_2d eqf_2d`)

| $k$ | Recall@k ($G_{struct}$, n=32) | vorher (dqr_2013/eqf_2017) |
|---|---|---|
| 5  | 0,875 | 0,844 |
| 10 | 0,906 | 0,906 |
| 15 | 0,938 | 0,938 |
| 20 | 1,000 | 1,000 |
| 30 | 1,000 | 1,000 |

Nur $k=5$ weicht ab (28 statt 27 Treffer von 32), vermutlich durch die
gegen dqr.de/OJ-C-189 leicht ueberarbeiteten Dimensionsdeskriptor-Texte
in `dqr_2D.ttl`/`eqf_2D.ttl`. $k^{*}=10$, Empfehlung $k=20$ unveraendert.
$G_{manual}$ (e-CF A.8 <-> ESCO) unveraendert, haengt nicht an DQR/EQF.

## E2/E3/E4: geprüft, kein Re-Run noetig

- **E2/E3**: `_few_shot_text_for_n_fs()` (`eval/E2_few_shot.py`) zieht
  die Few-Shot-Anker aus den ersten `n_fs` Eintraegen von
  `G_struct.json["pairs"]`. Fuer $n_{FS} \in \{0,1,3,5\}$ sind das
  hoechstens die ersten 5 Paare (Niveau 1 komplett + Niveau-2-Wissen);
  deren `subject_label`/`object_label` sind zwischen altem und neuem
  G_struct bis auf das oben genannte Leerzeichen identisch. Kein
  LLM-Re-Run noetig, keine API-Kosten verursacht.
- **E4**: `E4_DEFAULT_KQR_IDS = ("esco_v1_2_ict_ausschnitt", "ecf")` in
  `eval/E4_hdbscan.py` ist hartkodiert und unabhaengig von DQR/EQF.
  Unberuehrt.

## Synchronisiert (Vorlage)

`chapters/chapter_5/exp1_recall_k.tex` (Tabelle auf neue Werte
aktualisiert, auf eine gemeinsame Tabelle fuer $G_{struct}$/$G_{manual}$
verdichtet), `exp2_few_shot.tex`, `exp3_confidence.tex` -- alle drei im
selben Zug erheblich gekuerzt (372 -> 205 Zeilen gemeinsam), da sie
reine Parameterkalibrierung mit im Fliesstext unnoetig ausgebreiteter
Verfahrensbegruendung waren; die tragenden inhaltlichen Nebenbefunde
(DQR/EQF-Dimensionsasymmetrie in E1, F1_EQUIV=0 in E2, Recall-Einbruch
mit Konfund in E3) sind erhalten geblieben, Verfahrensdetail verweist
jetzt auf die entsprechenden Abschnitte hier im Protokoll. Volle
Fassungen vor der Kuerzung gesichert als
`chapters/chapter_5/exp{1,2,3}_*.tex.bak_orig_20260905T210000Z`.
`exp4_hdbscan.tex` unveraendert (einziges Experiment mit offener
Forschungsfrage statt reiner Parameterbestaetigung, traegt CQ4/FF2
direkt). `chapters/chapter_4/architektur.tex` ADR-18 in-place korrigiert
und mit ADR-20--28 konsolidiert (20 -> 16 Tabellenzeilen); Details dazu
in `chapters/PLAN_harm_haslevel_kap345.md`.

# Nachtrag 2026-09-06 -- DQR-Namespace-Migration (harm-dqr:)

Die DQR-Konzept-URIs in `data/formalized/dqr_1D.ttl` und
`data/formalized/dqr_2D.ttl` sind von `http://data.bmbf.de/dqr/` auf die
harmonisierte Source-Basis `http://hr-qde.org/harmonised/source/dqr/`
(`harm-dqr:`) umgestellt. Jeder Konzeptknoten traegt jetzt genau ein
`owl:sameAs` auf die gleichnamige `data.bmbf.de`-URI (Bruecke fuer externe
Referenzen). Der Generator `scripts/22_build_eqf_dqr_granularity_variants.py`
erzeugt diese Form; `eqf_1D.ttl`/`eqf_2D.ttl` kalibrieren ihre
`skos:exactMatch`-Kante entsprechend auf `harm-dqr:L{n}`. Motivation:
`eval/G_levels.json` verwendete die harmonisierte Basis bereits, der Rest
der Niveau-Kette zog nach; `harm-dqr:` ist SPARQL/Cypher-traversierbar im
HR-QDE-Graphen, `data.bmbf.de` bleibt als `owl:sameAs`-Ziel erhalten.

Mitgezogen: `eval/G_struct.json` (32 DQR-Subjekt-URIs), `scripts/23_build_g_levels.py`
(liest die Anker-URI jetzt direkt statt sie aus Praefix + `sourceIdentifier`
zu rekonstruieren), `tests/test_granularity_variants.py` (Namespace-Konstante
plus neuer `owl:sameAs`-Test). `eval/G_levels.json` durch `scripts/23` neu
erzeugt -- inhaltlich unveraendert (113 Paare, alle `object_id` unter
`harm-dqr:`). Nicht angefasst: die Legacy-Voll-DQR-Dateien (`dqr.ttl`,
`dqr_2013.ttl`, `dqr_l6_walkthrough_slice.ttl`), der eingefrorene
Cognitive-Walkthrough-Lauf und die historischen E5/G_manual-Artefakte --
sie tragen `data.bmbf.de` als echte Autoritaets-URI eines anderen
Datenbestands.

## K_levels-Re-Run (migrierter DQR-Bestand)

`python scripts/24_run_k_levels.py` (Satellit `dqr_2d`, Hub `eqf_1d`):
Projekt-ID `k_levels_20260906T065531Z`, Run-Laufzeit 0,44 s,
40 Mappings (8x `semapv:StructuralMatching`/`skos:exactMatch`/conf 1,0 +
32x `semapv:LogicalReasoning`/`skos:narrowMatch`/conf 1,0), Review-Queue
leer, kein `skos:relatedMatch`, kein EQF-Konzept als `subject_id`. Alle
`subject_id` unter `harm-dqr:`, `object_id` unter
`http://data.europa.eu/snb/eqf/` (unveraendert). Identisch zum Lauf vor
der Migration, nur mit den neuen Subjekt-URIs.

## E1 Recall@k -- G_levels (`ecf_level` <-> `dqr_1d`)

`python eval/E1_recall_k.py --gold eval/G_levels.json --kqr ecf_level dqr_1d --k-values 1 3 5 8`
(Ergebnis: `eval/results/E1_recall_k_levels.json`). `ecf_level` aus
`data/formalized/ecf_levelProposal.ttl.bak_20260905T192804Z` reaktiviert
als `data/formalized/ecf_level.ttl` (146 Konzepte, dessen
`harm:eqfCrosswalkTarget`-Praefix ebenfalls auf `harm-dqr:` gezogen) und
in `kqr_registry.json` registriert.

| $k$ | Recall@k ($G_{levels}$, n=113) |
|---|---|
| 1 | 0,221 (25/113) |
| 3 | 0,575 (65/113) |
| 5 | 0,894 (101/113) |
| 8 | 1,000 (113/113) |

$k=8$ ist der vollstaendige Retrieval-Raum (nur 6 DQR-Niveau-Anker
L3--L8 als Objektkandidaten, $k_{eff}=6$), Recall@8 daher konstruktiv
1,0. Aussagekraeftig sind Recall@1/3/5: die e-CF-Proficiency-Beschreibung
landet in 89,4 % der Faelle unter den Top 5 des korrekten DQR-Ankers.
E1-Laufzeit rund 21 s (inkl. Embedding-Vorlauf).

# Nachtrag 2026-09-06 -- Kanonisches Level-/Rollenmodell v0.3

Die Shapes und das Schema aus dem Toolkit-Change-Request gelten ab diesem
Stand als kanonisch. Rollen werden nicht mehr ueber `harm:conceptRole`
annotiert, sondern ueber `rdf:type harm:CompetenceConcept` bzw.
`rdf:type harm:LevelConcept`. Die Relation `harm:hasLevel` hat den festen
Vertrag Kompetenzkonzept -> Niveaukonzept. Der e-CF-Dimension-3-Crosswalk
wird als regulaerer `harm:LevelMapping` mit `skos:closeMatch`, manueller
Kuration und Konfidenz 1.0 materialisiert; er ist nicht Teil der ESCO-
Coverage. Damit ist die gesamte Niveaukette maschinenlesbar:
e-CF-Dimension 2 -> `harm:hasLevel` -> Dimension-3-LevelConcept ->
`harm:LevelMapping` -> DQR-Level.

Die erneute Lieferung (`oberhuber-*-v0.3.*`) besteht SHACL-seitig ohne
Violations. Die E5-Auswertung wurde gegen die reifizierten Lieferartefakte
erneut ausgefuehrt:

| CQ | Treffer | Erfuellt |
|---|---:|---|
| CQ1: exactMatch-HubMappings | 0 | nein |
| CQ2: e-CF -> ESCO narrowMatch | 156 | ja |
| CQ3: disjunkte Konzepte mit Strategie | 5 | ja |
| CQ4: hasLevel -> LevelMapping -> DQR | 113 | ja |

Die Lieferung enthaelt 364 `harm:HubMapping`, 113 e-CF->DQR-
`harm:LevelMapping` und 8 DQR<->EQF-`harm:LevelMapping`. Die offene
Coverage-Limitation bleibt bestehen (601 offene Reviews, Coverage 364/965 =
37,7 %); die Modellumstellung aendert diese empirische Einschraenkung nicht.

# Nachtrag 2026-09-06 -- Unabhaengigkeit der K_levels-Goldmenge

Die technische Pruefung der K_levels-Evaluation bestaetigt die
Quellenunabhaengigkeit. E1 erzeugt Embeddings ausschliesslich aus
`skos:prefLabel` und `skos:definition` jedes Konzepts. Die 146 e-CF-
Dimension-3-Knoten wurden aus den freitextlichen Proficiency-Beschreibungen
der e-CF-Quelldatei formalisiert. In diesen beiden Feldern findet sich keine
explizite DQR- oder EQF-Zuordnung. Die DQR-Ankerknoten enthalten ihre
eigenen DQR-Niveau-Bezeichnungen und -Beschreibungen, aber keinen Verweis
auf e-CF. Die normative Zuordnung liegt getrennt in e-CF 3.0
(CWA 16234-1:2014) und in `G_levels.json`; sie wird nicht in den Embedding-Text
eingespeist.

E1 baut den FAISS-Index fuer jedes Goldpaar aus den eindeutigen Objekt-URIs
der evaluierbaren Goldmenge. `G_levels` verwendet sechs distinkte DQR-Anker
L3--L8, weshalb Recall@8 eine konstruktive Obergrenze ist. Die Messung
bewertet damit die semantische Retrieval-Faehigkeit zwischen unabhaengigen
Freitexten, waehrend `G_levels` die normative Referenz fuer die korrekte
Zielstufe bereitstellt.


# Nachtrag 2026-10-04 -- Baselines, E2-Korrektur, Recall@k im vollen Pool

Branch `eval/baselines`, Sicherung vorher: Tags `backup/head-20261004`
und `backup/worktree-20261004`. Keine LLM-Aufrufe in diesem Nachtrag.

**E2 Macro-F1 (Korrektur).** `compute_macro_f1` mittelte ueber die
beobachteten Labels. Sobald UNRESOLVED vorhergesagt wurde, ging es als
fuenfte Klasse mit F1 = 0 in den Nenner ein. Neu berechnet aus den
gespeicherten Klassen-F1 (Mittel ueber vier Goldklassen):
n_FS 0/1/3/5 = 0,398/0,404/0,354/0,394 (vorher 0,318/0,323/0,354/0,316).
n_FS = 3 ist damit der schwaechste Wert, die Spanne bleibt im Rauschen.
`E2_few_shot.json` ist unveraendert. Achtung: `E3_confidence.py` liest
n_FS* ohne `--n-fs` aus dieser Datei; nach einem E2-Neulauf wuerde es
n_FS = 1 waehlen.

**Baselines (`B_baselines.py`).** K-Mitgliedschaft (Vergleich E3,
Pipeline F1 = 0,911 bei theta* = 0,33): alles uebernehmen F1 = 0,835;
Kosinus-Schwelle F1 = 0,891 (auf G_manual optimiert) bzw. 0,852
(Leave-One-Out); AUC K vs. RELATED = 0,862. Vier Klassen (Vergleich E2):
Zufall stratifiziert 0,25; Mehrheitsklasse 0,115; Kosinus-Drei-Band-
Heuristik 0,424 (optimiert) bzw. 0,343 (Leave-One-Out). Die Heuristik
erreicht F1_EQUIVALENT 0,47 (LOOCV 0,375), die Pipeline 0.
Exakter Label-Abgleich: 2 Treffer, beide korrekt EQUIVALENT.

**Recall@k im vollen Pool (`B_recall_fullpool.py`).** E1 indexiert nur
die Goldobjekte. Gegen den vollstaendigen Ziel-KQR: G_manual_seed
(Zare, Pool 1302) Recall@10 = 0,375, @20 = 0,875, @30 = 1,0
(E1-Stil: @10 = 1,0). G_struct (Pool 32) @20 = 0,938.

**Befunde zu G_manual.** Alle 74 Objekte stammen aus dem abgeloesten
Ausschnitt `esco_v1_2_ict_ausschnitt` (956), nur 27 liegen im Skelett
(1302). 7 der 74 Paare haben ein DQR-Subjekt (6 davon mit veralteten
URIs `http://data.bmbf.de/dqr/...`, nicht mehr in der Registry). Im
956er-Pool ist der maximale Rang aller Goldobjekte exakt 20: G_manual
enthaelt nur Paare, die die ANN-Suche mit k = 20 bereits gefunden hat,
und eignet sich daher nicht zur Messung des Recalls.


# Nachtrag 2026-10-04 (2) -- LLM-Neulauf rerun_2026-10

Runner `R_rerun.py`, Auswertung `R_analyze.py`, Ergebnisse in
`results/rerun_2026-10/`. Modell `mistral-small-2603` (Alias
`mistral-small-latest` ueber die Modellliste der API aufgeloest; welche
Version im August/September hinter dem Alias stand, ist nicht mehr
feststellbar). 68 von 74 G_manual-Paaren; die 6 Paare mit veralteten
DQR-URIs sind ausgelassen. Konfidenzintervalle: Bootstrap, 2000 Ziehungen.

**Temperatur.** Die `.env` setzt `CLASSIFICATION_TEMPERATURE=0.3`,
`ClassificationRun` protokolliert fest 0,0. Selbstkonsistenz (Anteil 3/3):
T = 0 ergibt 0,93/0,99/0,97, T = 0,3 ergibt 0,60. Der E3-Nachtrag vom
2026-09-06 nennt 45--46 von 74 einstimmigen Paaren (0,61). Die frueheren
Laeufe sind damit mit hoher Wahrscheinlichkeit bei T = 0,3 entstanden.

**Produktionskonfiguration (n_FS = 3, T = 0), drei Durchgaenge.**
Macro-F1 0,382/0,397/0,397 (KI95 Durchgang 1: 0,289--0,463),
98,5 % der Paare mit identischer Endrelation in allen Durchgaengen.
K-Mitgliedschaft bei Mehrheit: P = 0,897, R = 0,981, F1 = 0,937
(KI95 0,887--0,980); bei Einstimmigkeit F1 = 0,925. F1_EQUIVALENT = 0:
10 der 11 EQUIVALENT-Paare werden als A_SUBSUMES_B klassifiziert,
16 der 20 B_SUBSUMES_A-Paare ebenfalls; 18 Richtungsvertauschungen.
Das Modell bevorzugt A_SUBSUMES_B (47 von 68 Vorhersagen).

**Few-Shot-Ablation (T = 0, je ein Durchgang).** Macro-F1 n_FS 0/1/3/5 =
0,499/0,487/0,382--0,397/0,421. Die G_struct-Anker (DQR<->EQF) helfen
nicht; n_FS = 3 ist der schwaechste Wert.

**Kombination Kosinus + LLM.** EQUIVALENT, wenn Kosinus >= t, sonst
LLM-Relation; t per Leave-One-Out (Median 0,794). Macro-F1 0,487
(LOOCV) gegenueber 0,382 (LLM allein), gepaarte Bootstrap-Differenz
+0,099 (KI95 0,004--0,179).

**LLM vs. Kosinus fuer K (McNemar, exakt).** 6 Paare nur vom LLM
richtig, 1 nur vom Kosinus; p = 0,125.

**E3-Schwellen.** `E3_confidence.py` vergleicht theta = 0,67 mit der
Konfidenz 2/3 = 0,6667. theta = 0,67 verlangt damit faktisch
Einstimmigkeit, theta = 0,33 entspricht dem einfachen Mehrheitsentscheid.


# Nachtrag 2026-10-04 (3) -- Richtungsgenauigkeit

`R_analyze.py` weist jetzt je Lauf die Richtungsgenauigkeit aus
(`per_run.<datei>.direction`). Unter den Gold-Subsumtionspaaren (42), die
als Subsumtion erkannt wurden, stimmt die Richtung bei: n_FS = 3 (alle drei
Durchgaenge) 23 von 41 (56,1 %, exakter Binomialtest gegen 0,5: p = 0,53);
n_FS = 0: 25 von 37 (67,6 %, p = 0,047); n_FS = 1: 22 von 39 (56,4 %,
p = 0,52); n_FS = 5: 23 von 39 (59,0 %, p = 0,34); T = 0,3: 20 von 40
(50,0 %, p = 1,0). Ausser bei n_FS = 0 ist die Richtung statistisch nicht
vom Zufall zu unterscheiden; n_FS = 0 bleibt bei sieben Konfigurationen
und einem p von 0,047 ein Einzelbefund ohne Korrektur fuer Mehrfachtests.
Die Aussage "das LLM erkennt die Richtung der Subsumtion" ist durch die
Daten nicht gedeckt. Gedeckt ist: Das LLM erkennt, dass eine
hierarchische Beziehung besteht (41 von 42 Paaren als Subsumtion erkannt).


# Nachtrag 2026-10-04 (4) -- Mehrfachtest-Korrektur der Richtungsgenauigkeit

`R_analyze.py` weist unter `direction_multiple_testing` die Korrektur fuer
die Richtungsgenauigkeit aus. Familie: fuenf Konfigurationen (n_FS = 0, 1,
3, 5 und T = 0,3; die drei Durchgaenge von n_FS = 3 sind identisch und
zaehlen einmal), m = 5. Rohe p-Werte (exakter Binomialtest gegen 0,5):
n_FS = 0: 0,047 (25 von 37); n_FS = 1: 0,522; n_FS = 3: 0,533;
n_FS = 5: 0,337; T = 0,3: 1,0. Der kleinste Wert (n_FS = 0) wird nach
Bonferroni und nach Holm zu 0,235. Die Permutationsprüfung nach Westfall
und Young (20000 Ziehungen, Gold-Richtung je Paar gemeinsam fuer alle
Konfigurationen umgedreht, Statistik = kleinster p-Wert, Seed 20261004)
ergibt p_FWER = 0,113. Ein Unterschied zum Zufall ist damit fuer keine
Konfiguration gesichert. Mit 41 erkannten Subsumtionspaaren braeuchte es
unter Bonferroni (alpha = 0,01) mindestens 30 richtige (73 %).
Die Familie umfasst nur die Richtungsgenauigkeit; weitere gepruefte
Kennzahlen (Macro-F1, K-Mitgliedschaft) sind nicht eingerechnet.


# Nachtrag 2026-10-04 (5) -- Lieferung v0.4 und Primaerkonfiguration n_FS = 0

**Befund Few-Shot.** Im Produktionspfad liefert find_structural_shortcuts fuer
e-CF gegen das ESCO-Skelett 0 Treffer. Der Prompt enthaelt
"(keine Crosswalk-Beispiele verfuegbar)", die Produktion laeuft mit n_FS = 0.
Die Varianten mit G_struct-Ankern (n_FS = 1, 3, 5) sind Ablationen, die so
nie in Produktion liefen. Primaerkonfiguration der Auswertung ist daher
n_FS = 0 (Konfiguration prod0, drei Durchgaenge).

**Neuerzeugung.** Neues Projekt saeule_d_lieferung_v0_4_t_0_mistral_small_2603_*
(kein Wiederverwenden frueherer Klassifikationen), T = 0, Modell
mistral-small-2603, 800 Paare mit 3 Laeufen, etwa 35 Minuten, SHACL-konform
(Ontologie und Mappings). Konfiguration: redeliver_v0.4_run_config.json
(19 uncommittete getrackte Dateien zum Laufzeitpunkt, Few-Shot leer).
v0.3 blieb unveraendert. Alter Lauf (Projekt ..._20260831T171750Z):
mistral-small-latest, im Protokoll T = 0,0 (Feld fest im Code), 73 % der Paare
einstimmig.

| Kennzahl | v0.3 (alt) | v0.4 (neu) |
|---|---|---|
| Relationen (800 Paare) RELATED / A>B / B>A / EQUIV / kein Konsens | 568 / 156 / 43 / 0 / 33 | 556 / 192 / 48 / 1 / 3 |
| Konfidenz 1,0 / 0,67 / 0,33 | 583 (72,9 %) / 184 / 33 | 712 (89,0 %) / 85 / 3 |
| HubMapping gesamt | 364 | 440 |
| davon narrowMatch / broadMatch / exactMatch | 321 / 43 / 0 | 391 / 48 / 1 |
| LevelMapping | 113 + 8 | 113 + 8 |
| HarmonisedConcept (own_class) | 5 (A.2, D.5, D.6, D.8, D.9) | 3 (A.2, D.6, D.9) |
| Coverage / offene Reviews | 364 von 965 (37,7 %) / 601 | 440 von 999 (44,0 %) / 559 |
| E5 CQ1a / CQ1b / CQ3 / CQ4 | 0 / 156 / 5 / 113 | 1 / 192 / 3 / 113 |

E5 fuer v0.3 aus dem Backup reproduziert die Werte der Arbeit (0 / 156 / 5 / 113).
Der eine EQUIVALENT-Fall ist "Solution Deployment" gegen "solution deployment"
(identische Bezeichnung, Konfidenz 1,0). Drei Paare ohne Mehrheitsentscheid.

**Primaerauswertung n_FS = 0, T = 0, 68 Paare, drei Durchgaenge** (prod0_*).
Macro-F1 0,457 / 0,481 / 0,468 (Durchgang 1: KI95 0,343 bis 0,565).
K-Mitgliedschaft bei Mehrheit: P 0,980, R 0,906, F1 0,941 (49 uebernommen,
KI95 F1 0,887 bis 0,981); Einstimmigkeit F1 0,875. Klassen-F1 Durchgang 1:
EQUIVALENT 0,167 (1 Vorhersage, korrekt), A>B 0,540, B>A 0,296, RELATED 0,824.
Vorhersagen: 41 A>B, 19 RELATED, 7 B>A, 1 EQUIVALENT. Selbstkonsistenz 0,90 /
0,91 / 0,94; 92,6 % der Paare mit identischer Endrelation ueber die Durchgaenge.
Kosinus + LLM fuer EQUIVALENT (Leave-One-Out): Macro-F1 0,518 statt 0,457,
Differenz KI95 -0,007 bis 0,141, nicht gesichert. McNemar LLM gegen Kosinus fuer
K: 11 zu 5, p = 0,21.

**Richtung.** Der Einzelbefund n_FS = 0 aus dem Ablationslauf (25 von 37,
p = 0,047) bestaetigt sich in drei Wiederholungen derselben Konfiguration
nicht: 21/37 (p = 0,51), 22/39 (p = 0,52), 22/38 (p = 0,42). Die Richtung liegt
auch ohne Few-Shot auf Zufallsniveau.

**Streuung.** Derselbe Prompt, dieselbe Temperatur: Macro-F1 bei n_FS = 0
0,457 bis 0,499 ueber vier Laeufe. Unterschiede unter etwa 0,05 sind
Laufrauschen. n_FS = 3 (0,382 bis 0,397) liegt darunter, der Abstand ist
groesser als die Streuung, aber klein.

## G_manual_seed entfernt (11.10.2026)

Die Menge `G_manual_seed` (14 Paare aus Zare et al. 2025, Table 6) ist aus
Repository und Masterarbeit entfernt. Die Paare sind laut Quelle die als am
aehnlichsten identifizierten ESCO-Skills eines MPNet-Verfahrens fuer zwei
Dimension-4-Beispiele (K3, S4) der e-Competence A.8 und wurden dort nicht
fachlich validiert. Als Goldmenge sind sie daher nicht geeignet.

Entfernt: `eval/G_manual_seed.json`, die Auswertung in `E1_recall_k.py` und
`B_recall_fullpool.py`, die Eintraege in `B_recall_fullpool.json`,
`E1_recall_k.json` (Schluessel `g_manual`, der diese Menge enthielt),
`final_submission_numbers.json` und im Modellvergleich
`embedding_model_comparison_20261010/` (Nachtrag im Manifest). Die uebrigen
Werte bleiben unveraendert. Eintraege weiter oben in diesem Protokoll
dokumentieren den frueheren Stand. Sicherung: Git-Tag
`backup/pre-glit-entfernung-20261011`.
