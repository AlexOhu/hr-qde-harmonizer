# Domain docs

Dieses Repo ist ein einzelner fachlicher Kontext: der HR-QDE Harmonizer.

## Vor der Erkundung lesen

- `CONTEXT.md` im Repo-Root, sobald vorhanden.
- `docs/adr/` für Entscheidungen, die den bearbeiteten Bereich betreffen,
  sobald dort ADRs vorhanden sind.
- Bis zur Migration: `docs/ARCHITECTURE.md`, das derzeit ADR-1 bis ADR-27
  enthält.

Fehlt eine dieser Dateien, arbeite mit den vorhandenen Quellen weiter.

## Struktur

- Ein Glossar und Domänenmodell liegen in `/CONTEXT.md`.
- Neue Architekturentscheidungen liegen in `/docs/adr/`.
- `docs/ARCHITECTURE.md` bleibt die bestehende Architekturübersicht und
  Referenz für die aktuellen ADRs.

## Begriffswahl und Konflikte

Domänenbegriffe aus `CONTEXT.md` in Issues, Vorschlägen und Tests verwenden.
Widersprüche zu einer einschlägigen ADR ausdrücklich benennen, statt sie
still zu übergehen.
