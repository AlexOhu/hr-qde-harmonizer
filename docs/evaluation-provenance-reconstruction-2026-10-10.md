# Rekonstruktion: Embedding-Modell und E1–E5

> Nachtrag 11.10.2026: Die Menge `G_manual_seed` (Zare et al.) wurde aus Repository und Arbeit entfernt. Angaben dazu in diesem Dokument beschreiben den frueheren Stand.

Stand: 10. Oktober 2026. Dieses Dokument ordnet nur Primärartefakte des
Repositories zu. Ein Wert ist nur dann einem Modell zugeordnet, wenn das
Ergebnisartefakt oder die zugehörige Laufkonfiguration das Modell selbst
nennt. Der Git-Default ist kein Beleg für die Konfiguration eines zuvor
ausgeführten Laufs, da `EMBEDDING_MODEL` aus der Umgebung den Default in
`app/config.py` überschreibt.

## Kurzbefund

Die belegten produktiven Artefakte verwenden
`sentence-transformers/paraphrase-multilingual-mpnet-base-v2`:

* E4 am 31. August 2026 nennt dieses Modell direkt.
* Die v0.4-Lieferung vom 4. Oktober 2026 nennt es in ihrer
  Laufkonfiguration; damit ist das Modell für die Kandidatengenerierung der
  veröffentlichten Lieferung und deren E5-Auswertung belegt.
* Die am 4. Oktober gespeicherte Baseline-Auswertung nennt dasselbe Modell.

Der Git-Default war demgegenüber vom ersten versionierten Stand am
5. September bis Commit `a284afb` am 8. Oktober noch
`intfloat/multilingual-e5-large-instruct`. Das ist ein Konfigurationsfehler
in der historischen Coderevision, keine Widerlegung der genannten Läufe:
die v0.4-Laufkonfiguration beweist eine Umgebungsüberschreibung auf
paraphrase. Commit `a284afb` hat den Default danach an die belegte
Laufkonfiguration angeglichen.

E1 und der E1b-Lauf `G_levels` speichern ihr Embedding-Modell nicht. Ihre
Zahlen können deshalb aus dem Repository derzeit **nicht** belastbar einem
der beiden Modelle zugeordnet werden. Das ist die einzige modellrelevante
Lücke für die E1–E5-Zahlen. E2 und E3 klassifizieren feste Goldpaare mit
einem LLM; sie erzeugen keinen ANN-Kandidatenraum und hängen somit nicht vom
Embedding-Modell ab.

## Zeitleiste und Belegkette

| Zeitpunkt / Commit | Artefakt oder Änderung | Modellstatus | Folgen für die Arbeit |
|---|---|---|---|
| 31.08.2026 (Metadatum) | `eval/results/E4_hdbscan.json` | **paraphrase**, direkt in `_meta.embedding_model`; Raum: 956 ESCO + 45 e-CF = 1.001 | Historischer E4-Wert: H=0,6514, bei m=3: 716/1.001 Noise (71,53 %). |
| 31.08.2026 (Metadatum) | `E2_few_shot.json`, `E3_confidence.json` | LLM `mistral-small-latest`; kein Embedding-Lauf | E2/E3 beziehen sich auf 74 feste `G_manual`-Paare. |
| 05.09.2026, `fb195ee` | erster versionierter Repository-Stand | Code-Default: **E5** | Der Commit enthält bereits den obigen E4-Lauf mit paraphrase. Daher erfolgte die tatsächliche Umstellung spätestens vor diesem Commit, außerhalb der verfügbaren Git-Historie. |
| 06.09.2026, `f15f382` | `E1_recall_k_levels.json`, `G_levels` | nicht gespeichert | E1b: 101/113 bei k=5, 113/113 bei k=8; Modellzuordnung offen. |
| 06.09.2026, `c517974` | v0.3-Lieferung und `E5_cq_evaluation.json` | nicht gespeichert | E5 v0.3: CQ1–CQ4 = 0 / 156 / 5 / 113. Dieser Stand ist historisch und nicht der v0.4-Abgabestand. |
| 04.10.2026, `c928057` und `85c7daa` | Vollpool-Recall und Baselines | `B_baselines.json`: **paraphrase**; `B_recall_fullpool.json`: Modell nicht gespeichert | Die Vollpool-E1-Werte sind methodisch maßgeblicher als die reine Goldobjekt-Suche, bleiben aber ohne direkte Modell-Provenienz. |
| 04.10.2026, `412c4b4` | Lieferung v0.4, E5-v0.4, Laufkonfiguration | **paraphrase**, direkt in `redeliver_v0.4_run_config.json` und `data/deliverables/v0.4-20261004/run_config.json` | Produktive Lieferung: 800 Paare, Top-k=20, `mistral-small-2603`, T=0, drei LLM-Läufe. E5: 1 / 192 / 3 / 113. |
| 08.10.2026, `a284afb` | `app/config.py` | Default E5 → **paraphrase** | Der Code-Default wird erst hier mit den bereits belegten v0.4-Laufdaten synchronisiert. |
| 09.10.2026 (unversioniert) | `E4_membership_prod1302_20261009.json` | **paraphrase**, direkt gespeichert | Nachweis für den Produktionsraum: 1.302 ESCO + 45 e-CF, m=3: 166/1.347 Noise (12,32 %); dokumentiert außerdem SHA-256 der beiden Turtle-Eingaben. |

