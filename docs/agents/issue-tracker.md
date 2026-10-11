# Issue tracker: GitHub

Issues und Spezifikationen für dieses Repo liegen in GitHub Issues:
`AlexOhu/hr-qde-harmonizer`. Für alle Issue-Operationen die `gh`-CLI im
Repo-Checkout verwenden.

## Konventionen

- Erstellen: `gh issue create --title "..." --body "..."`
- Lesen: `gh issue view <nummer> --comments`
- Auflisten: `gh issue list --state open`
- Kommentieren: `gh issue comment <nummer> --body "..."`
- Labels setzen/entfernen: `gh issue edit <nummer> --add-label "<label>"` bzw.
  `--remove-label "<label>"`
- Schließen: `gh issue close <nummer> --comment "..."`

Das Repository wird über `git remote -v` erkannt. Die GitHub-CLI verwendet
das Repo des aktuellen Checkouts.

## Pull Requests als Anfragequelle

**PRs als Anfragequelle: nein.** Externe Pull Requests werden nicht in die
Issue-Triage aufgenommen.

## Wayfinding

- Eine Map ist ein GitHub-Issue mit dem Label `wayfinder:map`; darin stehen
  Notizen, Entscheidungen und offene Fragen.
- Child-Tickets werden als GitHub-Sub-Issues verknüpft. Falls Sub-Issues
  nicht verfügbar sind, werden sie in einer Task-Liste der Map geführt und
  mit `Part of #<nummer>` markiert.
- Blockierende Abhängigkeiten werden bevorzugt als native GitHub-Issue-
  Dependencies gepflegt; andernfalls steht `Blocked by: #<nummer>` im Ticket.
- Zum Übernehmen eines Tickets `gh issue edit <nummer> --add-assignee @me`
  verwenden.
- Zum Abschließen die Antwort im Issue dokumentieren und anschließend das
  Issue schließen.
