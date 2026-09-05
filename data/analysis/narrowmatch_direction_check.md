# Richtungsprüfung `skos:narrowMatch` – Freitext vs. formales Prädikat

## Kernergebnis (max. 5 Sätze)

Die manuelle Stichprobe ist reproduzierbar: Bei `skos:narrowMatch`-Records
bezeichnet der LLM-Freitext sehr häufig das ESCO-**Objekt** (nicht das
KQR-Subjekt) als das speziellere Konzept – gemessen gegen die Lesart „Subjekt
ist enger" trifft das auf **44,7 % von 3.629 Records** zu (belastbare
Untergrenze 34,6 %, hochkonfident erkannt). Die anschließende Code-Prüfung zeigt
aber, dass diese Lesart selbst falsch ist: `RelationType.to_skos_predicate()`
und `tab:predicate_mapping` (Kap. 3) bilden `B_SUBSUMES_A` auf `skos:narrowMatch`
ab und meinen damit „Subjekt enger", während W3C SKOS **und Kapitel 2 der
Arbeit** (`sssom.tex`) `skos:narrowMatch` als „Objekt enger" definieren – gegen
diese korrekte Lesart ist der Freitext in der Mehrheit **konsistent**. Der reale
Defekt ist also nicht „Begründungen widersprechen den Mappings", sondern eine
**invertierte Prädikat-Richtung** (für jeden standardkonformen SKOS-Konsumenten,
und gegenüber dem strukturell abgeleiteten Shortcut-Pfad im selben Code) plus
zwei einander widersprechende Definitionen in der Arbeit. Zusätzlich ist das
Richtungssignal des LLM funktionslos: In ~8.360 Einzelaufrufen wurde nur
`B_SUBSUMES_A` und `RELATED` erzeugt, nie `A_SUBSUMES_B` oder `EQUIVALENT`, und
die Begründungstexte argumentieren durchgängig die Gegenrichtung zum Token.
Einstufung: **behebbarer Implementierungs- und Spezifikationsfehler**, kein
inhärentes methodisches Limit; die Prädikat-Inversion und die
Prompt-Unterspezifikation sind im Code behoben (Stand 2026-08-29), offen bleibt
die Re-Klassifikation des Bestands und die Angleichung von `tab:predicate_mapping`
in Kapitel 3 (Details und Status in Abschnitt 7).

---

## 1. Datengrundlage

Quelle: `data/projects/default/mappings.json`, 4.820 Mapping-Records;
`data/projects/default/classification_results.json`, 4.180 Klassifikationsergebnisse.

### 1.1 Verteilung nach `predicate_id` (`mappings.json`)

| `predicate_id` | Records | Anteil |
|---|---:|---:|
| `skos:narrowMatch` | 3.629 | 75,3 % |
| `skos:relatedMatch` | 1.191 | 24,7 % |
| `skos:broadMatch` | 0 | – |
| `skos:exactMatch` / `skos:closeMatch` | 0 | – |

Es existiert **kein einziger `broadMatch`-Record**. Der in der Aufgabenstellung
vorgesehene Vergleich „narrowMatch erwartet subject_enger / broadMatch erwartet
object_enger" reduziert sich damit auf die 3.629 `narrowMatch`-Records.

### 1.2 Verteilung nach `subject_kqr_id`

| `subject_kqr_id` | gesamt | davon `narrowMatch` | davon `relatedMatch` |
|---|---:|---:|---:|
| `dqr_2` | 3.920 | 2.897 | 1.023 |
| `ecf` | 900 | 732 | 168 |

`object_kqr_id` ist bei den `narrowMatch`-Records durchgängig
`esco_v1_2_ict_ausschnitt` (bei 104 `relatedMatch`-Records ist `object_kqr_id`
`null`). Andere Subjekt-KQR treten im Mapping-Bestand nicht als Subjekt auf.

### 1.3 Formale Felder der `narrowMatch`-Records – vollständig uniform

Alle 3.629 `narrowMatch`-Records haben **identische** Werte in:

