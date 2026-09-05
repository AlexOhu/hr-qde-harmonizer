# E4 – HDBSCAN-Parametersweep (VH₂.₃)

**Ziel:** Bestimme `min_cluster_size m*`, das im gemeinsamen
Embedding-Raum kompakte, gut getrennte Cluster erzeugt,
bei einer Noise-Rate η < 0.20.

**Auflöst:** VH₂.₃ (optimale HDBSCAN-Parameter)

---

## Voraussetzung

Die Embeddings für alle registrierten KQR müssen gecacht sein.
Prüfen:

```bash
.venv\Scripts\python.exe -c "
from app.services.kqr_service import KQRService
svc = KQRService()
for kqr in svc.list_kqrs():
    print(kqr.id, kqr.status, kqr.concept_count)
"
```

Alle KQR sollten Status `bereit` haben. Falls nicht:

```bash
# API starten und Embeddings über UI oder API-Endpunkt berechnen
uvicorn app.api.main:app --reload
# POST /kqr/{kqr_id}/embed
```

---

## Durchführung

```bash
.venv\Scripts\python.exe eval\E4_hdbscan.py \
  --m-values 3 5 8 10 15 \
  --output eval/results/E4_hdbscan.json
```

Das Skript:
1. Lädt alle gecachten Embedding-Vektoren via `kqr_service`
2. Normiert auf L2 (konsistent mit Prototyp 2)
3. Führt HDBSCAN für jeden m-Wert aus (Metrik: euclidean,
   gen_min_span_tree=True — identisch zu Prototyp 5)
4. Berechnet je Lauf: Silhouette-Koeffizient S,
   Davies-Bouldin-Index DB, Cluster-Anzahl, Noise-Rate η

---

## Auswertung

```bash
.venv\Scripts\python.exe eval\E4_hdbscan.py --report \
  --input eval/results/E4_hdbscan.json
```

Ausgabe-Format:

```
m=3:  S=X.XXX  DB=X.XXX  Cluster=NNN  η=X.XX%
m=5:  S=X.XXX  DB=X.XXX  Cluster=NNN  η=X.XX%  <-- Initialwert
m=8:  S=X.XXX  DB=X.XXX  Cluster=NNN  η=X.XX%
m=10: S=X.XXX  DB=X.XXX  Cluster=NNN  η=X.XX%
m=15: S=X.XXX  DB=X.XXX  Cluster=NNN  η=X.XX%

Optimum (S↑, DB↓, η<0.20): m* = X
```

---

## Entscheidungslogik

```
wenn η(m) ≥ 0.20: m aus Kandidatenmenge ausschließen
m* = argmax S(m) unter verbleibenden Kandidaten
Tiebreaker: niedrigstes DB(m)
```

---

## In die Thesis übernehmen

→ Werte in `chapters/chapter_5/exp4_hdbscan.tex`,
  Tabelle `tab:exp4_hdbscan`, eintragen.
→ m* als `MIN_CLUSTER_SIZE`-Konstante in `app/config.py` setzen
  (oder direkt im `cluster_concepts()`-Defaultparameter).
→ Falls m* = 5: Initialwahl bestätigt, kein Code-Update nötig.
