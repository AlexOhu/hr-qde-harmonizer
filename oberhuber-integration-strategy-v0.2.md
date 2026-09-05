# Integrationsstrategie und Begleitprotokoll — Saeule D v0.2

Lieferdatum: 2026-09-04
Pipeline-Version: 0.2

## 1. Begleitprotokoll

### Konzepte je Rahmen

| Rahmen | Konzepte in der Lieferung |
|---|---|
| e-CF 3.0 (Dimension 2) | 40 (+ 5 Bereiche) |
| DQR 2013 (Niveaus) | 8 (als Skelett-Referenz `hrqde:DQR1`–`DQR8`) |
| EQF 2017 (Niveaus) | 8 (als Autoritaets-URI `qf-eu-level/1`–`8`) |

### Mappings je Typ

| Typ | Anzahl | Zaehlt zur Coverage |
|---|---|---|
| `harm:HubMapping` (e-CF ↔ ESCO-Skill) | 364 | ja |
| `harm:LevelMapping` (DQR ↔ EQF) | 8 | nein |
| `harm:OccupationMapping` | 0 | nein |

### Coverage-Quote

- `coverage_resolved` (finalisierte HubMappings): 364
- `coverage_total` (K ∪ C_conf inkl. offener Reviews): 965
- `coverage_ratio`: 0.377 (37.7 %)
- `open_review_count`: 601

### Bekannte Limitationen

- Offene Reviews (RELATED/UNRESOLVED) fallen aus den Artefakten; die Einzelentscheidungen stehen aus (Coverage-Nenner beruecksichtigt sie).
- Disjunkte e-CF-Konzepte tragen den automatischen Vorschlag `own_class` (`disjoint_service.suggest_strategy`); die vollstaendige manuelle Einzelpruefung steht aus.
- Kein `harm:HarmonisedCluster`: HDBSCAN erreichte keine navigierbare Hierarchie (Negativbefund, Kapitel 6).
- Kein `EQUIVALENT`-Mapping im Gesamtdatensatz (LLM-Richtungsverzerrung, Kapitel 6).

### Repraesentation

Mappings liegen ausschliesslich reifiziert als `harm:HubMapping`/`harm:LevelMapping` in `oberhuber-mappings-v{V}.ttl` vor. Es gibt keine zusaetzliche direkte SKOS-Kante, daher keine Doppelzaehlung (Spec Abschnitt 2).

## 2. Integrationsstrategie je disjunktem Konzept

| Strategie | Anzahl |
|---|---|
| `own_class` | 5 |
| `attach_to_skeleton` | 0 |
| `map_to_nearest` | 0 |
| `out_of_scope` | 0 |

Alle disjunkten Konzepte tragen den automatischen Vorschlag `own_class` (`disjoint_service.suggest_strategy`). Eine manuelle Einzelpruefung steht aus (siehe Limitationen).

## 3. CEN-EN-16234-1-Crosswalk: e-CF Dimension 3 → EQF

Dieser Crosswalk erscheint bewusst NICHT als `harm:LevelMapping` im Lieferartefakt (ADR-24): die kanonische `LevelMappingShape` verlangt fuer Subjekt und Objekt eine Niveau-URI. Eine e-CF-Kompetenz ist kein Niveau. Der Zusammenhang wird daher hier narrativ dokumentiert.

Stufenband-Semantik: dieselbe Kompetenz auf verschiedenen Verantwortungsebenen ergibt mehrere EQF-Ziele. Zusaetzlich verdoppelt e-3 jede Zuordnung (EQF 5 UND EQF 6), weil der CEN-Standard fuer diese Stufe einen Bereich angibt.

