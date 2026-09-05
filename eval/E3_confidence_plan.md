# E3 – Confidence-Schwellen: Precision/Recall-Trade-off (VH₁.₇)

**Ziel:** Bestimme die optimale Confidence-Schwelle θ*, die auf
`G_manual` den F1-Score maximiert, mit Präferenz für höhere Precision.

**Auflöst:** VH₁.₇ (empirische Validierung der Confidence-Schwellen)

**Wichtiger Hinweis:** Der Dreifach-Mehrheitsentscheid aus Prototyp 3
erzeugt genau drei diskrete Confidence-Werte:
- 0.33 → 1 von 3 Stimmen übereinstimmend
- 0.67 → 2 von 3 Stimmen übereinstimmend
- 1.00 → 3 von 3 Stimmen übereinstimmend

Die PR-Kurve hat daher genau drei Stützpunkte.

---

## Voraussetzung

`G_manual` muss aus E2 vorliegen:
`eval/gold/G_manual.json`

Die Klassifikationsergebnisse aus E2 (n_FS=n*) werden wiederverwendet:
`eval/results/E2_few_shot.json` (Lauf mit optimalem n_FS*)

---

## Durchführung

```bash
.venv\Scripts\python.exe eval\E3_confidence.py \
  --gold eval/gold/G_manual.json \
  --classifications eval/results/E2_few_shot.json \
  --n-fs OPTIMAL_N_FS \
  --thresholds 0.33 0.67 1.00 \
  --output eval/results/E3_confidence.json
```

Das Skript liest `mapping_confidence` aus den gespeicherten
`ClassificationResult`-Objekten und vergleicht die akzeptierten
Mappings (confidence ≥ θ) gegen die Goldlabels.

---

## Auswertung

```bash
.venv\Scripts\python.exe eval\E3_confidence.py --report \
  --input eval/results/E3_confidence.json
```

Ausgabe-Format:

```
θ=0.33: Precision=X.XX  Recall=X.XX  F1=X.XX  Mappings=NNN
θ=0.67: Precision=X.XX  Recall=X.XX  F1=X.XX  Mappings=NNN
θ=1.00: Precision=X.XX  Recall=X.XX  F1=X.XX  Mappings=NNN

Optimum (max F1): θ* = X.XX
Empfehlung (Precision-Bias): θ_op = X.XX
```

---

## In die Thesis übernehmen

→ Werte in `chapters/chapter_5/exp3_confidence.tex`,
  Tabelle `tab:exp3_confidence`, eintragen.
→ Operativen Schwellwert θ_op als Konstante in
  `app/config.py` (`CONFIDENCE_THRESHOLD`) setzen.
→ Initialwert 0.40 (zwischen den Stützpunkten 0.33 und 0.67)
  war eine vertretbare Initialwahl; dies im Thesis-Text bestätigen
  oder begründen, warum der tatsächliche Wert abweicht.
