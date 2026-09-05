# Aufgabe E1: Recall@k — Implementierungsspec für Claude Code

**Lies zuerst:** `CLAUDE.md` im Projektroot. Dann dieses Dokument.  
**Ziel:** `eval/E1_recall_k.py` implementieren und ESCO-URIs in `eval/G_manual_seed.json` nachschlagen.

---

## Zwei Teilaufgaben

1. **URI-Lookup** (Voraussetzung): `eval/G_manual_seed.json` enthält `PLACEHOLDER`-URIs.  
   Schlage die echten ESCO-URIs nach und aktualisiere die Datei.

2. **Script implementieren**: `eval/E1_recall_k.py` — Recall@k für k ∈ {5, 10, 15, 20, 30}  
   auf G_struct und G_manual getrennt messen und als Tabelle ausgeben.

---

## Teilaufgabe 1: URI-Lookup für G_manual_seed.json

### Was zu tun ist

`eval/G_manual_seed.json` hat 14 Paare. Jedes Paar hat ein `object_label` (ESCO-Skill-Name)
und eine `object_id` die mit `PLACEHOLDER_` beginnt. Ersetze die Placeholder durch echte URIs.

### Lookup-Strategie (Priorität absteigend)

**Schritt A — TTL-Dateien in `data/formalized/`:**  
Lade alle `*.ttl`-Dateien mit rdflib. Suche per `skos:prefLabel` und `skos:altLabel`  
(case-insensitive) nach dem `object_label`. Wenn gefunden → URI übernehmen.

```python
from rdflib import Graph, Namespace, RDF
from rdflib.namespace import SKOS

g = Graph()
for ttl_path in Path("data/formalized").glob("*.ttl"):
    g.parse(ttl_path)

def lookup_uri(label: str) -> str | None:
    label_lower = label.lower()
    for s, p, o in g.triples((None, SKOS.prefLabel, None)):
        if str(o).lower() == label_lower:
            return str(s)
    for s, p, o in g.triples((None, SKOS.altLabel, None)):
        if str(o).lower() == label_lower:
            return str(s)
    return None
```

**Schritt B — Falls nicht in TTL gefunden:**  
Die aktuellen TTL-Dateien enthalten nur Occupations, keine Skills. In diesem Fall:
- `uri_status` im JSON-Pair auf `"NOT_FOUND_IN_CORPUS"` setzen (nicht `"PLACEHOLDER"`)
- `object_id` unverändert lassen (für spätere Nachschlag-Runde nach Skill-Formalisierung)

### Wichtiger Hinweis zu subject_id

Die `subject_id`-Werte (e-CF K3/S4) sind ebenfalls Placeholder. Die e-CF-Formalisierung
(`data/formalized/ecf.ttl`) liegt noch nicht vor. Lass `subject_id` und `subject_label`
unverändert. Setze nur `"subject_uri_status": "PENDING_ECF_FORMALIZATION"` im JSON-Pair
wenn das Feld noch nicht existiert, sonst belassen.

### Ergebnis-Update in G_manual_seed.json

Pro Pair wird `uri_status` auf einen dieser Werte gesetzt:
- `"RESOLVED"` — URI gefunden, in `object_id` eingetragen
- `"NOT_FOUND_IN_CORPUS"` — Label nicht in TTL, Placeholder bleibt stehen
- `"PLACEHOLDER"` — noch nicht versucht (Ausgangszustand)

Schreibe außerdem ein kurzes Lookup-Protokoll als `"uri_lookup_log"` auf oberster JSON-Ebene:

```json
"uri_lookup_log": {
  "timestamp": "2026-07-29T...",
  "ttl_files_searched": ["esco_ict_draft.ttl", "esco_v1_2_ict_ausschnitt.ttl"],
  "resolved": 0,
  "not_found": 14,
  "note": "Aktuelle TTL-Dateien enthalten Occupations, keine Skills. Nach Skill-Formalisierung wiederholen."
}
```

---

## Teilaufgabe 2: eval/E1_recall_k.py

### Was das Script messen soll

Recall@k = Anteil der Gold-Paare, bei denen das Gold-Objekt im Top-k-Ergebnis  
der FAISS-Suche für das Gold-Subjekt enthalten ist.

```
Recall@k = |{(s,o) ∈ G : o ∈ TopK_FAISS(s)}| / |G_evaluierbar|
```

`G_evaluierbar` = nur Paare, bei denen **beide** URIs im eingebetteten Korpus vorhanden sind.  
Paare mit `PLACEHOLDER`- oder `NOT_FOUND_IN_CORPUS`-URIs werden ausgeschlossen und gezählt.

### Goldmengen-Dateien

| Datei | Inhalt | Erwartete Paare |
|---|---|---|
| `eval/G_struct.json` | 8 normative EQF↔DQR-Niveaupaare | Placeholder-URIs bis DQR/EQF formalisiert |
| `eval/G_manual_seed.json` | 14 e-CF A.8 ↔ ESCO-Paare (K3/S4) | Nach URI-Lookup: 0–14 evaluierbar |

### Interface-Kontrakte (vorhandene Klassen verwenden)

```python
# Embedding laden — über config.py, nicht hardcoden
from app.config import settings
# Modell: settings.embedding_model
# k-Initialwert: settings.ann_top_k (wird in E1 überschrieben)

# FAISS-Index aufbauen — Logik aus prefilter.py wiederverwenden
from app.pipeline.step2_embedding_prefilter.prefilter import find_candidate_pairs
# ODER direkter FAISS-Aufruf, wenn find_candidate_pairs nicht passt
```

### Embedding-Bereitstellung

Das Script muss Embeddings für die Gold-Konzepte berechnen können.  
Zwei Fälle sind zu unterscheiden:

