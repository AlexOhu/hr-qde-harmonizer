# Integrationsstrategie und Begleitprotokoll — Saeule D v0.4

Lieferdatum: 2026-10-04
Pipeline-Version: 0.4

## 1. Begleitprotokoll

### Konzepte je Rahmen

| Rahmen | Konzepte in der Lieferung |
|---|---|
| e-CF 3.0 (Dimension 2) | 40 (+ 0 Bereiche) |
| e-CF 3.0 (Dimension 3) | 106 LevelConcepts |
| DQR 2013 (Niveaus) | 8 (als Skelett-Referenz `hrqde:DQR1`–`DQR8`) |
| EQF 2017 (Niveaus) | 8 (als Autoritaets-URI `qf-eu-level/1`–`8`) |

### Mappings je Typ

| Typ | Anzahl | Zaehlt zur Coverage |
|---|---|---|
| `harm:HubMapping` (e-CF ↔ ESCO-Skill) | 440 | ja |
| `harm:LevelMapping` (e-CF Dimension 3 ↔ DQR) | 113 | nein |
| `harm:LevelMapping` (DQR ↔ EQF) | 8 | nein |
| `harm:OccupationMapping` | 0 | nein |

### Coverage-Quote

- `coverage_resolved` (finalisierte HubMappings): 440
- `coverage_total` (K ∪ C_conf inkl. offener Reviews): 999
- `coverage_ratio`: 0.440 (44.0 %)
- `open_review_count`: 559

### Bekannte Limitationen

- Offene Reviews (RELATED/UNRESOLVED) fallen aus den Artefakten; die Einzelentscheidungen stehen aus (Coverage-Nenner beruecksichtigt sie).
- Disjunkte e-CF-Konzepte tragen den automatischen Vorschlag `own_class` (`disjoint_service.suggest_strategy`); die vollstaendige manuelle Einzelpruefung steht aus.
- Kein `harm:HarmonisedCluster`: HDBSCAN erreichte keine navigierbare Hierarchie (Negativbefund, Kapitel 6).
- Die e-CF-Dimension-3-zu-DQR-Mappings sind normative, deterministische LevelMappings aus e-CF 3.0 (CWA 16234-1:2014), kein LLM-Ergebnis.
- Nur 1 von 800 klassifizierten Paaren erhielten `EQUIVALENT`; die Erkennung von Aequivalenz bleibt unzuverlaessig (Kapitel 5 und 6).

### Repraesentation

Mappings liegen ausschliesslich reifiziert als `harm:HubMapping`/`harm:LevelMapping` in `oberhuber-mappings-v{V}.ttl` vor. Es gibt keine zusaetzliche direkte SKOS-Kante, daher keine Doppelzaehlung.

## 2. Integrationsstrategie je disjunktem Konzept

| Strategie | Anzahl |
|---|---|
| `own_class` | 3 |
| `attach_to_skeleton` | 0 |
| `map_to_nearest` | 0 |
| `out_of_scope` | 0 |

Alle disjunkten Konzepte tragen den automatischen Vorschlag `own_class` (`disjoint_service.suggest_strategy`). Eine manuelle Einzelpruefung steht aus (siehe Limitationen).

## 3. Niveaukette: e-CF Dimension 2 → Dimension 3 → DQR

e-CF-Dimension-2-Kompetenzen sind als `harm:CompetenceConcept` typisiert und über `harm:hasLevel` mit ihren `harm:LevelConcept`-Beschreibungen verbunden. Jede normative Zuordnung eines Dimension-3-Knotens auf einen DQR-Anker wird als `harm:LevelMapping` mit `skos:closeMatch` serialisiert. Diese Records zählen nicht zur ESCO-Coverage.