- `source_relation` = `B_SUBSUMES_A`
- `review_status` = `conjunct`
- `mapping_justification` = `semapv:LLMBasedMatching`
- `mapping_confidence` = `1.0`

### 1.4 Je-Lauf ausgegebene Relations-Tokens (`classification_results.json`)

Über alle Läufe aller 4.180 Ergebnisse gepoolt (~8.360 Einzelaufrufe):

| Token | Häufigkeit |
|---|---:|
| `B_SUBSUMES_A` | 6.455 |
| `RELATED` | 1.905 |
| `A_SUBSUMES_B` | **0** |
| `EQUIVALENT` | **0** |

Das Modell hat in keinem einzigen Lauf `A_SUBSUMES_B` oder `EQUIVALENT`
produziert. `final_relation`-Verteilung: `B_SUBSUMES_A` 3.072, `RELATED` 797,
`UNRESOLVED` 311. Jedes Paar mit hierarchischem Bezug erhält denselben Token –
das Richtungssignal ist konstant (vgl. Abschnitt 7, Befund 1).

---

## 2. Methode der Textauswertung

Für jeden `narrowMatch`-Record wurde das Feld `justification` (deutscher, teils
englischer Freitext) mit einem regelbasierten Textmuster-Klassifikator
ausgewertet:

1. **Konzept-Anker lokalisieren** (wörtliche Labels, `(A)`/`(B)`, KQR-Kürzel;
   Sonderbehandlung bei lexisch überlappenden Labels).
2. **Richtungsformulierungen gewichtet bewerten** („X ist spezifischer …",
   „X ist ein übergeordnetes Konzept", „X fällt unter Y", „X umfasst Y",
   „X geht über Y hinaus", „was … Y einschließt", englische Entsprechungen …).
3. **Netto-Richtung:** `subject_enger`, `object_enger` oder `unklar`.
4. **Klassifikation gegen die (Kap.-3-/Code-)Erwartung** `narrowMatch` ⇒
   „subject_enger":
   - Freitext = `subject_enger` → **konsistent**
   - Freitext = `object_enger` → **widersprüchlich**
   - `unklar` → **unklar**

> **Wichtig für die Deutung:** „widersprüchlich" heißt hier ausschließlich
> „der Freitext argumentiert gegen die Lesart *Subjekt ist enger*". Abschnitt 7
> zeigt, dass diese Lesart der Fehler ist – gegen die W3C-/Kapitel-2-Lesart
> (*Objekt ist enger*) kehrt sich die Bewertung praktisch um.

### Grenzen der Methode

- **Keine Semantikprüfung**, nur Formulierungsmuster in LLM-Freitext.
- **Niederkonfidenter Teil unzuverlässig.** Manuelle Gegenprüfung von ~130
  Records: hochkonfident „widersprüchlich" (Stichprobe 40) → 0 klare Fehler,
  ~5 in sich widersprüchliche LLM-Texte; hochkonfident „konsistent"
  (Stichprobe 10) → 0 Fehler. **Niederkonfident „widersprüchlich" (366 Records):
  ~40–45 % bei Nachprüfung eigentlich „konsistent" oder mehrdeutig.**
  Niederkonfident „konsistent" (Stichprobe 14): ~3 eigentlich „widersprüchlich".
- **`unklar` (588 Records):** 447 „keine Richtungsformulierung erkannt"
  (hedgende Formulierungen wie „X erfordert Y als Voraussetzung"), 138
  „gegenläufige Formulierungen, Netto ≈ 0" (der LLM benennt Richtung und
  Gegenrichtung im selben Satz), 3 „kein Anker".
- **Netto:** Nennwert 44,7 % ist die Obergrenze, hochkonfidente Untergrenze
  34,6 %, realistische Punktschätzung ≈ 38–41 % – jeweils **bezogen auf die
  invertierte Lesart**.

---

## 3. Ergebnisse der Textauswertung (gegen die Lesart „Subjekt enger")

### 3.1 Gesamt (alle 3.629 `narrowMatch`-Records)

