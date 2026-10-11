# Empirischer Modellvergleich für den HR-QDE Harmonizer

## Ergebnis in einem Satz

Der vollständige Zwei-Modell-Vergleich wurde am 10.10.2026 mit festen lokalen Snapshots durchgeführt. MPNet ist auf der semantischen e-CF→ESCO-Menge `G_manual` klar stärker und auf CPU rund 22-mal schneller; das E5-Modell ist dagegen auf der normativen DQR↔EQF-Menge `G_struct` stärker. E1b ist praktisch ausgeglichen: E5 gewinnt 2,65 Prozentpunkte bei Recall@3, beide Modelle sind bei Recall@5 und @8 gleich.

**Begriffstrennung:** Das **E5-Modell** ist `intfloat/multilingual-e5-large-instruct`. **Experiment E5** ist die Kompetenzfragen-Evaluation der Arbeit. Der vorliegende Vergleich betrifft nicht Experiment E5.

## Reproduzierbarkeitsstatus

- Ergebnisordner: `data/e1_e1b_run_20261010/modelvergleich_e5_mpnet_20261010/` im Thesis-Repository.
- Git bestätigt für diesen exakten Ordner die bestehende Ignore-Regel `.gitignore:27:/data/e1_e1b_run_20261010/`.
- Die 15 im MPNet-Baseline-Manifest aufgeführten Eingabedateien stimmen vollständig in SHA-256 überein; auch `e1_fullpool.json`, `e1b_levels.json` und das Baseline-README stimmen mit ihren Manifest-Hashes überein.
- MPNet: lokaler Snapshot `4328cf26390c98c5e3c738b4460a05b95f4911f5`, CPU, strikt offline.
- E5-Modell: lokaler Snapshot `274baa43b0e13e37fafa6428dbc7938e62e5c439`, CPU, strikt offline ausgeführt. Der Snapshot wurde ohne die für diesen PyTorch-Lauf unnötigen ONNX-Duplikate geladen; alle tatsächlich verwendeten Snapshotdateien sind im Manifest gehasht.
- Weder Code-Repository, LaTeX-Arbeit, produktive Konfiguration noch Lieferung wurden verändert. Alle erzeugten Dateien liegen im ignorierten Ergebnisordner.

## Vorverarbeitung und Implementationsprüfung

Für beide Modelle bleibt der Rohtext `pref_label + ". " + definition` unverändert. MPNet kodiert diesen Text symmetrisch für Query und Ziel und normalisiert die Vektoren. Das entspricht der aktuellen Funktion `app/pipeline/step2_embedding_prefilter/embed.py::embed_concepts()`.

Für das E5-Modell wurde vor einem möglichen Ergebnis die folgende Instruktion festgelegt:

> Given a competency or proficiency statement from one qualification framework, retrieve the semantically equivalent or most closely corresponding concept in the target qualification framework.

