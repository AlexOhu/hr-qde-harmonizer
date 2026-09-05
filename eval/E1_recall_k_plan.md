# E1 – Recall@k: ANN-Suchparameter (VH₁.₅)

**Ziel:** Bestimme das minimale `k`, sodass ≥ 90 % aller Goldpaare
aus `G_struct` im FAISS-Kandidatenraum enthalten sind.

**Auflöst:** VH₁.₅ (Parameter k der ANN-Suche)

---

## Goldstandard: G_struct

Die strukturelle Goldmenge wird aus den ELM-Rohdaten extrahiert.
ELM enthält explizite `elm:relatedEscoSkill`-Prädikate, die
bekannte Korrespondenzen zu ESCO-Skills ausdrücken.

```bash
# Schritt 1: ELM laden und Goldpaare extrahieren
cd E:\Fernuni\Master\Masterarbeit\hrqde-harmonizer
.venv\Scripts\python.exe eval\E1_recall_k.py --extract-gold
# Ausgabe: eval/gold/G_struct.json
```

Format von `G_struct.json`:
```json
[
  {"subject_id": "elm:...", "object_id": "esco:skill/..."},
  ...
]
```

---

## Durchführung

```bash
# Sweep k ∈ {5, 10, 15, 20, 30}
.venv\Scripts\python.exe eval\E1_recall_k.py \
  --gold eval/gold/G_struct.json \
  --k-values 5 10 15 20 30 \
  --output eval/results/E1_recall_k.json
```

Das Skript lädt den gecachten FAISS-Index aus `data/kqr_registry.json`
(via `kqr_service`) und führt für jeden k-Wert eine ANN-Suche durch.

## Auswertung

```bash
.venv\Scripts\python.exe eval\E1_recall_k.py --report \
  --output eval/results/E1_recall_k.json
```

Ausgabe-Format:

```
    k  Recall@k     Neu  Kumulativ
 ----  --------  ------  ---------
    5  0.XXXX     XXX    XXX/NNN
   10  0.XXXX     XXX    XXX/NNN
   15  0.XXXX     XXX    XXX/NNN
   20  0.XXXX     XXX    XXX/NNN   <-- Initialwert
   30  0.XXXX     XXX    XXX/NNN

Optimales k (Recall >= 0.90): XX
```

---

## Hinweis zu KQR-IDs

Die KQR-IDs `elm` und `esco_ict` müssen in der Registry vorhanden sein.
Prüfe mit:

```bash
.venv\Scripts\python.exe -c "
from app.services import kqr_service
for kqr in kqr_service.list_kqr():
    print(kqr.id, kqr.status)
"
```

Falls ELM noch nicht registriert ist:

```bash
# API starten
uvicorn app.api.main:app --reload

# ELM registrieren (via API oder Streamlit-UI, Seite 1_KQR_Auswahl.py)
curl -X POST http://localhost:8000/kqr/register \
  -F "name=ELM" \
  -F "source_format=rdf" \
  -F "file=@data/raw/ELM.rdf"
```

---

## In die Thesis übernehmen

→ Werte in `chapters/chapter_5/exp1_recall_k.tex`,
  Tabelle `tab:exp1_recall_k`, eintragen.
→ Falls k* ≠ 20: Wert als `ANN_TOP_K`-Konstante in `app/config.py`
  aktualisieren und in ADR-Tabelle (`chapters/chapter_4/architektur.tex`)
  als Nachtrag dokumentieren.
→ Falls k=20 bestätigt: "strukturell begründeter Initialwert k=20
  empirisch validiert" im Thesis-Text notieren.
