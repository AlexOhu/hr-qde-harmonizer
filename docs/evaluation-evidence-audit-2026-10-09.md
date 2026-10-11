# Evidenzaudit: E1, E3, E4 und Backend-Testumfang

> Nachtrag 11.10.2026: Die Menge `G_manual_seed` (Zare et al.) wurde aus Repository und Arbeit entfernt. Angaben dazu in diesem Dokument beschreiben den frueheren Stand.

Stand: 9. Oktober 2026. Dieser Vermerk trennt die Primärartefakte der
jeweiligen Läufe. Er legt keine Zahlen allein aufgrund von Textstellen fest.

## Prüfumfang und Quellen

Die Untersuchung stützt sich auf gespeicherte Ergebnis-JSONs, die Skripte, die
ihre Kennzahlen berechnen, die Rohprotokolle der LLM-Durchgänge und die lokale
Test-Sammlung. Die folgenden Dateien waren bei Beginn unversioniert und werden
nur als zusätzliches, nicht überschriebenes Reproduktionsartefakt verwendet:

- `eval/E4_membership.py`
- `eval/results/E4_membership_prod1302_20261009.json`
- `eval/results/final_submission_numbers.json`

Der Vermerk selbst legt keine Zahlen allein aufgrund von Textstellen fest.

## Ausdrücklich ausgeklammert: E5

Der DQR-2D-Vergleich für E5 läuft während dieses Audits erneut. Daher werden
keine E5-Kennzahl, kein Nenner und keine E5-Textstelle aus dem vorliegenden
Zwischenstand abgeleitet oder geändert.

## E1: Recall@k im vollständigen Zielpool

`eval/E1_recall_k.py` und sein Ergebnis `eval/results/E1_recall_k.json`
bewerten den Kandidatenraum, der nur aus den in der jeweiligen Goldmenge
vorkommenden Zielobjekten besteht. Für kleine Goldmengen ist dieser Raum klein
und die dortigen Werte sind deshalb keine Messung des produktiven Suchraums.
`eval/B_recall_fullpool.py` misst dagegen dieselben Paare gegen den
vollständigen Ziel-KQR und schreibt `eval/results/B_recall_fullpool.json`.
Der Vollpool-Lauf verwendet `eval/G_struct.json`,
`eval/G_manual_seed.json`, `eval/gold/G_manual.json` sowie die registrierten
Embeddings für `eqf_2d`, `esco_skeleton_oberhuber` bzw. für den historischen
Vergleich `esco_v1_2_ict_ausschnitt` (`eval/B_recall_fullpool.py:24-94`).

| Goldmenge / Zielpool | Auswertbare Paare | Recall@20 | Recall@30 | weiterer Befund |
|---|---:|---:|---:|---|
| `G_struct` / `eqf_2d` (32) | 32 | 30/32 = **0,9375** | 32/32 = **1,0000** | Vollständige normative Dimensionsmenge. |
| `G_manual_seed` (Zare) / ESCO-Skelett (1302) | 8 | 7/8 = **0,8750** | 8/8 = **1,0000** | Bei k=20 wird die 90-Prozent-Schwelle nicht erreicht. |
| `G_manual` / ESCO-Skelett (1302) | 26 | 23/26 = **0,8846** | 23/26 = **0,8846** | Erst @50: 25/26 = **0,9615**; maximaler Rang 196. |

Die Werte stehen in `eval/results/B_recall_fullpool.json:15-102`. Der
`G_manual`-Wert ist als unabhängiger Recall-Schätzer eingeschränkt, weil diese
Goldmenge aus Top-20-Kandidaten des abgelösten 956er-Ausschnitts kuratiert
wurde (`eval/B_recall_fullpool.py:27-30`). Für den Produktionsparameter
belegt E1 deshalb einen Kompromiss, aber weder eine allgemeine
90-Prozent-Bestätigung von k=20 noch eine globale Coverage-Empfehlung für
k=30.

## E4: HDBSCAN und Hopkins

### Zwei unterschiedliche, belegte Räume