| Kategorie | Records | Anteil |
|---|---:|---:|
| konsistent | 1.418 | 39,1 % |
| widersprüchlich | 1.623 | 44,7 % |
| unklar | 588 | 16,2 % |

Nur hochkonfidente Urteile (Score-Differenz ≥ 1,0; n = 1.747):

| Kategorie | Records | Anteil an allen 3.629 | Anteil an den hochkonf. Urteilen |
|---|---:|---:|---:|
| konsistent | 490 | 13,5 % | 28,0 % |
| widersprüchlich | 1.257 | 34,6 % | 72,0 % |

### 3.2 Aufgeschlüsselt nach `subject_kqr_id`

| KQR | n | konsistent | widersprüchlich | unklar | widersprüchlich (hochkonf.) |
|---|---:|---:|---:|---:|---:|
| `dqr_2` | 2.897 | 1.150 (39,7 %) | 1.210 (41,8 %) | 537 (18,5 %) | 889 (30,7 %) |
| `ecf` | 732 | 268 (36,6 %) | 413 (56,4 %) | 51 (7,0 %) | 368 (50,3 %) |

Der Effekt tritt in **beiden** Subjekt-KQR auf, bei `ecf` deutlich stärker
(e-CF-Bereiche wie `BUILD`/`PLAN`/`MANAGE`/„Testing" sind besonders breit
formuliert, die zugeordneten ESCO-Skills konkret). `dqr_2` hat eine höhere
`unklar`-Quote, weil DQR-Begründungen häufiger die hedgende Form „X erfordert Y
als Voraussetzung" wählen. Es ist **kein KQR-Artefakt**, sondern ein
systemweiter Effekt mit KQR-Gradient – konsistent mit einer gemeinsamen Ursache
in der Ableitungslogik (Abschnitt 7).

---

## 4. Beispiele zur eigenen Gegenprüfung

### 4.1 Fünfzehn Records aus „widersprüchlich" (hochkonfident, 10× `dqr_2`, 5× `ecf`)

Alle mit `predicate_id = skos:narrowMatch`. Der Freitext bezeichnet jeweils das
**Objekt** als das engere/speziellere Konzept.

