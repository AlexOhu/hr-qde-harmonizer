# E5 – Kompetenzfragen-Evaluation (CQ₁–CQ₄)

**Ziel:** Überprüfe, ob die materialisierte Basisontologie alle vier
Kompetenzfragen durch formale SPARQL-Abfragen beantworten kann.

**Auflöst:** CQ₁–CQ₄ (qualitative Ontologie-Validierung nach
Gruninger & Fox 1995)

---

## Voraussetzung: Ontologie materialisieren

Die OWL-Ontologie im Turtle-Format muss erzeugt sein.
Falls noch nicht vorhanden:

```bash
# API starten
uvicorn app.api.main:app --reload

# Export via UI (Seite 5_Export.py) oder direkt:
curl -X POST http://localhost:8000/export/ontology \
  -H "Content-Type: application/json" \
  -d '{"format": "turtle"}' \
  -o data/ontology/harmonised_ontology.ttl
```

Prüfen, ob die Datei Inhalt hat:
```bash
.venv\Scripts\python.exe -c "
from rdflib import Graph
g = Graph()
g.parse('data/ontology/harmonised_ontology.ttl', format='turtle')
print(f'Tripel: {len(g)}')
"
```

Erwartung: > 1000 Tripel.

---

## Durchführung

```bash
.venv\Scripts\python.exe eval\E5_cq_evaluation.py \
  --ontology data/ontology/harmonised_ontology.ttl \
  --output eval/results/E5_cq_evaluation.json
```

Das Skript führt alle vier SPARQL-Abfragen aus
(exakt wie in `chapters/chapter_5/cq_evaluation.tex` definiert)
und protokolliert Treffer-Anzahl und Beispiel-Ergebnisse.

---

## Auswertung

```bash
.venv\Scripts\python.exe eval\E5_cq_evaluation.py --report \
  --input eval/results/E5_cq_evaluation.json
```

Ausgabe-Format:

```
CQ1 (exactMatch): N Treffer — Erfüllt: JA/NEIN
  Beispiel: "Application Development" ↔ "ICT system programming"

CQ2 (narrowMatch von e-CF): N Treffer — Erfüllt: JA/NEIN
  Beispiel: ecf:BUILD → esco:skill/...

CQ3 (disjunkte Konzepte): N Treffer — Erfüllt: JA/NEIN
  Beispiel: dqr:Sozialkompetenz (Strategie: standalone_class)

CQ4 (transitive Hierarchie): N Vorfahren für Cluster-42 — Erfüllt: JA/NEIN
  Pfad: Cluster-42 → Cluster-12 → Cluster-3
```

---

## Erfüllungskriterien

| CQ | Erfüllt wenn |
|---|---|
| CQ₁ | ≥ 1 exactMatch-Paar abgerufen |
| CQ₂ | ≥ 1 narrowMatch von e-CF nach ESCO |
| CQ₃ | Anzahl disjunkter Konzepte ≡ Einträge in Strategie-Doku |
| CQ₄ | ≥ 1 Vorfahren-Cluster für mind. ein Blatt-Konzept |

---

## In die Thesis übernehmen

→ Status und Treffer-Zahlen in `chapters/chapter_5/cq_evaluation.tex`,
  Tabelle `tab:exp5_cq_uebersicht`, eintragen.
→ 2–3 konkrete Beispiel-Paare aus CQ₁ und CQ₃ im Fließtext nennen.
→ Falls eine CQ nicht erfüllt: Begründung als Limitation in
  `chapters/kapitel_6.tex` aufnehmen.