| e-CF-LevelConcept | Proficiency | DQR-Anker |
|---|---|---|
| A.1 Niveau 4 — A.1 – IS and Business Strategy Alignment, Proficiency 4 | e-4 | DQR L7 |
| A.1 Niveau 5 — A.1 – IS and Business Strategy Alignment, Proficiency 5 | e-5 | DQR L8 |
| A.2 Niveau 3 — A.2 – Service Level Management, Proficiency 3 | e-3 | DQR L6 |
| A.2 Niveau 4 — A.2 – Service Level Management, Proficiency 4 | e-4 | DQR L7 |
| A.3 Niveau 3 — A.3 – Business Plan Development, Proficiency 3 | e-3 | DQR L6 |
| A.3 Niveau 4 — A.3 – Business Plan Development, Proficiency 4 | e-4 | DQR L7 |
| A.3 Niveau 5 — A.3 – Business Plan Development, Proficiency 5 | e-5 | DQR L8 |
| A.4 Niveau 2 — A.4 – Product / Service Planning, Proficiency 2 | e-2 | DQR L5 |
| A.4 Niveau 3 — A.4 – Product / Service Planning, Proficiency 3 | e-3 | DQR L6 |
| A.4 Niveau 4 — A.4 – Product / Service Planning, Proficiency 4 | e-4 | DQR L7 |
| A.5 Niveau 3 — A.5 – Architecture Design, Proficiency 3 | e-3 | DQR L6 |
| A.5 Niveau 4 — A.5 – Architecture Design, Proficiency 4 | e-4 | DQR L7 |
| A.5 Niveau 5 — A.5 – Architecture Design, Proficiency 5 | e-5 | DQR L8 |
| A.6 Niveau 1 — A.6 – Application Design, Proficiency 1 | e-1 | DQR L3 |
| A.6 Niveau 1 — A.6 – Application Design, Proficiency 1 | e-1 | DQR L4 |
| A.6 Niveau 2 — A.6 – Application Design, Proficiency 2 | e-2 | DQR L5 |
| A.6 Niveau 3 — A.6 – Application Design, Proficiency 3 | e-3 | DQR L6 |
| A.7 Niveau 4 — A.7 – Technology Trend Watching, Proficiency 4 | e-4 | DQR L7 |
| A.7 Niveau 5 — A.7 – Technology Trend Watching, Proficiency 5 | e-5 | DQR L8 |
| A.8 Niveau 3 — A.8 – Sustainable Development, Proficiency 3 | e-3 | DQR L6 |
| A.8 Niveau 4 — A.8 – Sustainable Development, Proficiency 4 | e-4 | DQR L7 |
| A.9 Niveau 4 — A.9 – Innovating, Proficiency 4 | e-4 | DQR L7 |
| A.9 Niveau 5 — A.9 – Innovating, Proficiency 5 | e-5 | DQR L8 |
| B.1 Niveau 1 — B.1 – Application Development, Proficiency 1 | e-1 | DQR L3 |
| B.1 Niveau 1 — B.1 – Application Development, Proficiency 1 | e-1 | DQR L4 |
| B.1 Niveau 2 — B.1 – Application Development, Proficiency 2 | e-2 | DQR L5 |
| B.1 Niveau 3 — B.1 – Application Development, Proficiency 3 | e-3 | DQR L6 |
| B.2 Niveau 2 — B.2 – Component Integration, Proficiency 2 | e-2 | DQR L5 |
| B.2 Niveau 3 — B.2 – Component Integration, Proficiency 3 | e-3 | DQR L6 |
| B.2 Niveau 4 — B.2 – Component Integration, Proficiency 4 | e-4 | DQR L7 |
| B.3 Niveau 1 — B.3 – Testing, Proficiency 1 | e-1 | DQR L3 |
| B.3 Niveau 1 — B.3 – Testing, Proficiency 1 | e-1 | DQR L4 |
| B.3 Niveau 2 — B.3 – Testing, Proficiency 2 | e-2 | DQR L5 |
| B.3 Niveau 3 — B.3 – Testing, Proficiency 3 | e-3 | DQR L6 |
| B.3 Niveau 4 — B.3 – Testing, Proficiency 4 | e-4 | DQR L7 |
| B.4 Niveau 1 — B.4 – Solution Deployment, Proficiency 1 | e-1 | DQR L3 |
| B.4 Niveau 1 — B.4 – Solution Deployment, Proficiency 1 | e-1 | DQR L4 |
| B.4 Niveau 2 — B.4 – Solution Deployment, Proficiency 2 | e-2 | DQR L5 |
| B.4 Niveau 3 — B.4 – Solution Deployment, Proficiency 3 | e-3 | DQR L6 |
| B.5 Niveau 1 — B.5 – Documentation Production, Proficiency 1 | e-1 | DQR L3 |
| B.5 Niveau 1 — B.5 – Documentation Production, Proficiency 1 | e-1 | DQR L4 |
| B.5 Niveau 2 — B.5 – Documentation Production, Proficiency 2 | e-2 | DQR L5 |
| B.5 Niveau 3 — B.5 – Documentation Production, Proficiency 3 | e-3 | DQR L6 |
| B.6 Niveau 3 — B.6 – Systems Engineering, Proficiency 3 | e-3 | DQR L6 |
| B.6 Niveau 4 — B.6 – Systems Engineering, Proficiency 4 | e-4 | DQR L7 |
| C.1 Niveau 1 — C.1 – User Support, Proficiency 1 | e-1 | DQR L3 |
| C.1 Niveau 1 — C.1 – User Support, Proficiency 1 | e-1 | DQR L4 |
| C.1 Niveau 2 — C.1 – User Support, Proficiency 2 | e-2 | DQR L5 |
| C.1 Niveau 3 — C.1 – User Support, Proficiency 3 | e-3 | DQR L6 |
| C.2 Niveau 2 — C.2 – Change Support, Proficiency 2 | e-2 | DQR L5 |
| C.2 Niveau 3 — C.2 – Change Support, Proficiency 3 | e-3 | DQR L6 |
| C.3 Niveau 1 — C.3 – Service Delivery, Proficiency 1 | e-1 | DQR L3 |
| C.3 Niveau 1 — C.3 – Service Delivery, Proficiency 1 | e-1 | DQR L4 |
| C.3 Niveau 2 — C.3 – Service Delivery, Proficiency 2 | e-2 | DQR L5 |
| C.3 Niveau 3 — C.3 – Service Delivery, Proficiency 3 | e-3 | DQR L6 |
| C.4 Niveau 2 — C.4 – Problem Management, Proficiency 2 | e-2 | DQR L5 |
| C.4 Niveau 3 — C.4 – Problem Management, Proficiency 3 | e-3 | DQR L6 |
| C.4 Niveau 4 — C.4 – Problem Management, Proficiency 4 | e-4 | DQR L7 |
| D.1 Niveau 4 — D.1 – Information Security Strategy Development, Proficiency 4 | e-4 | DQR L7 |
| D.1 Niveau 5 — D.1 – Information Security Strategy Development, Proficiency 5 | e-5 | DQR L8 |
| D.10 Niveau 3 — D.10 – Information and Knowledge Management, Proficiency 3 | e-3 | DQR L6 |
| D.10 Niveau 4 — D.10 – Information and Knowledge Management, Proficiency 4 | e-4 | DQR L7 |
| D.10 Niveau 5 — D.10 – Information and Knowledge Management, Proficiency 5 | e-5 | DQR L8 |
| D.11 Niveau 3 — D.11 – Needs Identification, Proficiency 3 | e-3 | DQR L6 |
| D.11 Niveau 4 — D.11 – Needs Identification, Proficiency 4 | e-4 | DQR L7 |
| D.11 Niveau 5 — D.11 – Needs Identification, Proficiency 5 | e-5 | DQR L8 |
| D.12 Niveau 2 — D.12 – Digital Marketing, Proficiency 2 | e-2 | DQR L5 |
| D.12 Niveau 3 — D.12 – Digital Marketing, Proficiency 3 | e-3 | DQR L6 |
| D.12 Niveau 4 — D.12 – Digital Marketing, Proficiency 4 | e-4 | DQR L7 |
| D.2 Niveau 4 — D.2 – ICT Quality Strategy Development, Proficiency 4 | e-4 | DQR L7 |
| D.2 Niveau 5 — D.2 – ICT Quality Strategy Development, Proficiency 5 | e-5 | DQR L8 |
| D.3 Niveau 2 — D.3 – Education and Training Provision, Proficiency 2 | e-2 | DQR L5 |
| D.3 Niveau 3 — D.3 – Education and Training Provision, Proficiency 3 | e-3 | DQR L6 |
| D.4 Niveau 2 — D.4 – Purchasing, Proficiency 2 | e-2 | DQR L5 |
| D.4 Niveau 3 — D.4 – Purchasing, Proficiency 3 | e-3 | DQR L6 |
| D.4 Niveau 4 — D.4 – Purchasing, Proficiency 4 | e-4 | DQR L7 |
| D.5 Niveau 3 — D.5 – Sales Proposal Development, Proficiency 3 | e-3 | DQR L6 |
| D.5 Niveau 4 — D.5 – Sales Proposal Development, Proficiency 4 | e-4 | DQR L7 |
| D.6 Niveau 3 — D.6 – Channel Management, Proficiency 3 | e-3 | DQR L6 |
| D.6 Niveau 4 — D.6 – Channel Management, Proficiency 4 | e-4 | DQR L7 |
| D.7 Niveau 3 — D.7 – Sales Management, Proficiency 3 | e-3 | DQR L6 |
| D.7 Niveau 4 — D.7 – Sales Management, Proficiency 4 | e-4 | DQR L7 |
| D.7 Niveau 5 — D.7 – Sales Management, Proficiency 5 | e-5 | DQR L8 |
| D.8 Niveau 2 — D.8 – Contract Management, Proficiency 2 | e-2 | DQR L5 |
| D.8 Niveau 3 — D.8 – Contract Management, Proficiency 3 | e-3 | DQR L6 |
| D.8 Niveau 4 — D.8 – Contract Management, Proficiency 4 | e-4 | DQR L7 |
| D.9 Niveau 2 — D.9 – Personnel Development, Proficiency 2 | e-2 | DQR L5 |
| D.9 Niveau 3 — D.9 – Personnel Development, Proficiency 3 | e-3 | DQR L6 |
| D.9 Niveau 4 — D.9 – Personnel Development, Proficiency 4 | e-4 | DQR L7 |
| E.1 Niveau 3 — E.1 – Forecast Development, Proficiency 3 | e-3 | DQR L6 |
| E.1 Niveau 4 — E.1 – Forecast Development, Proficiency 4 | e-4 | DQR L7 |
| E.2 Niveau 2 — E.2 – Project and Portfolio Management, Proficiency 2 | e-2 | DQR L5 |
| E.2 Niveau 3 — E.2 – Project and Portfolio Management, Proficiency 3 | e-3 | DQR L6 |
| E.2 Niveau 4 — E.2 – Project and Portfolio Management, Proficiency 4 | e-4 | DQR L7 |
| E.2 Niveau 5 — E.2 – Project and Portfolio Management, Proficiency 5 | e-5 | DQR L8 |
| E.3 Niveau 2 — E.3 – Risk Management, Proficiency 2 | e-2 | DQR L5 |
| E.3 Niveau 3 — E.3 – Risk Management, Proficiency 3 | e-3 | DQR L6 |
| E.3 Niveau 4 — E.3 – Risk Management, Proficiency 4 | e-4 | DQR L7 |
| E.4 Niveau 3 — E.4 – Relationship Management, Proficiency 3 | e-3 | DQR L6 |
| E.4 Niveau 4 — E.4 – Relationship Management, Proficiency 4 | e-4 | DQR L7 |
| E.5 Niveau 3 — E.5 – Process Improvement, Proficiency 3 | e-3 | DQR L6 |
| E.5 Niveau 4 — E.5 – Process Improvement, Proficiency 4 | e-4 | DQR L7 |
| E.6 Niveau 2 — E.6 – ICT Quality Management, Proficiency 2 | e-2 | DQR L5 |
| E.6 Niveau 3 — E.6 – ICT Quality Management, Proficiency 3 | e-3 | DQR L6 |
| E.6 Niveau 4 — E.6 – ICT Quality Management, Proficiency 4 | e-4 | DQR L7 |
| E.7 Niveau 3 — E.7 – Business Change Management, Proficiency 3 | e-3 | DQR L6 |
| E.7 Niveau 4 — E.7 – Business Change Management, Proficiency 4 | e-4 | DQR L7 |
| E.7 Niveau 5 — E.7 – Business Change Management, Proficiency 5 | e-5 | DQR L8 |
| E.8 Niveau 2 — E.8 – Information Security Management, Proficiency 2 | e-2 | DQR L5 |
| E.8 Niveau 3 — E.8 – Information Security Management, Proficiency 3 | e-3 | DQR L6 |
| E.8 Niveau 4 — E.8 – Information Security Management, Proficiency 4 | e-4 | DQR L7 |
| E.9 Niveau 4 — E.9 – IS Governance, Proficiency 4 | e-4 | DQR L7 |
| E.9 Niveau 5 — E.9 – IS Governance, Proficiency 5 | e-5 | DQR L8 |

Provenienz: normative e-CF-3.0-Crosswalk (CWA 16234-1:2014); `mapping_justification = semapv:ManualMappingCuration`, `mapping_confidence = 1.0`.