| # | KQR | subject_label | object_label | justification (Wortlaut) |
|---|---|---|---|---|
| 1 | dqr_2 | Very broad methodological spectrum | monitor developments in field of expertise | „monitor developments in field of expertise" ist eine spezifische Ausprägung der Fähigkeit, über ein breites Methodenspektrum zu verfügen, da das Verfolgen von Entwicklungen eine Methode innerhalb dieses Spektrums darstellt. |
| 2 | dqr_2 | Specialized conceptual skills | develop strategy to solve problems | „develop strategy to solve problems" (B) ist eine spezifischere Ausprägung von „Specialized conceptual skills" (A), da strategische Planung und Problemlösung eine Teilmenge konzeptioneller Fertigkeiten darstellen. |
| 3 | dqr_2 | Scientific foundations | data scientist | „Scientific foundations" (dqr_2) ist ein allgemeineres Konzept, das grundlegendes Wissen und wissenschaftliche Prinzipien umfasst, während „data scientist" (esco_v1_2_ict_ausschnitt) spezifische Fähigkeiten und Tätigkeiten in der Datenanalyse und Modellierung beschreibt, die auf diesen Grundlagen aufbauen. |
| 4 | dqr_2 | Comprehensive consideration of alternatives and interactions | conduct impact evaluation of ICT processes on business | „Comprehensive consideration of alternatives and interactions" (dqr_2) ist ein allgemeineres Konzept, das die Berücksichtigung von Handlungsalternativen und Wechselwirkungen umfasst, während „conduct impact evaluation of ICT processes on business" (esco_v1_2_ict_ausschnitt) eine spezifische Anwendung dieses Prinzips im ICT-Bereich darstellt. |
| 5 | dqr_2 | Social Competence – Level 4 | communicate analytical insights | „communicate analytical insights" (B) ist eine spezifischere Teilmenge von „Social Competence – Level 4" (A), da analytische Kommunikation eine Form der umfassenden Kommunikation und Teamunterstützung darstellt, aber nicht alle Aspekte von A (z.B. Gestalten von Gruppenprozessen) abdeckt. |
| 6 | dqr_2 | Integrated specialist knowledge | monitor developments in field of expertise | „monitor developments in field of expertise" (B) ist eine spezifischere Fähigkeit, die „Integrated specialist knowledge" (A) voraussetzt, aber über dessen reine Anwendung hinausgeht. |
| 7 | dqr_2 | Sustainable design of learning and work processes | follow work procedures | „Following work procedures" (B) ist eine spezifische, systematische Handlung, die als Teilmenge der nachhaltigen Gestaltung von Lern- und Arbeitsprozessen (A) verstanden werden kann. |
| 8 | dqr_2 | Apply suitable means | apply risk management processes | „apply risk management processes" ist eine spezifische Ausprägung von „Apply suitable means", da Risikomanagementprozesse eine konkrete Methode zur Zielerreichung darstellen. |
| 9 | dqr_2 | Evaluate innovative processes | identify processes for re-engineering | „identify processes for re-engineering" (B) ist eine spezifischere Tätigkeit, die das Bewerten innovativer Prozesse (A) als Teilaspekt einschließt, da Re-Engineering eine gezielte Identifikation und Bewertung von Prozessen voraussetzt. |
| 10 | dqr_2 | Very broad methodological spectrum | analyse big data | „analyse big data" ist eine spezifische Methode innerhalb des breiten methodischen Spektrums von „Very broad methodological spectrum". |
| 11 | ecf | ICT Quality Management | administer ICT system | „administer ICT system" ist eine spezifischere Tätigkeit innerhalb des breiteren Rahmens von „ICT Quality Management", das strategische Planung und kontinuierliche Verbesserung umfasst. |
| 12 | ecf | Testing | manage system testing | „manage system testing" ist eine spezifischere Ausprägung von „Testing", da es konkrete Testarten (z.B. Installationstests) und organisatorische Aspekte (Durchführung, Nachverfolgung) umfasst, die im übergeordneten Konzept nicht explizit genannt werden. |
| 13 | ecf | Digital Marketing | mobile marketing | „Mobile Marketing" ist ein spezifischer Anwendungsfall von „Digital Marketing", der sich auf mobile Geräte als Kommunikationskanal konzentriert. |
| 14 | ecf | PLAN | utilise decision support system | „utilise decision support system" ist eine spezifische Anwendung von „PLAN", da Entscheidungsunterstützungssysteme ein Werkzeug für strategische Planung und IT-Dienstleistungen darstellen. |
| 15 | ecf | MANAGE | ICT quality assurance manager | „MANAGE" ist ein übergeordneter Kompetenzbereich, der „ICT quality assurance manager" als spezifische Rolle mit Fokus auf Qualitätsmanagement umfasst. |

Der **in der Aufgabenstellung genannte Stichprobenfall**
(`mapping_id` `f2b3d29c-c1ac-4e53-ba6f-102df6dc3935`): subject_label
„Communication", object_label „use different communication channels",
`skos:narrowMatch` – justification: „‚use different communication channels' ist
spezifischer als ‚Communication' und umfasst explizit verschiedene Kanäle
(mündlich, schriftlich, digital, telefonisch), während ‚Communication' allgemein
bleibt."

> Alle diese Freitexte sagen: **das Objekt ist enger.** Genau das verlangt W3C
> SKOS und Kapitel 2 der Arbeit für `skos:narrowMatch` (`X narrowMatch Y` ⟹ Y
> enger). Gegen die korrekte Lesart sind diese 15 Records also **konsistent** –
> „widersprüchlich" sind sie nur gegenüber der invertierten Kap.-3-/Code-Lesart.

### 4.2 Fünf Records aus „konsistent" (hochkonfident, Lesart „Subjekt enger")

