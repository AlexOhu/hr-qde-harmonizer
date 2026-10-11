# eval/ – Evaluationsumgebung für Kapitel 5

Dieses Verzeichnis enthält alle Skripte für die
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
├── E2_few_shot.py
├── E3_confidence.py
├── E4_hdbscan.py
├── E5_cq_evaluation.py
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

## G_levels.json
Goldmenge für K_levels: e-CF Dimension-3-Proficiency-Beschreibungen ↔
DQR-Niveau-Anker.
Quelle: e-CF 3.0 (CWA 16234-1:2014) (normative Crosswalk-Tabelle).
Mapping_justification: semapv:ManualMappingCuration
Paare: 113 (106 e-CF-Levelknoten × 1 DQR-Anker, außer e-1 × 2 DQR-Anker)
Erstellt: 2026-09-06

## Weitere Skripte und Protokolle (Stand Übergabe, Oktober 2026)

Über die Reihenfolge E1 bis E5 hinaus enthält `eval/`:

| Datei | Zweck |
|---|---|
| `B_baselines.py`, `B_recall_fullpool.py` | Baselines für Kapitel 5 (lexikalisch bzw. Recall über den vollen Kandidatenpool) |
| `S_sample.py`, `S_analyze.py`, `annotation/` | Stichprobe und Auswertung der blinden Zweitannotation |
| `R_rerun.py`, `R_analyze.py`, `R_tables.py` | Rerun Oktober 2026 (Primärkonfiguration n_FS = 0), Ergebnisse unter `results/rerun_2026-10/` |
| `scripts/e3_isolation_run.py` | Isolationslauf zur E3-Neukalibrierung |
| `PROTOKOLL.md` | Ausführungsprotokoll mit Abweichungen und Zahlenständen |