| e-CF-Kompetenz | Proficiency | EQF |
|---|---|---|
| A.1 — IS and Business Strategy Alignment | e-4 | EQF 7 |
| A.1 — IS and Business Strategy Alignment | e-5 | EQF 8 |
| A.2 — Service Level Management | e-3 | EQF 5 |
| A.2 — Service Level Management | e-3 | EQF 6 |
| A.2 — Service Level Management | e-4 | EQF 7 |
| A.3 — Business Plan Development | e-3 | EQF 5 |
| A.3 — Business Plan Development | e-3 | EQF 6 |
| A.3 — Business Plan Development | e-4 | EQF 7 |
| A.3 — Business Plan Development | e-5 | EQF 8 |
| A.4 — Product / Service Planning | e-2 | EQF 4 |
| A.4 — Product / Service Planning | e-3 | EQF 5 |
| A.4 — Product / Service Planning | e-3 | EQF 6 |
| A.4 — Product / Service Planning | e-4 | EQF 7 |
| A.5 — Architecture Design | e-3 | EQF 5 |
| A.5 — Architecture Design | e-3 | EQF 6 |
| A.5 — Architecture Design | e-4 | EQF 7 |
| A.5 — Architecture Design | e-5 | EQF 8 |
| A.6 — Application Design | e-1 | EQF 3 |
| A.6 — Application Design | e-2 | EQF 4 |
| A.6 — Application Design | e-3 | EQF 5 |
| A.6 — Application Design | e-3 | EQF 6 |
| A.7 — Technology Trend Watching | e-4 | EQF 7 |
| A.7 — Technology Trend Watching | e-5 | EQF 8 |
| A.8 — Sustainable Development | e-2 | EQF 4 |
| A.8 — Sustainable Development | e-3 | EQF 5 |
| A.8 — Sustainable Development | e-3 | EQF 6 |
| A.8 — Sustainable Development | e-4 | EQF 7 |
| A.9 — Innovating | e-4 | EQF 7 |
| A.9 — Innovating | e-5 | EQF 8 |
| B.1 — Application Development | e-1 | EQF 3 |
| B.1 — Application Development | e-2 | EQF 4 |
| B.1 — Application Development | e-3 | EQF 5 |
| B.1 — Application Development | e-3 | EQF 6 |
| B.2 — Component Integration | e-2 | EQF 4 |
| B.2 — Component Integration | e-3 | EQF 5 |
| B.2 — Component Integration | e-3 | EQF 6 |
| B.3 — Testing | e-1 | EQF 3 |
| B.3 — Testing | e-2 | EQF 4 |
| B.3 — Testing | e-3 | EQF 5 |
| B.3 — Testing | e-3 | EQF 6 |
| B.3 — Testing | e-4 | EQF 7 |
| B.4 — Solution Deployment | e-1 | EQF 3 |
| B.4 — Solution Deployment | e-2 | EQF 4 |
| B.4 — Solution Deployment | e-3 | EQF 5 |
| B.4 — Solution Deployment | e-3 | EQF 6 |
| B.5 — Documentation Production | e-1 | EQF 3 |
| B.5 — Documentation Production | e-2 | EQF 4 |
| B.5 — Documentation Production | e-3 | EQF 5 |
| B.5 — Documentation Production | e-3 | EQF 6 |
| B.6 — Systems Engineering | e-3 | EQF 5 |
| B.6 — Systems Engineering | e-3 | EQF 6 |
| B.6 — Systems Engineering | e-4 | EQF 7 |
| C.1 — User Support | e-1 | EQF 3 |
| C.1 — User Support | e-2 | EQF 4 |
| C.1 — User Support | e-3 | EQF 5 |
| C.1 — User Support | e-3 | EQF 6 |
| C.2 — Change Support | e-2 | EQF 4 |
| C.2 — Change Support | e-3 | EQF 5 |
| C.2 — Change Support | e-3 | EQF 6 |
| C.3 — Service Delivery | e-1 | EQF 3 |
| C.3 — Service Delivery | e-2 | EQF 4 |
| C.3 — Service Delivery | e-3 | EQF 5 |
| C.3 — Service Delivery | e-3 | EQF 6 |
| C.4 — Problem Management | e-2 | EQF 4 |
| C.4 — Problem Management | e-3 | EQF 5 |
| C.4 — Problem Management | e-3 | EQF 6 |
| C.4 — Problem Management | e-4 | EQF 7 |
| D.1 — Information Security Strategy Development | e-4 | EQF 7 |
| D.1 — Information Security Strategy Development | e-5 | EQF 8 |
| D.2 — ICT Quality Strategy Development | e-4 | EQF 7 |
| D.2 — ICT Quality Strategy Development | e-5 | EQF 8 |
| D.3 — Education and Training Provision | e-3 | EQF 5 |
| D.3 — Education and Training Provision | e-3 | EQF 6 |
| D.3 — Education and Training Provision | e-4 | EQF 7 |
| D.4 — Purchasing | e-2 | EQF 4 |
| D.4 — Purchasing | e-3 | EQF 5 |
| D.4 — Purchasing | e-3 | EQF 6 |
| D.4 — Purchasing | e-4 | EQF 7 |
| D.5 — Sales Proposal Development | e-3 | EQF 5 |
| D.5 — Sales Proposal Development | e-3 | EQF 6 |
| D.5 — Sales Proposal Development | e-4 | EQF 7 |
| D.6 — Channel Management | e-3 | EQF 5 |
| D.6 — Channel Management | e-3 | EQF 6 |
| D.6 — Channel Management | e-4 | EQF 7 |
| D.7 — Sales Management | e-3 | EQF 5 |
| D.7 — Sales Management | e-3 | EQF 6 |
| D.7 — Sales Management | e-4 | EQF 7 |
| D.8 — Contract Management | e-3 | EQF 5 |
| D.8 — Contract Management | e-3 | EQF 6 |
| D.8 — Contract Management | e-4 | EQF 7 |
| D.9 — Personnel Development | e-2 | EQF 4 |
| D.9 — Personnel Development | e-3 | EQF 5 |
| D.9 — Personnel Development | e-3 | EQF 6 |
| D.9 — Personnel Development | e-4 | EQF 7 |
| D.10 — Information and Knowledge Management | e-3 | EQF 5 |
| D.10 — Information and Knowledge Management | e-3 | EQF 6 |
| D.10 — Information and Knowledge Management | e-4 | EQF 7 |
| D.10 — Information and Knowledge Management | e-5 | EQF 8 |
| D.11 — Needs Identification | e-3 | EQF 5 |
| D.11 — Needs Identification | e-3 | EQF 6 |
| D.11 — Needs Identification | e-4 | EQF 7 |
| D.12 — Digital Marketing | e-3 | EQF 5 |
| D.12 — Digital Marketing | e-3 | EQF 6 |
| D.12 — Digital Marketing | e-4 | EQF 7 |
| D.12 — Digital Marketing | e-5 | EQF 8 |
| E.1 — Forecast Development | e-3 | EQF 5 |
| E.1 — Forecast Development | e-3 | EQF 6 |
| E.1 — Forecast Development | e-4 | EQF 7 |
| E.2 — Project and Portfolio Management | e-3 | EQF 5 |
| E.2 — Project and Portfolio Management | e-3 | EQF 6 |
| E.2 — Project and Portfolio Management | e-4 | EQF 7 |
| E.2 — Project and Portfolio Management | e-5 | EQF 8 |
| E.3 — Risk Management | e-2 | EQF 4 |
| E.3 — Risk Management | e-3 | EQF 5 |
| E.3 — Risk Management | e-3 | EQF 6 |
| E.3 — Risk Management | e-4 | EQF 7 |
| E.4 — Relationship Management | e-3 | EQF 5 |
| E.4 — Relationship Management | e-3 | EQF 6 |
| E.4 — Relationship Management | e-4 | EQF 7 |
| E.5 — Process Improvement | e-3 | EQF 5 |
| E.5 — Process Improvement | e-3 | EQF 6 |
| E.5 — Process Improvement | e-4 | EQF 7 |
| E.6 — ICT Quality Management | e-2 | EQF 4 |
| E.6 — ICT Quality Management | e-3 | EQF 5 |
| E.6 — ICT Quality Management | e-3 | EQF 6 |
| E.6 — ICT Quality Management | e-4 | EQF 7 |
| E.7 — Business Change Management | e-3 | EQF 5 |
| E.7 — Business Change Management | e-3 | EQF 6 |
| E.7 — Business Change Management | e-4 | EQF 7 |
| E.8 — Information Security Management | e-2 | EQF 4 |
| E.8 — Information Security Management | e-3 | EQF 5 |
| E.8 — Information Security Management | e-3 | EQF 6 |
| E.8 — Information Security Management | e-4 | EQF 7 |
| E.9 — IS Governance | e-4 | EQF 7 |
| E.9 — IS Governance | e-5 | EQF 8 |

Stand: normative Referenz `qf-eu-level`-Autoritaets-URIs unter `http://data.europa.eu/snb/qf-eu-level/`.
