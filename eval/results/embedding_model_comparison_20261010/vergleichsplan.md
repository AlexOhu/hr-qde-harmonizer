# Reproduzierbarer Vergleichsplan: E5-Modell gegen MPNet

Stand vor Berechnung: 2026-10-10 (Europe/Vienna)

## Zweck und Abgrenzung

Verglichen werden `intfloat/multilingual-e5-large-instruct` (im Folgenden **E5-Modell**) und `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (**MPNet**) für die Retrieval-Aufgaben E1 und E1b des HR-QDE Harmonizers. **Experiment E5** bezeichnet dagegen die Kompetenzfragen-Evaluation und ist nicht Gegenstand dieses Laufs. Der Vergleich prüft nur die Retrieval-Eignung auf den angegebenen Goldmengen; er belegt weder E4-Clustering, Lieferqualität noch Experiment E5. Da dieselben Goldmengen potenziell zur Modellwahl dienen, ist der Vergleich explorativ.

## Unveränderliche Eingaben und Pools

- E1 gemäß `eval/B_recall_fullpool.py`:
  - `eval/gold/G_manual.json` gegen den vollständigen Pool `esco_skeleton_oberhuber` (1302 Konzepte), zusätzlich historische Sensitivitätsreferenz gegen `esco_v1_2_ict_ausschnitt` (956 Konzepte),
  - `eval/G_struct.json` gegen `eqf_2d`.
- E1b gemäß `eval/E1_recall_k.py`: `eval/G_levels.json`, Query-KQR `ecf_level`, Ziel-KQR `dqr_1d`, k = 1, 3, 5, 8. Der Auswertungspool besteht wie im Skript aus den unterschiedlichen Gold-Objekten der evaluierbaren Paare.
- Konzepttext für beide Modelle: unveränderte Konkatenation `pref_label + ". " + definition`; fehlende Definition wird durch die leere Zeichenfolge ersetzt, anschließend nur äußeres Whitespace entfernt.
- Vor der Nutzung der vorhandenen MPNet-Baseline müssen sämtliche im Baseline-Manifest erfassten Eingabe-Hashes sowie die Ergebnis-Hashes übereinstimmen.

`G_manual` wurde aus früheren Top-20-Kandidaten kuratiert und ist daher kein unabhängiger Recall-Test. E1b enthält nur sechs unterschiedliche evaluierbare DQR-Zielanker; bei k = 8 (effektiv k = 6) ist Recall konstruktiv 1,0.

## Modellrevisionen und Vorverarbeitung

- MPNet: lokaler Hugging-Face-Snapshot `4328cf26390c98c5e3c738b4460a05b95f4911f5`; derselbe Text auf Query- und Zielseite; `SentenceTransformer.encode(..., normalize_embeddings=True)`.
- E5-Modell: nur bei vorhandenem lokalem Snapshot und mit dessen unveränderlicher Snapshot-/Commit-ID. Vor Einsicht in E5-Resultate festgelegte Retrieval-Instruktion:

  `Given a competency or proficiency statement from one qualification framework, retrieve the semantically equivalent or most closely corresponding concept in the target qualification framework.`

  Querytext: `Instruct: <Instruktion>\nQuery: <Konzepttext>`. Ziel-/Dokumenttext: nur `<Konzepttext>`, ohne Instruktion. Query- und Zielvektoren werden getrennt berechnet und L2-normalisiert. Die Instruktion bleibt für alle E1- und E1b-Queries identisch und wird nach Sichtung der Resultate nicht verändert. Dieses Rollenmodell kann die produktive Funktion `embed_concepts()` nicht ausdrücken, da sie genau einen symmetrisch verwendeten Vektor je Konzept erzeugt; deshalb ist gegebenenfalls ein isolierter Runner ausschließlich in diesem ignorierten Ergebnisordner zulässig.

## Ranking, Metriken und Tie-Behandlung

- Exakte Kosinus-/Inner-Product-Suche im vollständigen jeweiligen Zielpool; keine ANN-Näherung.
- 1-basierter Goldrang: `1 + Anzahl(score > Goldscore)`. Gleichstände mit dem Goldscore teilen damit den besten Rang; dies entspricht `B_recall_fullpool.py`.
- Recall@k für E1: k = 5, 10, 15, 20, 30, 50, 100. Zusätzlich werden die exakten Einzelränge ausgegeben.
- Recall@k für E1b: k = 1, 3, 5, 8, mit effektivem k begrenzt auf die Poolgröße. Zusätzlich exakte Einzelränge.
- Modellvergleich je Goldmenge: Differenz der Recall-Werte, Änderungen der Einzelränge, Trefferwechsel pro k sowie zusammenfassend Median/Maximum der Ränge.
- Laufzeit und Spitzen-Arbeitsspeicher werden nur berichtet, wenn sie im isolierten Prozess zuverlässig messbar sind. CPU-Peak-RSS wird unter Windows pro Prozess erhoben; modellübergreifende Aussagen bleiben wegen Cache-, Lade- und Systemeinflüssen deskriptiv.

## Reproduzierbarkeit und Abbruchregeln

- Keine kostenpflichtigen APIs, keine Ersatzmodelle, keine Änderung an LaTeX, produktiver Konfiguration, Lieferung oder Code-Repository.
- Der Runner lädt ausschließlich explizite lokale Snapshotpfade (`local_files_only=True`). Fehlt das E5-Modell lokal oder verhindert die Ressourcenausstattung den Lauf, wird der konkrete Blocker dokumentiert; MPNet-Werte werden nicht als E5-Ersatz interpretiert.
- Das Abschlussmanifest enthält lokale/UTC-Zeitstempel, beide Git-HEADs und Dirty-Status, Modell-IDs und Revisionen, genaue Vorverarbeitung, Python-/Bibliotheksversionen, Gerät, Aufrufe und SHA-256 aller Eingaben und Ergebnisdateien.
- Alle neu erzeugten Dateien verbleiben in diesem Ordner. Git bestätigt für den exakten Pfad die Ignore-Regel `/.gitignore:27:/data/e1_e1b_run_20261010/`.