| # | KQR | subject_label | object_label | justification (Wortlaut) |
|---|---|---|---|---|
| 1 | dqr_2 | Comprehensive strategic career-related knowledge | manage business knowledge | „manage business knowledge" (B) umfasst die Einrichtung von Strukturen und die Nutzung von Tools zur Informationsausbeutung, was die strategische Anwendung von beruflichem Wissen (A) einschließt. |
| 2 | ecf | Application Design | ICT system analyst | „Application Design" ist ein spezifischerer Teilbereich der allgemeinen Systemanalyse-Tätigkeiten eines „ICT system analyst", da es konkrete Design- und Modellierungsaspekte (z.B. Datenstrukturen, Pilotanwendungen) abdeckt, die in der Definition des ICT system analyst enthalten sind. |
| 3 | dqr_2 | Sustainable design of learning and work processes | provide training on technological business developments | „Sustainable design of learning and work processes" (A) ist ein spezifischerer Aspekt von „provide training on technological business developments" (B), da nachhaltiges Gestalten von Lern- und Arbeitsprozessen eine mögliche Methode zur Umsetzung von Schulungen zu technologischen Geschäftsentwicklungen sein kann. |
| 4 | dqr_2 | Defining learning and work goals | analyse business processes | „Defining learning and work goals" (A) ist ein spezifischerer Teilaspekt von „analyse business processes" (B), da das Definieren von Zielen eine Voraussetzung für die Analyse von Geschäftsprozessen darstellt. |
| 5 | ecf | Technology Trend Watching | ICT research consultant | Technology Trend Watching ist eine spezifische Form der ICT-Forschung, die sich auf die Beobachtung technischer Entwicklungen konzentriert, während ICT research consultant ein breiteres Spektrum an Forschungs- und Beratungstätigkeiten umfasst. |

> Diese fünf Records benennen das **Subjekt** als das engere Konzept. Gegen W3C
> SKOS / Kapitel 2 wären genau sie die widersprüchlichen Fälle. Die beiden
> Kategorien tauschen bei korrekter Lesart also im Wesentlichen die Rollen.

---

## 5. Antwort auf die Leitfrage

- **Wie viel Prozent der `narrowMatch`/`broadMatch`-Records sind widersprüchlich?**
  `broadMatch` existiert nicht. Von den 3.629 `narrowMatch`-Records argumentiert
  der Freitext in **44,7 % (Nennwert) / 34,6 % (hochkonfidente Untergrenze) /
  ≈ 38–41 % (Punktschätzung)** gegen die Lesart „Subjekt ist enger". **Diese
  Lesart ist jedoch der Fehler** (Abschnitt 7): Gegen die W3C-konforme und in
  Kapitel 2 der Arbeit dokumentierte Lesart „Objekt ist enger" ist der Freitext
  mehrheitlich konsistent.
- **Konzentriert auf einzelne KQR oder gleichmäßig verteilt?**
  Nicht auf ein KQR konzentriert – beide Subjekt-KQR sind betroffen (`dqr_2`
  hochkonfident 30,7 %, `ecf` hochkonfident 50,3 %). KQR-Gradient (e-CF stärker),
  aber systemweit. Das passt zu einer gemeinsamen Ursache in der
  Prädikat-Ableitung, nicht zu einem KQR-spezifischen Datenproblem.

---

## 6. (weggefallen – ersetzt durch Abschnitt 7)

---

## 7. Ursache (Ergebnis der Code-Prüfung)

Geprüft: `prompts/classification_prompt_template.txt`,
`app/pipeline/step3_classification/classify.py`,
`app/pipeline/step4_export/sssom_writer.py`,
`app/models/schemas.py::RelationType.to_skos_predicate`,
`app/pipeline/step2_embedding_prefilter/prefilter.py`,
`app/services/classification_service.py`, sowie
`chapters/chapter_2/integrations/sssom.tex` und
`chapters/chapter_3/fz12_matching.tex`. Es liegen **zwei unabhängige Defekte**
vor.

### Befund 1 – Der Richtungs-Token des LLM ist funktionslos