## Ergebnisinventar nach Experiment

| Experiment | Abgaberelevantes Ergebnisartefakt | Modellbezug | Bewertung der Zahlenbasis |
|---|---|---|---|
| E1 Recall@k | `B_recall_fullpool.json`; ergänzend `E1_recall_k.json` | nicht gespeichert | Vollpool: `G_struct` R@20=30/32=0,9375; `G_manual_seed` R@20=7/8=0,875; `G_manual` R@20=23/26=0,8846. Das Modell muss vor Verwendung in der Arbeit erneut mit einem Manifest belegt oder der Lauf wiederholt werden. |
| E1b Levels | `E1_recall_k_levels.json` | nicht gespeichert | R@5=101/113=0,8938; R@8=1,0 ist wegen des kleinen Zielraums eine konstruktive Obergrenze. Modellzuordnung offen. |
| E2 Few-Shot | `E2_few_shot.json`; Oktober-Rerun unter `rerun_2026-10/` | LLM, kein Embedding | Der JSON-Lauf vom 31.08. und der Oktober-Rerun sind verschiedene LLM-Läufe. Für v0.4 ist die Produktionskonfiguration `prod0`, n_FS=0, entscheidend; die n_FS=3-Reihe ist eine Variante. |
| E3 Confidence | `E3_confidence.json`; Oktober-Rerun unter `rerun_2026-10/` | LLM, kein Embedding | Die historische Schwellenkalibrierung und die v0.4-Reruns dürfen nicht vermischt werden. `final_submission_numbers.json` ordnet die v0.4-Primärreihe `prod0_nfs0_t0.0_pass3` zu. |
| E4 HDBSCAN | `E4_hdbscan.json`, `E4_hdbscan_prod1302.json` | **paraphrase** für den historischen Lauf direkt; Produktionslauf durch späteren Mitgliedschaftsexport bestätigt | 71,53 % und 12,32 % sind verschiedene Eingaberäume (1.001 bzw. 1.347 Konzepte), kein Zahlenwiderspruch. Für v0.4 ist der 1.347er Produktionsraum zu nennen. |
| E5 Kompetenzfragen | `rerun_2026-10/E5_cq_v0.4.json`, v0.4-Lieferung | **paraphrase** durch v0.4-Laufkonfiguration | CQ1–CQ4 = **1 / 192 / 3 / 113**. Die Zahlen beziehen sich auf die gespeicherte v0.4-Lieferung und sind synchron zu deren Konfiguration. |

## Widersprüche, Grenzen und sichere Aussagen

