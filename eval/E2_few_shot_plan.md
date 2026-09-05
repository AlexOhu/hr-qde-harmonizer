# E2 – Few-Shot-Ablation: Anzahl der Few-Shot-Beispiele (VH₁.₆)

**Ziel:** Bestimme die optimale Anzahl Few-Shot-Beispiele `n_FS`,
die den Macro-F1 der LLM-Klassifikation auf `G_manual` maximiert.

**Auflöst:** VH₁.₆ (Few-Shot-Anzahl, zweiter Teil)

---

## Goldstandard: G_manual aufbauen

`G_manual` enthält 80 manuell annotierte e-CF↔ESCO-Paare,
balanciert über 4 Relationsklassen (je 20 Paare).

**Vorgehen:**
1. Starte die API: `uvicorn app.api.main:app --reload`
2. Öffne die Streamlit-UI: `streamlit run ui/app.py`
3. Führe eine Klassifikation für das KQR-Paar (e-CF, ESCO ICT) durch
4. Exportiere die ClassificationResult-Objekte:

```bash
.venv\Scripts\python.exe eval\build_gold_manual.py \
  --kqr-a ecf --kqr-b esco_ict \
  --n 80 --balanced \
  --output eval/gold/G_manual.json
```

`build_gold_manual.py` wählt je 20 Paare aus den persistierten
`ClassificationResult`-Objekten (`data/classification_results.json`)
und schreibt eine Review-CSV:

```
eval/gold/G_manual_review.csv
subject_id, subject_label, object_id, object_label, model_relation, gold_relation
```

**Annotation:** Die Spalte `gold_relation` wird manuell anhand
der e-CF-3.0-Spezifikation befüllt. Erlaubte Werte:
`EQUIVALENT`, `A_SUBSUMES_B`, `B_SUBSUMES_A`, `RELATED`.

```bash
# Nach manueller Annotation einlesen:
.venv\Scripts\python.exe eval\build_gold_manual.py --finalize \
  --review eval/gold/G_manual_review.csv \
  --output eval/gold/G_manual.json
```

---

## Durchführung

```bash
# Sweep n_FS ∈ {0, 1, 3, 5}
.venv\Scripts\python.exe eval\E2_few_shot.py \
  --gold eval/gold/G_manual.json \
  --n-fs-values 0 1 3 5 \
  --model claude-haiku-4-5 \
  --output eval/results/E2_few_shot.json
```

Das Skript ruft für jedes Paar aus `G_manual` den Dreifach-
Mehrheitsentscheid mit der jeweiligen Few-Shot-Anzahl auf.
Temperatur: 0. Kein Cache (Ergebnisse müssen unabhängig sein).

---

## Auswertung

```bash
.venv\Scripts\python.exe eval\E2_few_shot.py --report \
  --input eval/results/E2_few_shot.json
```

Ausgabe-Format (Konsole + `eval/results/E2_few_shot_report.txt`):

```
n_FS=0: Macro-F1=X.XX  F1[EQUIV]=X.XX  F1[SUBS]=X.XX  F1[REL]=X.XX  Acc=X.XX
n_FS=1: ...
n_FS=3: ...   <-- Initialwert (ADR-7)
n_FS=5: ...
Optimum: n_FS* = X  (Macro-F1 = X.XX)
```

---

## In die Thesis übernehmen

→ Werte in `chapters/chapter_5/exp2_few_shot.tex`,
  Tabelle `tab:exp2_few_shot`, eintragen.
→ `n_FS*` in `prompts/classification_prompt_template.txt`
  als Kommentar dokumentieren (kein automatischer Update nötig).
→ Falls `n_FS* ≠ 3`: ADR-7 in `chapters/chapter_4/architektur.tex`
  um Nachtrags-Kommentar ergänzen.
