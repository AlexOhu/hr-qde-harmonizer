# eval/ – Evaluationsumgebung für Kapitel 5

Dieses Verzeichnis enthält alle Skripte und Pläne für die
Evaluationsphase (Nunamaker: Experimentation).

---

## Reihenfolge der Ausführung

```
1. build_gold_manual.py   → G_manual aufbauen (manuelle Annotation)
2. E1_recall_k.py         → VH₁.₅ schließen  (k* bestimmen)
3. E2_few_shot.py         → VH₁.₆ schließen  (n_FS* bestimmen)
4. E3_confidence.py       → VH₁.₇ schließen  (θ* bestimmen)
5. E4_hdbscan.py          → VH₂.₃ schließen  (m* bestimmen)
6. E5_cq_evaluation.py    → CQ₁–CQ₄ prüfen   (qualitative Eval.)
```

E3 verwendet das Ergebnis von E2 (n_FS*). Alle anderen Schritte
sind unabhängig voneinander.

---

## Voraussetzungen

```bash
# Aus dem Repo-Root:
.venv\Scripts\activate

# API muss laufen (für E2, E3 – LLM-Aufrufe):
uvicorn app.api.main:app --reload

# Alle KQR müssen registriert und embedded sein (Status: bereit):
python -c "from app.services import kqr_service; [print(k.id, k.status) for k in kqr_service.list_kqr()]"
```

---

## Verzeichnisstruktur (nach vollständiger Ausführung)

```
eval/
├── gold/
│   ├── G_manual.json          # Manuell annotierte Goldmenge (80 Paare)
│   └── G_manual_review.csv    # Review-CSV vor Annotation
├── results/
│   ├── E1_recall_k.json
│   ├── E2_few_shot.json
│   ├── E3_confidence.json
│   ├── E4_hdbscan.json
│   └── E5_cq_evaluation.json
├── E1_recall_k.py
├── E1_recall_k_plan.md
├── E2_few_shot.py
├── E2_few_shot_plan.md
├── E3_confidence.py
├── E3_confidence_plan.md
├── E4_hdbscan.py
├── E4_hdbscan_plan.md
├── E5_cq_evaluation.py
├── E5_cq_evaluation_plan.md
├── build_gold_manual.py
└── README.md                  # Diese Datei
```

---

## Ergebnisse → Thesis

Alle Ergebnistabellen in Kapitel 5 sind mit `\ldots`-Platzhaltern
vorbereitet. Nach Ausführung der Skripte:

| Experiment | LaTeX-Datei | Tabellen-Label |
|---|---|---|
| E1 | `chapters/chapter_5/exp1_recall_k.tex` | `tab:exp1_recall_k` |
| E2 | `chapters/chapter_5/exp2_few_shot.tex` | `tab:exp2_few_shot` |
| E3 | `chapters/chapter_5/exp3_confidence.tex` | `tab:exp3_confidence` |
| E4 | `chapters/chapter_5/exp4_hdbscan.tex` | `tab:exp4_hdbscan` |
| E5 | `chapters/chapter_5/cq_evaluation.tex` | `tab:exp5_cq_uebersicht` |