- In ~8.360 Einzelaufrufen (`classification_results.json`) wurde als
  hierarchischer Token **ausschließlich `B_SUBSUMES_A`** erzeugt (6.455×),
  daneben nur `RELATED`. **Nie `A_SUBSUMES_B`, nie `EQUIVALENT`.**
- Der mitgelieferte `reasoning`-Text argumentiert dabei durchgängig die
  **Gegenrichtung** zum Token. Beispiel (erster `B_SUBSUMES_A`-Record):
  `subject` (= Konzept A) = e-CF „PLAN", `object` (= Konzept B) = ESCO-Skill
  „ICT capacity planning strategies"; beide Läufe: „‚ICT capacity planning
  strategies' ist ein spezifischerer **Unterbegriff** von ‚PLAN'". Laut
  `fz12_matching.tex` bedeutet `B_SUBSUMES_A` „B (Objekt) ist Oberbegriff von A"
  – der Text sagt das Gegenteil. Das Modell liest die undefinierte Zeichenkette
  `B_SUBSUMES_A` als „B **wird subsumiert von** A" und meint konsistent
  `A_SUBSUMES_B`.
- Ursachen im Prompt (`classification_prompt_template.txt`, Block 4):
  1. Die vier Tokens werden **ohne jede Definition** aufgelistet. Kein Satz der
     Art „`A_SUBSUMES_B` heißt: A ist der Oberbegriff, B fällt unter A".
     `A_SUBSUMES_B` / `B_SUBSUMES_A` sind grammatisch in beide Richtungen lesbar.
  2. Keine Angabe, welches der beiden Konzepte die Referenz ist.
  3. Der Few-Shot-Block (`classification_service.py::_build_few_shot_text`) wird
     aus den Struktur-Shortcuts gefüllt und erzeugt Zeilen der Form
     `"<Label>" skos:broadMatch "<Label>"` – also in **anderem Vokabular** als
     die vier erlaubten Ausgabe-Tokens, und nur in einer Richtung (`isPartOf`).
- Folge: Der Token trägt keine Information (konstant für jedes hierarchische
  Paar). Die uniforme `mapping_confidence = 1.0` aller `narrowMatch`-Records ist
  ein direktes Artefakt (identische Läufe). Das reale Richtungsurteil steckt nur
  im Freitext.

### Befund 2 – Die Prädikat-Abbildung ist invertiert

`app/models/schemas.py::RelationType.to_skos_predicate()`:

```python
RelationType.A_SUBSUMES_B: "skos:broadMatch",
RelationType.B_SUBSUMES_A: "skos:narrowMatch",
```

mit `subject_id = concept_a`, `object_id = concept_b` (`sssom_writer.py`), ohne
Vertauschung. Verwendet von `sssom_writer.py` (LLM-Pfad) und
`mapping_service.py` (Review-PUT).

| Quelle | Bedeutung von `skos:narrowMatch` |
|---|---|
| **W3C SKOS Reference** | `X skos:narrowMatch Y` ⟹ *Y ist enger als X* (Y = Unterbegriff) |
| **Arbeit, Kapitel 2** (`sssom.tex`, Zeile 37) | „Subject ist **weiter** als Object (Object ist Unterbegriff)" – deckt sich mit W3C |
| **Arbeit, Kapitel 3** (`tab:predicate_mapping`) + Code | `B_SUBSUMES_A → skos:narrowMatch`, gemeint als „Subjekt A ist enger" – **entgegengesetzt** |

Zusätzlich ist der **Struktur-Shortcut-Pfad im selben Code W3C-konform**:
`prefilter.py::STRUCTURAL_SHORTCUT_PREDICATES` bildet `esco:isPartOf` (Subjekt =
Teil, Objekt = Ganzes) auf `skos:broadMatch` ab – Objekt breiter. Die beiden
Mapping-Pfade nutzen damit **unterschiedliche SKOS-Konventionen in derselben
TTL**.