**Fall A — Embeddings bereits persistiert** (z.B. als `.npy`-Dateien unter `data/`):  
Lade sie direkt. Bevorzuge diesen Weg.

**Fall B — Keine persistierten Embeddings vorhanden:**  
Berechne Embeddings on-the-fly mit `sentence-transformers` und dem Modell aus `settings.embedding_model`.  
Input-Format für das Modell: `"{pref_label}: {definition}"` (analog zu embed.py in der Pipeline).  
Caching: Speichere berechnete Embeddings unter `eval/cache/embeddings_{model_slug}.pkl` damit  
wiederholte Läufe schnell sind.

**Wenn ein URI weder im persistierten Corpus noch als Label für on-the-fly-Berechnung auflösbar ist:**  
Paar aus der Auswertung ausschließen, in `excluded_pairs` zählen. Nicht crashen.

### Hauptlogik

```python
K_VALUES = [5, 10, 15, 20, 30]

def recall_at_k(
    gold_pairs: list[tuple[str, str]],   # (subject_uri, object_uri)
    embeddings: dict[str, np.ndarray],   # uri -> vektor
    k: int,
) -> tuple[float, int, int]:
    """
    Gibt zurück: (recall, hits, total_evaluable)
    """
    ...
```

### Ausgabe auf stdout

Zwei Tabellen — eine für G_struct, eine für G_manual. Format passend zu
`chapters/chapter_5/exp1_recall_k.tex` (Spalten: k, Recall@k, neu gefundene Paare, kumulativ):

```
=== G_struct: EQF<->DQR Niveaupaare (n=8, evaluierbar=X, ausgeschlossen=Y) ===

 k   | Recall@k | Neu  | Kumulativ
-----|----------|------|----------
  5  |   0.000  |    0 |         0
 10  |   0.000  |    0 |         0
 15  |   0.000  |    0 |         0
 20  |   0.000  |    0 |         0
 30  |   0.000  |    0 |         0

Ausgeschlossene Paare (URI nicht im Korpus): Y/8
Grund: DQR/EQF noch nicht formalisiert (data/formalized/ enthält nur ESCO).

=== G_manual: e-CF A.8 <-> ESCO (n=14, evaluierbar=X, ausgeschlossen=Y) ===
Scope: K3 'Green ICT and Environmental Standards' + S4 'Analyze Social...' (Zare et al. 2025)

 k   | Recall@k | Neu  | Kumulativ
-----|----------|------|----------
  5  |   ...
...

Empfehlung k: [kleinster k mit Recall@k >= 0.90, oder "Datenbasis zu klein für Aussage"]
```

Wenn `evaluierbar = 0` für eine Goldmenge: trotzdem Tabelle ausgeben, alle Zellen mit `n/a`,
und einen klaren Hinweistext drucken warum (fehlende URIs / Formalisierung).

### Keine Änderungen an LaTeX

Das Script gibt nur stdout aus. Tabellenwerte werden **manuell** in  
`chapters/chapter_5/exp1_recall_k.tex` eingetragen. Kein Schreiben in LaTeX-Dateien.

---

## Projektstruktur (relevanter Ausschnitt)

```
hrqde-harmonizer/
├── app/
│   ├── config.py                          # settings.embedding_model, settings.ann_top_k
│   ├── models/schemas.py                  # CandidatePair, Mapping, MatchType, ...
│   └── pipeline/
│       └── step2_embedding_prefilter/
│           ├── embed.py                   # Embedding-Berechnung (Modell-Init, encode())
│           └── prefilter.py               # find_candidate_pairs(), FAISS-Logik
├── data/
│   └── formalized/                        # *.ttl — aktuell nur ESCO-Occupations
├── eval/
│   ├── G_struct.json                      # 8 EQF<->DQR Paare (Placeholder-URIs)
│   ├── G_manual_seed.json                 # 14 e-CF A.8 <-> ESCO Paare
│   ├── cache/                             # Embedding-Cache (anlegen falls nicht vorhanden)
│   └── E1_recall_k.py                     # DIESES SCRIPT (zu erstellen)
└── CLAUDE.md                              # Projektkontext, Confidence-Kalibrierung, Goldmengen
```

---

## Randbedingungen

- **Kein Neo4j erforderlich.** FAISS-only, analog zu den bestehenden Unit-Tests.
- **Keine hartcodierten Pfade.** Alle Pfade relativ zum Script-Verzeichnis oder über `config.py`.
- **Kein Absturz bei leerem Korpus.** Wenn `evaluierbar = 0` → Ausgabe mit `n/a`, Erklärung, Exit 0.
- **Kein automatisches Schreiben in LaTeX-Dateien.**
- **Python 3.11+, Typannotationen.** Pydantic für Datenstrukturen an Modulgrenzen.
- **Tests:** Mindestens ein Unit-Test in `tests/` der das Script mit Mock-Embeddings aufruft  
  (analog zu `test_prefilter.py` — Mock-Goldmenge mit 2 bekannten Paaren, k=1 → Recall=1.0).

---

## Bekannte Situation beim ersten Lauf

Beim ersten Ausführen werden **beide Goldmengen 0 evaluierbare Paare** haben:
- G_struct: DQR/EQF noch nicht formalisiert → alle 8 Paare ausgeschlossen
- G_manual: ESCO-Skills nicht in aktuellen TTL-Dateien → alle 14 Paare ausgeschlossen  
  (aktuelle TTL-Dateien enthalten Occupations, keine Skills)

Das ist **kein Bug**, sondern der korrekte Stand. Das Script soll das klar kommunizieren.  
E1 wird erst vollständig auswertbar, sobald ESCO-Skills und EQF/DQR formalisiert vorliegen.