Querys wurden als `Instruct: …\nQuery: …` kodiert, Zieldokumente ohne Instruktion. Die Modellautoren verlangen dieses Template auf der Query-Seite und keine Instruktion auf der Dokumentseite; siehe [offizielle Modelldiskussion](https://huggingface.co/intfloat/multilingual-e5-large-instruct/discussions/4) und [Modellkarte/Repository](https://huggingface.co/intfloat/multilingual-e5-large-instruct/tree/274baa43b0e13e37fafa6428dbc7938e62e5c439). Die bestehende produktive Implementierung erzeugt jedoch nur einen symmetrisch verwendeten Vektor je Konzept und bildet diese Rollen nicht ab. Der isolierte Runner trennt deshalb Query- und Zielkodierung, ohne die Pipeline zu verändern.

Unvermeidbar modellabhängig bleiben Tokenizer, Vektordimension und modellinterne maximale Sequenzlänge. MPNet liefert hier 768-dimensionale Vektoren und ist auf 128 Token begrenzt; E5 liefert 1024 Dimensionen und ist auf 512 Token begrenzt. Diese Unterschiede wurden nicht künstlich angeglichen, weil das die spezifizierten Modelle verändern würde. Bei MPNet wurden 2 von 172 Querytexten, 1 von 32 `eqf_2d`-Texten und 3 von 956 Texten des historischen ESCO-Ausschnitts abgeschnitten; im aktuellen 1302er-ESCO-Skelett wurde kein Text abgeschnitten. Bei E5 trat in keinem ausgewerteten Text eine Trunkierung auf.

## Vergleichsergebnisse

Die exakten Einzelränge stehen in `mpnet_detailed.json` und `e5_detailed.json`; die aggregierten Differenzen und Trefferwechsel stehen in `vergleich.json`. Der MPNet-Lauf reproduziert sämtliche Werte der vorhandenen Baseline.

### Recall und Ränge

| Goldmenge | evaluierbar | Modell | R@1 | R@3 | R@5 | R@10 | R@15 | R@20 | R@30 | R@50 | R@100 | Medianrang | Maximalrang |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `G_manual` | 26/74 | MPNet | – | – | 0,6154 | 0,7692 | 0,8462 | 0,8846 | 0,8846 | 0,9615 | 0,9615 | 3,5 | 196 |
|  |  | E5 | – | – | 0,5000 | 0,5769 | 0,5769 | 0,6154 | 0,7308 | 0,8077 | 0,9231 | 5,5 | 326 |
| `G_manual@956` | 68/74 | MPNet | – | – | 0,4853 | 0,6912 | 0,8088 | 1,0000 | 1,0000 | 1,0000 | 1,0000 | 6,0 | 20 |
|  |  | E5 | – | – | 0,3088 | 0,4412 | 0,5441 | 0,5441 | 0,6618 | 0,7794 | 0,8529 | 12,0 | 216 |
|  |  | E5 | – | – | 0,2500 | 0,3750 | 0,3750 | 0,3750 | 0,6250 | 0,8750 | 1,0000 | 23,0 | 56 |
| `G_struct` | 32/32 | MPNet | – | – | 0,8125 | 0,9063 | 0,9063 | 0,9375 | 1,0000 | 1,0000 | 1,0000 | 2,0 | 26 |
|  |  | E5 | – | – | 0,9688 | 1,0000 | 1,0000 | 1,0000 | 1,0000 | 1,0000 | 1,0000 | 1,0 | 6 |
| `G_levels` (E1b) | 113/113 | MPNet | 0,2212 | 0,5752 | 0,8938 | – | – | – | – | – | – | 3,0 | 6 |
|  |  | E5 | 0,2124 | 0,6018 | 0,8938 | – | – | – | – | – | – | 3,0 | 6 |

### Rangänderungen und Trefferwechsel

| Goldmenge | Rang besser / gleich / schlechter mit E5 | Median Δ Rang | auffälliger Trefferwechsel |
|---|---:|---:|---|
| `G_manual` | 5 / 5 / 16 | +1,0 | @20: 0 gewonnen, 7 verloren |
| `G_manual@956` | 11 / 13 / 44 | +6,5 | @20: 0 gewonnen, 31 verloren |
| `G_struct` | 18 / 10 / 4 | −1,0 | @5: 5 gewonnen, 0 verloren |
| `G_levels` | 39 / 39 / 35 | 0,0 | @3: 23 gewonnen, 20 verloren |

Ein positives Rangdelta bedeutet einen schlechteren E5-Rang. `G_manual` verliert mit E5 bei Recall@20 26,92 Prozentpunkte. `G_struct` gewinnt bei Recall@5 15,63 Prozentpunkte. E1b zeigt viele paarweise Umschichtungen, aber geringe Aggregatdifferenzen: −0,88 Prozentpunkte bei @1, +2,65 bei @3 und Gleichstand bei @5.

### Laufzeit und Speicher

MPNet benötigte 39,74 s, E5 876,15 s (14 min 36 s) auf derselben CPU und mit Batchgröße 16. E5 war damit in diesem vollständigen Lauf 22,05-mal langsamer. Das Peak Working Set betrug 1.305.337.856 Byte (1,216 GiB) für MPNet und 1.529.413.632 Byte (1,424 GiB) für E5. Die Zeitdifferenz ist deskriptiv und umfasst die modellinhärenten Sequenzlängen; insbesondere die 956er-Sensitivitätsreferenz enthält lange Texte und dominiert den E5-Lauf.

## Interpretationsgrenzen

- `G_manual` wurde aus früheren Top-20-Kandidaten kuratiert. Die Werte sind deshalb kein unabhängiger Recall-Test und können das damalige Retrievalverfahren begünstigen.
- E1b hat nur sechs unterschiedliche evaluierbare DQR-Zielanker. Bei k = 8 wird effektiv der vollständige Pool zurückgegeben; R@8 = 1,0 ist konstruktiv und keine Qualitätsaussage.
- Die Goldmengen sind klein und domänenspezifisch. Es werden weder Signifikanz noch Generalisierung über diese Daten hinaus behauptet.
- Der Vergleich soll dieselben Goldmengen potenziell für die Modellwahl verwenden und ist deshalb explorativ.
- Retrieval-Ergebnisse allein belegen weder E4-Clustering, die Qualität der finalen Lieferung noch Experiment E5.

## Rekonstruktion des Modellverlaufs

### Belegte Tatsachen

1. **29.07.2026:** Thesis-Commit `250406154f69af03dadb0283269572543ef133cf` führte `chapters/chapter_4/embeddingModel.tex` ein und kommunizierte das E5-Modell als Wahl. Das ist ein dokumentierter Kandidatenstand, aber kein unveränderlicher methodischer Zwang.
2. **31.08.2026:** `eval/results/E4_hdbscan.json` belegt MPNet unmittelbar in `_meta.embedding_model` für 956 ESCO- und 45 e-CF-Konzepte. Das Artefakt war bereits im ersten Code-Commit `fb195ee8f89f4c50526966355da726800e575edd` vom 05.09. enthalten.
3. **05.09.2026:** Der initiale Code-Stand war widersprüchlich: `app/config.py` und `.env.example` hatten E5 als Default, während README, Agentenanweisungen und E4-Unterlagen MPNet nannten. Da Umgebungsvariablen den Code-Default überschreiben, beweist der Default allein kein tatsächlich verwendetes Laufmodell.
4. **17.09.2026:** Thesis-Commit `fbbc58ad07480f197e156207b2fdfe3c011aa200` ersetzte E5 durch MPNet in Modell-, Architektur- und Anhangstexten. ADR-6 begründet MPNet mit Mehrsprachigkeit, lokaler Ausführung und dem Entfall einer Instruktionsvorverarbeitung; E5 blieb Alternative.
5. **04.10.2026:** Die v0.4-Laufkonfiguration und `eval/results/B_baselines.json` nennen MPNet. `data/deliverables/v0.4-20261004/run_config.json` dokumentiert den produktiven Lauf ebenfalls mit MPNet.
6. **08.10.2026:** Code-Commit `a284afb34c1b958b296cf4459db964632183baa2` synchronisierte den Default in `app/config.py` und `.env.example` auf MPNet.
7. **09.–10.10.2026:** Der E4-Mitgliedschaftslauf im Produktionsraum nennt MPNet; der aktuelle E1/E1b-Neulauf manifestiert MPNet, Snapshot, Hashes und Umgebung erstmals vollständig.
8. Historische E1/E1b-JSONs enthalten keinen Modellnamen, keine Revision und keine Input-Hashes. Der aktuelle MPNet-Neulauf reproduziert ihre Zahlen, belegt aber nicht rückwirkend, welches Modell den historischen Lauf erzeugte.
9. Der verfügbare frühere Codex-Chat **„Modellwechsel begründen“** (`01a1267b-eedc-7693-b637-d27a96a7517d`) enthält mögliche Rechtfertigungen, bezeichnet sie ohne identischen Vergleich aber selbst als Hypothesen. Er dokumentiert keinen ursprünglichen Anlass oder exakten Entscheidungszeitpunkt.

### Nicht belegbar beziehungsweise nur plausibel

- MPNet wurde spätestens für den belegten E4-Lauf am 31.08. verwendet; wann die operative Umstellung begann und welcher konkrete Anlass sie auslöste, bleibt offen.
- Der Commit vom 17.09. ist der erste klare versionierte Thesis-Wechsel, aber nicht zwingend der tatsächliche Entscheidungszeitpunkt.
- Die einfachere symmetrische Integration ist eine dokumentierte Architekturbegründung. Sie ist weder als historischer Auslöser noch als empirisch überlegene Retrieval-Qualität belegt.
- Die damalige Thesis-Aussage, E1 sei mit MPNet gelaufen, war bis zum manifestierten Neulauf am 10.10. keine belastbare Provenienzbehauptung.

## Entscheidungsvorlage

### Was spricht für welches Modell?

**Für MPNet sprechen:** deutlich bessere Werte auf beiden e-CF→ESCO-Mengen, 22-fach geringere CPU-Laufzeit im vollständigen Vergleich, vorhandene E4- und v0.4-Laufbelege sowie die direkte Passung zur symmetrischen produktiven Embedding-Schnittstelle. **Für das E5-Modell sprechen:** klar bessere Ränge auf `G_struct`, ein kleiner Vorteil bei E1b Recall@3 sowie die größere Sequenzgrenze ohne beobachtete Trunkierung. Diese Vorteile sind aufgabenspezifisch; E5 ist nicht durchgehend schlechter.

### Reicht die Architektur-/Integrationsbegründung für MPNet?

Die Architektur-/Integrationsbegründung wird nun durch einen praktisch relevanten Unterschied auf den anwendungsnahen e-CF→ESCO-Vollpools gestützt. Für die aktuelle Pipeline spricht der Vergleich daher für das Beibehalten von MPNet. Wegen der Top-20-Kuration von `G_manual`, nur acht evaluierbaren Seed-Paaren und der gegenläufigen `G_struct`-Leistung darf daraus keine allgemeine Überlegenheit von MPNet abgeleitet werden. Eine Aussage sollte auf „besser geeignet für die hier geprüfte aktuelle Retrieval-Konfiguration“ begrenzt bleiben.

### Was müsste bei einer späteren Entscheidung für das E5-Modell neu laufen?

- getrennte Query-/Zielembeddings und sämtliche Embedding-Caches,
- E1 und E1b einschließlich Vollpool-Rängen,
- E4-HDBSCAN und die E4-Mitgliedschaftsauswertung,
- embeddingbasierte Baselines in `eval/B_baselines.py`,
- produktive ANN-Kandidatengenerierung für alle KQR-Paare,
- alle nachgelagerten Klassifikations-/Review-/Disjunktheitsläufe, deren Kandidaten aus diesem Vorfilter stammen,
- Experiment E5 auf der neu erzeugten Lieferung,
- sämtliche v0.4-Nachfolge-Lieferartefakte, insbesondere Run-Konfiguration/Manifest, Mapping-/Review-Zustand, SSSOM- und Ontologieexporte sowie abgeleitete Kennzahlen.

Ein Modellwechsel ist keine bloße Konfigurationsänderung: Die aktuelle Schnittstelle muss zuerst Query- und Dokumentrollen korrekt modellieren.

### Welche E2-/E3-Ergebnisse sind embeddingsunabhängig?

`eval/E2_few_shot.py`, `eval/E3_confidence.py`, `eval/R_rerun.py` und `eval/scripts/e3_isolation_run.py` klassifizieren feste Goldpaare und rufen keine Embeddings auf. Ihre eigentliche Ergebnisberechnung ist daher modellunabhängig; ein reiner Embedding-Modellwechsel erzwingt keinen E2-/E3-Neulauf. Zu prüfen bleiben jedoch:

- `G_manual` stammt aus früheren Top-20-Kandidaten und ist als Datengrundlage nicht unabhängig vom früheren Retrievalprozess.
- `eval/B_baselines.py` verwendet Kosinusähnlichkeiten und ist direkt embeddingabhängig, auch wenn es E2/E3 gegenübergestellt wird.
- Produktionsläufe verwenden den Embedding-Vorfilter zur Kandidatenauswahl. Deren Klassifikation und Lieferung ändern sich indirekt, obwohl die isolierten E2/E3-Skripte feste Paare verwenden.
- Experiment E5 wertet eine gespeicherte Lieferung aus und ist daher indirekt vom Kandidatenraum und damit vom Embedding-Modell abhängig.

## Begrenzte Schlussfolgerung

Auf diesen Goldmengen und mit der vorab festgelegten, modellgerechten E5-Instruktion ist MPNet für die aktuelle e-CF→ESCO-Kandidatensuche praktisch günstiger: höhere Recall-Werte, bessere typische Ränge und erheblich geringere CPU-Laufzeit. E5 ist bei normativen DQR↔EQF-Strukturpaaren besser und bei E1b weitgehend gleichwertig. Das Muster spricht gegen eine pauschale Modellrangfolge und für eine aufgabenspezifische Wirkung.

Für die bestehende Gesamtpipeline ist das Beibehalten von MPNet die besser gestützte Entscheidung. Der Vergleich allein validiert jedoch weder E4-Clustering noch Lieferung oder Experiment E5 und rechtfertigt keine Signifikanz- oder Generalisierungsbehauptung. Die Auswahl bleibt explorativ, weil Goldmengen zugleich zur Entscheidung herangezogen werden.