1. **Zeitpunkt des Modellwechsels:** Git kann nur belegen, dass der
   Default am 8. Oktober angepasst wurde. E4 belegt jedoch paraphrase am
   31. August. Die tatsächliche Umstellung geschah daher vor dem ersten
   Git-Commit oder wurde nur in der ignorierten `.env` vorgenommen. Ein
   späterer Wechsel von E5 zu paraphrase am 8. Oktober ist ausgeschlossen.

2. **Code gegen Ausführung:** `app/config.py` mit E5-Default und die
   v0.4-Laufkonfiguration mit paraphrase bestanden gleichzeitig. Weil
   `os.getenv("EMBEDDING_MODEL", Default)` den Environment-Wert priorisiert,
   ist die Laufkonfiguration die stärkere Evidenz für v0.4. Der Default war
   dennoch irreführend und wurde erst vier Tage später korrigiert.

3. **E1-Provenienz:** Keines der beiden gespeicherten E1-Ergebnisse enthält
   Modellname, Modellrevision, Eingabedatei-Hashes oder Laufzeitpunkt. Die
   Zahlen selbst sind gespeichert; die Behauptung, sie seien mit paraphrase
   gerechnet worden, ist gegenwärtig nur plausibel, nicht nachweisbar.

4. **E4-Provenienz:** `E4_hdbscan_prod1302.json` enthält keine IDs, Hashes
   oder Zeit. Die nachträgliche Mitgliedschaftsdatei vom 9. Oktober macht die
   Zuordnung zum 1.347er Produktionsraum überzeugend, ist aber kein
   gleichzeitiges Manifest des ursprünglichen Sweeps.

5. **Versionsmischungen vermeiden:** E5 v0.3 (0/156/5/113) und v0.4
   (1/192/3/113), die E4-Räume 1.001 und 1.347 sowie die E3-Reihen n_FS=0
   und n_FS=3 sind jeweils getrennte Läufe. Die Arbeit darf sie nicht in
   einer Kennzahl zusammenziehen.

## Zustand vor der Abgabe

| Prüfziel | Zustand | Nächste zwingende Evidenzhandlung |
|---|---|---|
| Produktive Lieferung, E5 und Modell | belegt und konsistent: v0.4/paraphrase | Zahlen in der Arbeit auf v0.4 1/192/3/113 festlegen. |
| E4 und Modell | weitgehend belegt: paraphrase; Produktionsraum 1.347 | Nur den Raum und die dazugehörige Zahl 166/1.347 nennen. |
| E2/E3 und Modell | Embedding-unabhängig | V0.4-Primärreihe eindeutig benennen, keine Variantenwerte vermischen. |
| E1/E1b und Modell | offen | Vor Abgabe beide Läufe mit einem versionierten Manifest (Modell, Revision, Git-HEAD, KQR-IDs, Eingabe-Hashes, Golddatei-Hash, Zeit) erneut ausführen oder die Modellbehauptung aus dem Text entfernen. |
| Code-Default und dokumentierte Modellwahl | aktuell synchron | Die relevante `.env`-Zeile beim finalen Lauf in ein nicht sensibles Manifest übernehmen, damit die Konfiguration nicht erneut nur implizit bleibt. |

## Primärquellen im Repository

* `app/config.py` und Git-Diff `aeef7a1..a284afb`
* `eval/results/E4_hdbscan.json`
* `eval/results/E1_recall_k.json`, `eval/results/E1_recall_k_levels.json`,
  `eval/results/B_recall_fullpool.json`
* `eval/results/E2_few_shot.json`, `eval/results/E3_confidence.json`,
  `eval/results/rerun_2026-10/R_analysis.json`
* `eval/results/E4_hdbscan_prod1302.json` und
  `eval/results/E4_membership_prod1302_20261009.json`
* `eval/results/rerun_2026-10/E5_cq_v0.4.json` und
  `eval/results/rerun_2026-10/redeliver_v0.4_run_config.json`
* `data/deliverables/v0.4-20261004/run_config.json`
* `eval/results/final_submission_numbers.json` (aktuelles, noch
  unversioniertes Audit-Artefakt)