| Raum / Ergebnisartefakt | Eingaben | m = 3 | Hopkins | Rechnung und Befund |
|---|---|---:|---:|---|
| historischer Kompetenzraum, `eval/results/E4_hdbscan.json` | `esco_v1_2_ict_ausschnitt` (956) + `ecf` (45) = 1.001 Konzepte | 716 Noise, 20 Cluster | 0,6514 | `716 / 1.001 = 0,715284…`, im Artefakt als 0,7153 bzw. **71,53 %** gespeichert. |
| Produktionsraum, `eval/results/E4_hdbscan_prod1302.json` | 1.302 ESCO-Skelettkonzepte + 45 e-CF-Konzepte = 1.347 Konzepte | 166 Noise, 3 Cluster | 0,6718 | `166 / 1.347 = 0,123237…`, im Artefakt als 0,1232 bzw. **12,32 %** gespeichert. |

Der historische Raum ist im Ergebnisartefakt selbst ausdrücklich beschrieben:
`eval/results/E4_hdbscan.json:3-11`; seine H- und m=3-Werte stehen in
`eval/results/E4_hdbscan.json:13-22`. Der Produktionswert steht in
`eval/results/E4_hdbscan_prod1302.json:2-11`. Der Parameter-Sweep berechnet
Noise als Anzahl der Label `-1` geteilt durch alle Eingabevektoren
(`eval/E4_hdbscan.py:107-139`), Hopkins mit festem `random_state=42`
(`eval/E4_hdbscan.py:38-65`).

Damit sind 12,32 % und 71,53 % **kein Zahlenwiderspruch**, sondern Ergebnisse
verschiedener Eingabemengen. Die Standard-Allowlist des E4-Skripts ist dabei
weiterhin der historische Raum (`eval/E4_hdbscan.py:30-35`); der 1.347er-Wert
muss daher als ausdrücklich mit `esco_skeleton_oberhuber` und `ecf`
ausgeführter Produktionslauf bezeichnet werden, nicht als Standardlauf.

### Reproduktionsbeleg für den Produktionsraum

Der vollständige Mitgliedschaftsexport vom 9. Oktober verwendet
`min_cluster_size = 3`, HDBSCAN 0.8.44 und dokumentiert die konkreten
Eingabedateien sowie ihre SHA-256-Hashes:

- `data/formalized/esco_skeleton_oberhuber.ttl`, 1.302 Konzepte,
  `6b5be40e222c05b2333080303dc50191b379e9652affba4b03fc307c7de7fd08`
- `data/formalized/ecf.ttl`, 45 Konzepte,
  `228b8ebe0a5470ef80b1438157f35d7732de2f170902c0181bca5450b39ab0c8`

Beleg: `eval/results/E4_membership_prod1302_20261009.json:2-19`. Die
Mitgliedschaften ergeben 166 Noise, 4 + 1.151 + 26 nicht-Noise-Punkte und
damit wieder 1.347 (`eval/results/E4_membership_prod1302_20261009.json:20-55`).
Das bestätigt unabhängig die Noise-Rate des gespeicherten Produktions-Sweeps.

Einschränkung: `E4_hdbscan_prod1302.json` protokolliert selbst weder
KQR-IDs, Eingabe-Hashes noch den Aufrufzeitpunkt. Der Git-Commit
`a284afb34c1b958b296cf4459db964632183baa2` fügte es am 8. Oktober 2026
hinzu. Die Zuordnung des Hopkins-Werts 0,6718 zu den obigen Dateien folgt aus
der Gesamtzahl 1.347 und wird durch den späteren Mitgliedschaftsexport
gestützt, ist im Sweep-JSON aber nicht vollständig provenance-gebunden.

## E3: Selbstkonsistenz (Einstimmigkeit)

Die hier verglichenen Raten sind nicht die E3-Precision/Recall-Schwellenwerte,
sondern die Selbstkonsistenz der drei Klassifikationsaufrufe eines Paars. Die
Auswertung definiert sie als `votes_for_final == runs_total` und dividiert die
Anzahl dieser Paare durch alle Paare (`eval/R_analyze.py:114-129`). Die
Rohprotokolle speichern je Paar alle drei Einzelantworten sowie Zähler und
Nenner (`eval/R_rerun.py:116-142`).

| Konfiguration | Stichprobe | drei Durchgänge | exakte Selbstkonsistenz | Textliche Kurzform |
|---|---:|---|---|---|
| **Primär-/Produktionskonfiguration** `prod0`, n_FS = 0, T = 0, Modell `mistral-small-2603` | 68 von 74 `G_manual`-Paaren | Pass 1–3 | 61/68 = 0,8971; 62/68 = 0,9118; 64/68 = 0,9412 | **89,7–94,1 %** (gerundet 90–94 %) |
| Variante `prod`, n_FS = 3, T = 0, gleiches Modell | 68 von 74 `G_manual`-Paaren | Pass 1–3 | 63/68 = 0,9265; 67/68 = 0,9853; 66/68 = 0,9706 | **92,6–98,5 %** (gerundet 93–99 %) |

