# Demo-Skript — HR-QDE Harmonizer

Leitfaden für die Live-Demo des Prototyps gegenüber dem Betreuer. Zeigt den
Systementwicklungsstand (Kapitel 4) entlang der 5 Funktionsgruppen aus dem
Wireframe (Abb. 3.7). Geplante Dauer: ca. 10–15 Minuten plus Fragen.

## Vorbereitung (ca. 15 Min. vorher)

1. Terminal 1: `uvicorn app.api.main:app --reload`
2. Terminal 2: `streamlit run ui/app.py`
3. Terminal 3: `python scripts/00_demo_setup.py`
   Prüft die API (Retry auf `GET /docs`) und registriert die drei
   Demo-KQR, falls nicht vorhanden. Muss mit `✓ Setup komplett, ready
   for demo` enden — falls nicht, siehe [Fallback-Plan](#fallback-plan-falls-die-api-nicht-lädt).
4. Browser auf `http://localhost:8501` (Streamlit) öffnen, Seite 1 als
   Startpunkt.
5. **Nicht** zwischendurch `uvicorn` neu starten, sobald auf Seite 2
   klassifiziert wurde — Mappings/Jobs liegen nur In-Memory
   (`app/services/mapping_service.py`), ein Neustart löscht sie. Die
   KQR-Registry (`data/kqr_registry.json`) übersteht einen Neustart, die
   Klassifikationsergebnisse nicht.

Erwarteter Zustand nach Schritt 3 (aktuell verifiziert):

| KQR | Status | Konzepte | Hub |
|---|---|---|---|
| `esco_v1_2_ict_ausschnitt` | 🟢 bereit | 956 | ja |
| `satellite` | 🟢 bereit | 4 | nein |
| `dqr` | 🔴 roh (188 Validierungsfehler) | — | nein |

## Ablauf (Seite 1 → 5)

### Seite 1 — KQR-Auswahl

**Was der Betreuer sieht:** drei Karten (ESCO-Hub, satellite, DQR) mit
Status-Badge (🔴/🟡/🟢) und Konzeptanzahl. Der "Weiter"-Button ist aktiv,
da mindestens ein KQR `bereit` ist.

**Zu tun:** kurz auf `dqr` zeigen (Status `roh`) — Beleg für die
Action-Constraint-Logik (roh → formalisiert → bereit, Abschnitt 3.8.3):
das System lässt DQR bewusst nicht in die Klassifikation, weil Pflichtfelder
(`skos:prefLabel@en` etc.) fehlen.

**Zu erwähnen:**
- **VH1.3**: Vollautomatisierte Formalisierung ist explizit *kein*
  Forschungsziel. `dqr` demonstriert das live — die Validierung fängt ein
  unvollständiges Turtle-Artefakt ab, statt es stillschweigend
  durchzulassen. Bei PDF-Quellen (z. B. e-CF) ist das Ergebnis laut
  Konzeption ohnehin nur ein LLM-Entwurf, der manuell geprüft werden muss.
- Optional: einen neuen KQR live einpflegen (z. B.
  `tests/fixtures/hub_kqr.ttl` hochladen, `is_hub` je nach gewünschtem
  Demo-Pfad) — zeigt FA1 als aktiven statt nur vorbereiteten Schritt.

### Seite 2 — Klassifikation

**Was der Betreuer sieht:** zwei Statuszeilen (Neo4j erreichbar?,
LLM-Endpunkt konfiguriert?) *vor* dem Start — Transparency-Prinzip, nicht
erst ein Fehler nach dem Klick. Danach Auswahl KQR A/B und Fortschrittsbalken
mit Prozentzahl und Paaranzahl.

**Zu tun:** KQR A = `satellite`, KQR B = `esco_v1_2_ict_ausschnitt` wählen
(satellite als kleineres KQR zuerst hält die Paarzahl klein: 4 Konzepte ×
`ANN_TOP_K` Kandidaten). Klassifikation starten, Fortschrittsbalken
laufen lassen.

**Zu erwähnen:**
- Falls Neo4j nicht erreichbar ist: bewusst kein Show-Stopper — Warnung
  statt Fehler, da Neo4j nur optionale Materialisierung ist (siehe
  [Fallback-Plan](#fallback-plan-falls-die-api-nicht-lädt)).
- Vorfilter kombiniert einen regelbasierten Struktur-Shortcut (bekannte
  Cross-Referenz-Prädikate wie `esco:isPartOf` → sofort
  `mapping_confidence=1.0`, ohne LLM) mit FAISS-ANN-Suche für die übrigen
  Kandidatenpaare — Schritt 3 sieht nur, was der Shortcut nicht schon gelöst
  hat.
- Jedes verbleibende Paar durchläuft 3 unabhängige LLM-Klassifikationsläufe
  (Mehrheitsentscheid) — Nicht-Determinismus ist laut CLAUDE.md/VH1.6 eine
  akzeptierte Randbedingung, keine zu behebende Fehlerquelle.

### Seite 3 — Ergebnisliste

**Was der Betreuer sieht:** Tabelle mit subject/predicate/object,
Konfidenz, `match_type`, Quelle. Filter: "Nur manuelle Entscheidung
erforderlich" und Konfidenz-Slider.

**Zu tun:** Slider von 0.0 auf höhere Werte ziehen und live beobachten, wie
sich die Tabelle leert — das *ist* die Konfidenz-Verteilung, nicht als
Diagramm, sondern interaktiv über den Filter.

**Zu erwähnen:**
- **Confidence-Verteilung**: `mapping_confidence` ist der Anteil
  übereinstimmender Läufe unter den 3 LLM-Durchläufen (0.33 / 0.67 / 1.0),
  Struktur-Shortcut-Treffer liegen fix bei 1.0 (`match_type=struct`, kein
  LLM beteiligt). Zeigt konkret, wo das System sich sicher ist und wo
  nicht — Grundlage für den Schwellenwert `MAPPING_CONFIDENCE_THRESHOLD`
  (aktuell 0.40, VH1.7, vorläufig).
- Mixed-Initiative-Prinzip: eindeutige Fälle werden automatisch
  übernommen, niedrige Konfidenz bzw. `UNRESOLVED` werden gezielt zur
  manuellen Entscheidung vorgelegt — nicht die volle Liste unsortiert.
- Kurz eine manuelle Entscheidung vorführen: Relation wählen, Begründung
  eintragen (Pflichtfeld laut FA4 — ohne Begründung lässt sich nicht
  speichern, das ist Absicht, nicht ein fehlendes Feld).

### Seite 4 — SSSOM-Vorschau

**Was der Betreuer sieht:** Feldliste plus Tabellenvorschau der ersten 5
Mappings im finalen Exportformat.

**Zu erwähnen:**
- **SSSOM-Format**: die 11 Felder (`subject_id`, `subject_label`,
  `object_id`, `object_label`, `predicate_id`, `mapping_confidence`,
  `mapping_tool`, `match_type`, `comment`, `mapping_source`, `author_id`)
  entsprechen Tabelle 3.9 der Arbeit — bewusst ein offener Standard
  (Simple Standard for Sharing Ontology Mappings), kein
  Eigenformat, damit Ergebnisse in andere Ontologie-Tools weiterverwendbar
  sind.
- Diese Seite existiert eigenständig als Transparency-Maßnahme: der
  Nutzer sieht die Exportstruktur, *bevor* er exportiert, nicht erst in der
  heruntergeladenen Datei.

### Seite 5 — Export

**Was der Betreuer sieht:** Zusammenfassung offener Einträge
(UNRESOLVED / RELATED / unterhalb der Konfidenz-Schwelle) *oberhalb* der
Export-Buttons, danach drei Export-Optionen.

**Zu tun:** "SSSOM-TSV exportieren" klicken, Download-Button zeigen
(optional: Datei kurz in einem Editor öffnen).

**Zu erwähnen:**
- Gatekeeping-Prinzip (Accountability): die Warnung zu offenen Einträgen
  steht bewusst *vor* dem Export, nicht als Fehlermeldung danach —
  offene Fälle sind Kandidaten für die manuelle Integrationsstrategie
  disjunkter Konzepte (FZ3.2).
- Ehrlich benennen, was fehlt: OWL-/Turtle-Export und Prüfbericht liefern
  aktuell `501` — an die noch nicht implementierte HDBSCAN-Kernstruktur
  (FZ2.2) gekoppelt, siehe README "Implementierungsstand im Detail". Das
  ist eine bekannte, dokumentierte Lücke, kein Bug.

## Fallback-Plan falls die API nicht lädt

**Vorab-Check (ca. 15 Min. vor der Demo):** `python scripts/00_demo_setup.py`
laufen lassen. Das Skript wartet selbst mit Retry auf die API — bricht es
mit "API nicht erreichbar" ab, folgende Stufen durchgehen:

1. **Port belegt / uvicorn startet nicht:**
   `netstat -ano | findstr :8000` prüfen, ggf. blockierenden Prozess
   beenden oder mit `--port 8001` ausweichen (dann auch
   `API_BASE_URL`/`--base-url` in UI bzw. Setup-Skript anpassen).
2. **`.env` fehlt oder ist unvollständig:** `.env.example` nach `.env`
   kopieren, mindestens einen LLM-Provider-Key (`LLM_PROVIDERS`,
   z. B. `MISTRAL_API_KEY`) setzen. Fehlender Key blockiert *nicht* das
   Einpflegen/Anzeigen von KQR — nur Seite 2 (Klassifikation starten)
   ist betroffen, das zeigt die Vorbedingungs-Statuszeile bereits vorab.
3. **Neo4j nicht erreichbar:** kein Blocker — bewusste Architekturentscheidung
   (README "Bewusste Abweichungen"). Bei Bedarf kurz erwähnen statt zu
   reparieren: `docker compose up -d` nur, wenn genug Zeit vorhanden ist.
4. **LLM-Provider antwortet nicht / Rate Limit während der Demo:**
   Live-Klassifikation auf Seite 2 überspringen. Stattdessen direkt zu
   Seite 3/4 wechseln und die bereits vorhandene Export-Datei
   `data/sssom/export_20260726T191058Z.tsv` (echter, früherer
   Klassifikationslauf: satellite × ESCO-ICT-Ausschnitt, 59 Mappings) im
   Editor zeigen — demonstriert das Format ohne neuen LLM-Call.
5. **Streamlit-UI lädt nicht, API aber schon:** Fallback auf Swagger UI
   unter `http://localhost:8000/docs` — alle Endpunkte sind dort per
   "Try it out" direkt bedienbar, da die UI nur ein dünner Client über der
   API ist (`ui/api_client.py`).
6. **Worst Case — nichts läuft:** kein Live-System nötig. Anhand von
   README-Architekturdiagramm, `data/kqr_registry.json` (zeigt reale
   Konzeptzahlen/Status aus früheren Läufen) und der bereits exportierten
   TSV-Datei den Ablauf narrativ durchgehen. Zeitstempel im Dateinamen
   (`export_20260726T191058Z.tsv`) belegt, dass es sich um einen
   tatsächlich durchgeführten Lauf handelt, nicht um Mock-Daten.

**Wichtig:** Ist einmal auf Seite 2 klassifiziert worden, `uvicorn`
*nicht* mehr neu starten — sonst sind die In-Memory-Mappings weg und
Seite 3–5 zeigen wieder leer (siehe Vorbereitung, Punkt 5).
