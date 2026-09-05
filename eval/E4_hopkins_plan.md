# Plan: Hopkins-Statistik als Vorvalidierung in E4

**Zweck:** Ergänzung von `eval/E4_hdbscan.py` um einen Hopkins-Test,
der vor dem Parametersweep prüft, ob der gemeinsame Embedding-Raum
überhaupt eine Clustering-Tendenz aufweist (VH₂.₄).

**Kein neues Skript.** Alles kommt in `eval/E4_hdbscan.py`.
**Keine LaTeX-Änderungen.** Die werden separat vorgenommen.

---

## 1. Kontext

Die 1033 Konzeptvektoren (956 ESCO + 45 e-CF + 32 DQR) sind
L2-normalisiert und liegen auf der Einheitshypersphäre im
768-dimensionalen Raum (`paraphrase-multilingual-mpnet-base-v2`).
Geladen werden sie über `load_all_embeddings()` (bereits implementiert).

HDBSCAN läuft mit `metric="euclidean"` auf diesen Vektoren.
Der Hopkins-Test muss dieselbe Distanzmetrik und denselben
Datenraum verwenden.

---

## 2. Algorithmus (exakt implementieren)

Hopkins-Statistik für Daten auf der Einheitshypersphäre:

```
Eingabe: matrix X  (n × d, L2-normalisiert), n_samples s (Standard: max(50, n//10))

1. Ziehe s zufällige Punkte p_i aus X (ohne Zurücklegen, numpy.random.choice)
2. Erzeuge s zufällige Referenzpunkte u_i auf der Hypersphäre:
      u_i = normalize(randn(d))      # normalisierter Gauß-Zufallsvektor
3. Für jedes p_i: w_i = min Euklidische Distanz zu allen Punkten in X
   AUSSER p_i selbst (nearest-neighbor in X, Abstand zu sich selbst ausschließen)
4. Für jedes u_i: x_i = min Euklidische Distanz zu allen Punkten in X
5. H = sum(x_i) / (sum(x_i) + sum(w_i))
   (vereinfachte Form ohne Dimensionsexponent, ausreichend für d >> 1)
```

Implementierung mit `scipy.spatial.KDTree` für die NN-Suche:

```python
from scipy.spatial import KDTree
import numpy as np

def hopkins_statistic(
    matrix: np.ndarray,
    n_samples: int | None = None,
    random_state: int = 42,
) -> float:
    rng = np.random.default_rng(random_state)
    n, d = matrix.shape
    s = n_samples if n_samples is not None else max(50, n // 10)
    s = min(s, n - 1)

    # Schritt 1: Zufällige Stichprobe aus den echten Datenpunkten
    idx = rng.choice(n, size=s, replace=False)
    p = matrix[idx]

    # Schritt 2: Zufällige Punkte auf der Einheitshypersphäre
    raw = rng.standard_normal((s, d))
    u = raw / np.linalg.norm(raw, axis=1, keepdims=True)

    # Schritt 3 + 4: NN-Abstände via KDTree
    tree = KDTree(matrix)
    # k=2 für p-Punkte: Index 0 ist der Punkt selbst, Index 1 ist echter NN
    w_dists, _ = tree.query(p, k=2)
    w = w_dists[:, 1]
    # k=1 für u-Punkte: kein Ausschluss nötig
    x_dists, _ = tree.query(u, k=1)
    x = x_dists[:, 0]

    return float(x.sum() / (x.sum() + w.sum()))
```

---

## 3. Integration in `eval/E4_hdbscan.py`

### 3a. Funktion einfügen

`hopkins_statistic()` als neue Top-Level-Funktion einfügen,
direkt nach den Imports und vor `load_all_embeddings()`.

### 3b. `run_experiment()` erweitern

Nach dem `print(f"Gesamt: ...")`-Block und vor der `for m in`-Schleife
den Hopkins-Test ausführen:

```python
# Hopkins-Vorvalidierung (VH₂.₄)
print("Berechne Hopkins-Statistik ...")
matrix_all = np.stack(list(embeddings.values()))
h = hopkins_statistic(matrix_all)
print(f"Hopkins H = {h:.4f}  ", end="")
if h < 0.55:
    print("→ kein Clustering-Signal (H ≈ 0.5: zufällige Verteilung)")
elif h < 0.75:
    print("→ schwaches Clustering-Signal")
else:
    print("→ Clustering-Tendenz vorhanden (H > 0.75)")
print()
```

Den `h`-Wert in `results` aufnehmen:

```python
# Am Ende von run_experiment(), vor return:
return {"hopkins_h": round(h, 4), "results": results}
```

### 3c. `report()` erweitern

Signatur auf `report(data: dict)` ändern (war `report(results: list[dict])`).
Am Anfang von `report()` den Hopkins-Wert ausgeben:

```python
h = data.get("hopkins_h")
results = data["results"]
if h is not None:
    print(f"\nHopkins H = {h:.4f}", end="  ")
    if h < 0.55:
        print("(kein Clustering-Signal)")
    elif h < 0.75:
        print("(schwaches Signal)")
    else:
        print("(Clustering-Tendenz vorhanden)")
```

### 3d. `main()` anpassen

`run_experiment()` gibt jetzt ein Dict zurück, kein `list`:

```python
# Vorher:
results = run_experiment(args.m_values)
args.output.write_text(
    json.dumps({"results": results}, ...))
report(results)

# Nachher:
data = run_experiment(args.m_values)
args.output.write_text(
    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
report(data)
```

Beim `--report`-Modus ebenfalls anpassen:

```python
# Vorher:
data = json.loads(args.output.read_text(...))
report(data["results"])

# Nachher:
data = json.loads(args.output.read_text(...))
report(data)
```

---

## 4. Ergebnis-JSON-Format nach der Änderung

```json
{
  "hopkins_h": 0.5213,
  "results": [
    {"m": 3, "silhouette": 0.038, "davies_bouldin": 1.4777,
     "n_clusters": 4, "noise_rate": 0.2875, "n_noise": 297, "n_total": 1033},
    ...
  ]
}
```

---

## 5. PROTOKOLL.md aktualisieren

In `eval/PROTOKOLL.md` einen neuen Abschnitt anhängen:

```markdown
## Hopkins-Statistik (VH₂.₄, Ergänzung zu E4)

**Datum:** <aktuelles Datum>
**Methode:** Hopkins-Statistik auf L2-normalisierten Vektoren (768d),
n_samples = max(50, n//10), random_state=42, scipy KDTree (euclidean).
Referenzpunkte uniform auf der Einheitshypersphäre (normalisierter Gauß).

**Ergebnis:** H = <Wert aus Lauf>

**Interpretation:** <je nach Ergebnis — siehe Schwellenwerte in E4_hopkins_plan.md>

**Konsequenz für VH₂.₄:**
- H < 0.55: Bestätigt negativen Befund. Der Embedding-Raum hat keine
  Clustering-Tendenz; flache HDBSCAN-Topologie ist strukturell erklärbar.
- H >= 0.75: Widerspricht der bisherigen Interpretation. Clustering-Tendenz
  ist vorhanden, aber HDBSCAN mit Euclidean-Metrik auf der Hypersphäre
  konnte sie nicht erschließen. VH₂.₄-Interpretation in E4 und Kapitel 6
  muss entsprechend angepasst werden (Limitation betrifft dann Algorithmus/
  Metrik, nicht die Datenstruktur).
```

---

## 6. Test hinzufügen

In `tests/test_clustering.py` (wo die bestehenden HDBSCAN-Tests liegen)
zwei neue Tests ergänzen:

```python
# test_clustering.py — neue Tests am Ende

def test_hopkins_uniform_data():
    """Gleichmäßig verteilte Punkte auf Hypersphäre → H ≈ 0.5."""
    from eval.E4_hdbscan import hopkins_statistic
    rng = np.random.default_rng(0)
    raw = rng.standard_normal((200, 10))
    uniform = raw / np.linalg.norm(raw, axis=1, keepdims=True)
    h = hopkins_statistic(uniform, n_samples=30, random_state=0)
    assert 0.35 < h < 0.65, f"Erwarteter Bereich 0.35–0.65, bekommen: {h:.4f}"


def test_hopkins_clustered_data():
    """Klar geclusterte Punkte → H > 0.7."""
    from eval.E4_hdbscan import hopkins_statistic
    rng = np.random.default_rng(1)
    centers = np.array([[1,0,0,0,0], [0,1,0,0,0], [0,0,1,0,0]], dtype=float)
    points = []
    for c in centers:
        noise = rng.standard_normal((60, 5)) * 0.05
        cluster = c + noise
        cluster /= np.linalg.norm(cluster, axis=1, keepdims=True)
        points.append(cluster)
    clustered = np.vstack(points)
    h = hopkins_statistic(clustered, n_samples=30, random_state=1)
    assert h > 0.7, f"Erwarteter Wert > 0.7, bekommen: {h:.4f}"
```

**Wichtig:** `eval/E4_hdbscan.py` ist kein Package-Modul. Der Import
`from eval.E4_hdbscan import hopkins_statistic` funktioniert nur, wenn
`pytest` aus dem Projektroot (`E:\Fernuni\Master\Masterarbeit\hrqde-harmonizer`)
aufgerufen wird. Falls der Import fehlschlägt, `sys.path`-Handling prüfen
(analog zu `ROOT = Path(__file__).resolve().parents[1]` in E4_hdbscan.py).
Alternative: `hopkins_statistic()` in ein eigenes Modul
`app/pipeline/step2_embedding_prefilter/hopkins.py` auslagern und von dort
importieren — dann ist der Test-Import sauber. Entscheidung dem Implementierer
überlassen; Hauptsache konsistent mit der bestehenden Projektstruktur.

---

## 7. Checkliste

- [ ] `hopkins_statistic()` in `eval/E4_hdbscan.py` implementiert
- [ ] `run_experiment()` gibt `{"hopkins_h": ..., "results": [...]}` zurück
- [ ] `report()` gibt Hopkins-Wert mit Interpretation aus
- [ ] `main()` kompatibel mit neuem Dict-Format (run und --report)
- [ ] `eval/results/E4_hdbscan.json` enthält `hopkins_h`-Feld
- [ ] `eval/PROTOKOLL.md` enthält neuen Hopkins-Abschnitt mit tatsächlichem H-Wert
- [ ] Zwei neue Tests in `test_clustering.py` grün
- [ ] Alle 80 bestehenden Tests weiterhin grün (`pytest tests/ -v`)
- [ ] `python eval/E4_hdbscan.py --report` gibt Hopkins-Wert aus