Die Dateien und Werte sind direkt in
`eval/results/rerun_2026-10/R_analysis.json:217-244`, `:282-309` und
`:347-374` (prod0) sowie `:412-439`, `:475-502` und `:538-565` (n_FS=3)
gespeichert. Die Rohdateien bestätigen für beide Serien drei Aufrufe pro Paar,
68 verwendete Paare, n_FS, Temperatur, Modell und Zeitstempel, zum Beispiel
`eval/results/rerun_2026-10/prod0_nfs0_t0.0_pass1.json:3-22` und
`eval/results/rerun_2026-10/prod_nfs3_t0.0_pass1.json:3-22`.

`prod0` ist nicht nur eine Namensvariante: Der Rerun-Code erklärt n_FS = 0
als Produktionspfad, da keine Structural Shortcuts vorliegen, und n_FS = 3
als Variante (`eval/R_rerun.py:44-54`; `eval/R_analyze.py:202-218`). Daher
ist für eine Aussage über den v0.4-Produktionspfad die Reihe **89,7–94,1 %**
maßgeblich. Die Reihe **92,6–98,5 %** bleibt als Ablations-/Variantenbefund
belegbar und darf nicht ohne Kennzeichnung vereinheitlicht werden.

Die historische Datei `eval/results/E3_confidence.json:1-31` ist ein anderer
Lauf (31. August 2026, 74 Paare, n_FS = 3, Alias
`mistral-small-latest`) und enthält keine Selbstkonsistenzrate. Sie kann die
Oktoberwerte daher weder bestätigen noch widerlegen.

## Backend-Testumfang

| Aussage | Beleg | Bewertung |
|---|---|---|
| **235 Tests gesammelt** | Lokaler, cachefreier Befehl vom 9. Oktober 2026: `python -m pytest tests --collect-only -q -p no:cacheprovider` → `235 tests collected in 5.16s`. | Direkt belegt; dies ist der aktuelle Zähler. |
| 12 übersprungene Testinstanzen | `tests/test_eqf_formalize.py:19,25-27,45-111`: komplette Datei mit 9 Einzeltests und Parametrisierung über 3 Werte, alle unter `skipif` falls `data/formalized/eqf_2017.ttl` fehlt. Die Datei fehlt im aktuellen Arbeitsbaum. | 9 + 3 = **12**; erklärt die dokumentierte Skip-Zahl. |
| 223 bestanden, 12 übersprungen | `README.md:86-89` und `CLAUDE.md:24-26`. | Mit 235 gesammelten und den 12 bedingt übersprungenen Instanzen arithmetisch konsistent (`235 - 12 = 223`). Ein kompletter neuer Lauf wurde für diesen Auditvermerk nicht als Ersatz für den dokumentierten Abgabestand durchgeführt. |
| 231 insgesamt, 219 bestanden, 12 übersprungen | Historischer Git-Blob `624ecd61a02…:ABSCHLUSSBERICHT_SAEULE_D_V03.md:86-92`, Commit vom 6. September 2026. | Archivierter v0.3-Stand, **nicht** der aktuelle Abgabestand. |

Folgerung: Für den aktuellen Abgabestand lautet die korrekte Umfangsangabe
**235 gesammelte Backend-Tests**. Falls ein Ausführungsresultat angegeben wird,
ist der gegenwärtig dokumentierte Stand **223 bestanden, 12 übersprungen**;
die Zahl 231/219/12 darf nur mit ihrem historischen v0.3-Stichtag verwendet
werden.

## Ergebnis für die Textabstimmung

- E4 muss den Raum explizit nennen. Für v0.4/den ESCO-Skeleton-Produktionsraum
  sind bei m = 3 **H = 0,6718** und **166/1.347 = 12,32 % Noise** belegt;
  für den historischen 956er-Ausschnitt sind es **H = 0,6514** und
  **716/1.001 = 71,53 % Noise**.
- Bei E3 ist „90–94 %“ als gerundete Primärkonfiguration und „93–99 %“ als
  n_FS=3-Variante jeweils richtig, aber nicht austauschbar.
- Die Testzahl 231 ist für den aktuellen Stand überholt.