Kapitel 3 ist zudem in sich inkonsistent: `A_SUBSUMES_B` wird als „$c_i$ ist
Oberbegriff von $c_j$" definiert, dann auf `skos:broadMatch` abgebildet und als
OWL `$c_j$ rdfs:subClassOf $c_i$` materialisiert – die SKOS-Zeile
`$c_i$ skos:broadMatch $c_j$` besagt nach W3C aber „$c_j$ ist breiter".

### Zusammenwirken

`B_SUBSUMES_A` (LLM meint: A breiter, B enger) → `to_skos_predicate` →
`<A> skos:narrowMatch <B>`. Nach W3C / Kapitel 2 besagt dieses Tripel „B ist
enger als A" – **inhaltlich korrekt**, deckt sich mit dem Freitext. Nach
Kapitel 3 / Code-Absicht ist gemeint „A ist enger" – **falsch**. Die
Textauswertung in den Abschnitten 3–4 misst gegen die Kapitel-3-Absicht und
zählt deshalb ~40 % „widersprüchlich"; gegen die W3C-/Kapitel-2-Lesart kehrt
sich das Bild um.

### Einstufung

| Defekt | Einstufung | Behebung |
|---|---|---|
| **Befund 2** (Prädikat-Inversion) | Klarer Implementierungs- und Spezifikationsfehler | `to_skos_predicate()` auf die SKOS-/Kapitel-2-Richtung korrigieren (`A_SUBSUMES_B → skos:narrowMatch`, `B_SUBSUMES_A → skos:broadMatch`), Frontend-Spiegelung und Tests angleichen, `tab:predicate_mapping` (Kap. 3) mit `sssom.tex` (Kap. 2) versöhnen. |
| **Befund 1** (LLM-Richtungssignal) | Prompt-Designfehler; ob ein korrigierter Prompt ein funktionierendes Richtungssignal liefert, ist nur per erneutem Klassifikationslauf belegbar | Prompt-Block 4: die vier Tokens semantisch definieren und die Referenzrichtung nennen. Verifikation: voller Re-Run. Ohne Re-Run vor Abgabe → als Limitation dokumentieren. |

**Kein Relabeling des Bestands.** Eine frühere Fassung dieses Berichts schlug
vor, `predicate_id` der 3.629 Records „rein umzuetikettieren". Das ist falsch:
Weil der Token funktionslos ist (Befund 1), steht in allen Records dieselbe
Relation, während die Freitexte real in beide Richtungen argumentieren
(≈ 45 % „Objekt enger", ≈ 39 % „Objekt weiter", ≈ 16 % unklar). Ein uniformes
Umschreiben verschiebt den Fehler nur von der einen Teilmenge auf die andere.
Ein vertrauenswürdiger Richtungswert je Paar ist **nur durch erneute
Klassifikation mit dem korrigierten Prompt** zu bekommen. Nebenbefund: Die
aktuell persistierten `predicate_id`-Werte (uniform `skos:narrowMatch`) sind
durch das Zusammenwirken beider Defekte für die ≈ 45 % „Objekt enger"-Fälle
zufällig SKOS-korrekt und für die ≈ 39 % „Objekt weiter"-Fälle falsch.

**Gesamteinstufung:** behebbarer Implementierungs-/Spezifikationsfehler, kein
inhärentes methodisches Limit. Befund 2 ist im Code behoben; Befund 1 wird
entweder per Re-Run zum behobenen Fehler oder zur sauber benannten Limitation.

### Status der Behebung (2026-08-29)

Im Code umgesetzt (kein Re-Run, keine Änderung an persistierten Daten):

- `app/models/schemas.py` – `RelationType.to_skos_predicate()`: `A_SUBSUMES_B`
  → `skos:narrowMatch`, `B_SUBSUMES_A` → `skos:broadMatch` (SKOS-/Kap.-2-Richtung),
  Docstring ergänzt.
- `prompts/classification_prompt_template.txt` – Block 4: die vier Relationen
  werden jetzt definiert („A_SUBSUMES_B = Konzept A ist Oberbegriff von B, B ist
  enger"), plus expliziter Hinweis, zuerst das engere Konzept zu bestimmen.
- `app/pipeline/step4_export/sssom_writer.py` – klarstellender Kommentar an der
  `predicate_id`-Zuweisung.
- `frontend/src/features/mappings/mappingPresentation.ts` – `PREDICATE_BY_RELATION`,
  `relationFromPredicate()`, `RELATION_DESCRIPTIONS`, `PREDICATE_LABELS`,
  `PREDICATE_DESCRIPTIONS` an die korrigierte Richtung angeglichen.
- `tests/test_sssom_writer.py::test_subsumption_predicates_translated_correctly`
  – erwartete Prädikate getauscht.
- Tests: 141 Backend (pytest) und 59 Frontend (vitest) grün, `tsc --noEmit` sauber.

Offen (bewusst nicht automatisch ausgeführt):

- **Re-Klassifikation** des Default-Projekts mit dem korrigierten Prompt. Erst
  danach tragen `source_relation`, `predicate_id` und `mapping_confidence` je
  Paar eine belastbare Richtung. E2/E3 (Kap. 5) fassen beide Subsumtions-
  richtungen zu einer Klasse zusammen und sind von der Richtungskorrektur nicht
  betroffen; ein Re-Run könnte die EQUIVALENT/RELATED/SUBS-Grenzen dennoch
  leicht verschieben.
- **`chapters/chapter_3/fz12_matching.tex`**: `tab:predicate_mapping` und das
  DB-Durchlaufbeispiel tragen weiterhin die invertierte Zuordnung und müssen an
  `chapters/chapter_2/integrations/sssom.tex` angeglichen werden (Text der
  Vorlage, hier nicht geändert).

---

## 8. Weitere Beobachtungen (nicht Teil der ursprünglichen Prüfung)

- **Keine Prädikat-Vielfalt / kein `EQUIVALENT`.** Der Bestand kennt nur
  `skos:narrowMatch` und `skos:relatedMatch`; das Modell hat nie `EQUIVALENT`
  oder `A_SUBSUMES_B` erzeugt. Deckt sich mit der in `CLAUDE.md` (Abschnitt 10)
  vermerkten LLM-Richtungsverzerrung und ist jetzt über Befund 1 erklärt.
- **In sich widersprüchliche Begründungstexte.** Mindestens 138 Freitexte
  benennen Richtung und Gegenrichtung im selben Satz („B ist spezifischer … und
  umfasst A als Teilmenge") – eigenständiges Qualitätsproblem der `justification`.
- **`mapping_confidence` ohne Aussagekraft.** Alle 3.629 `narrowMatch`-Records
  tragen `1.0` (identische Läufe, vgl. Befund 1). Ein konstant gefülltes
  Konfidenzfeld kann keine Review-Priorisierung stützen. Die Confidence-Schwelle
  (E3: θ_op = 0,67) läuft für diese Records damit ins Leere.
- **`classification_runs_per_pair`** ist per Default 3
  (`app/config.py`), die persistierten Ergebnisse enthalten jedoch je 2 Läufe –
  der Bestand wurde also mit `CLASSIFICATION_RUNS_PER_PAIR=2` erzeugt.
- **Sprachmischung.** ~33 `narrowMatch`-Begründungen sind ganz oder überwiegend
  englisch statt deutsch.
- **104 `relatedMatch`-Records mit `object_kqr_id = null`**; alle 348
  `UNRESOLVED`-Records (`relatedMatch`) haben eine leere `justification`.
- **Lexische Label-Kollision.** Bei Paaren, in denen ein Label Teilstring des
  anderen ist (z. B. „Communication" ⊂ „use different communication channels"),
  ist eine textbasierte Anker-Zuordnung fehleranfällig (im Klassifikator dieser
  Prüfung abgefangen).

---

*Erstellt am 2026-08-29, Code-Prüfung ergänzt am 2026-08-29. Auswertungsskript
(nicht eingecheckt): `scratchpad/analyze2.py`. Keine Änderung an Produktions-
oder Projektdaten.*
