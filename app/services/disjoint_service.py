"""
Verwaltet Integrationsstrategien für disjunkte Konzepte (D1 ∪ D2, FZ3.3).

Disjunktes Konzept = Konzept, das in keinem Mapping mit predicate_id
skos:exactMatch / skos:broadMatch / skos:narrowMatch vorkommt (der
konjunkten Menge K). RELATED/UNRESOLVED-Klassifikationsergebnisse sind
Kandidaten für diese Service-Schicht.

Persistenz: data/projects/{project_id}/disjoint_decisions.json (ADR-02),
In-Memory-Cache nach project_id kodiert (ADR-04).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models.schemas import Concept, DisjointConceptDecision, DisjointStrategy
from app.services import kqr_service, mapping_service, project_service

# predicate_id-Werte, die Bestandteil der konjunkten Menge K sind
# (vgl. RelationType.to_skos_predicate() für EQUIVALENT/A_SUBSUMES_B/B_SUBSUMES_A).
_K_PREDICATES = {"skos:exactMatch", "skos:broadMatch", "skos:narrowMatch"}

_decisions: dict[str, list[DisjointConceptDecision]] = {}


def _decisions_path(project_id: str) -> Path:
    return project_service.get_project_data_dir(project_id) / "disjoint_decisions.json"


def _load_decisions(project_id: str) -> list[DisjointConceptDecision]:
    path = _decisions_path(project_id)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [DisjointConceptDecision(**item) for item in data]


def _save_decisions(project_id: str) -> None:
    path = _decisions_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [d.model_dump(mode="json") for d in _get_decisions(project_id)], indent=2, ensure_ascii=False
        ),
        encoding="utf-8",
    )


def _get_decisions(project_id: str) -> list[DisjointConceptDecision]:
    if project_id not in _decisions:
        _decisions[project_id] = _load_decisions(project_id)
    return _decisions[project_id]


def _all_concepts_by_layer(project_id: str | None = None) -> list[Concept]:
    """Konzepte aller registrierten (formalisierten) KQR, zuerst D1
    (Nicht-Hub-KQR), dann D2 (Hub) -- vgl. Tabelle 'kqr_schichten'.

    Mit project_id: nur Konzepte der KQR, die dieses Projekt tatsaechlich
    referenziert (project.kqr_ids). Ohne project_id (Rueckwaertskompatibilitaet
    fuer find_concept(), das konzeptbezogen und bewusst projektunabhaengig
    bleibt, KQR-Rohdaten sind projektuebergreifend global, ADR-01): global
    ueber alle registrierten KQR, wie zuvor."""
    kqrs = sorted(kqr_service.list_kqr(), key=lambda kqr: kqr.is_hub)
    if project_id is not None:
        try:
            allowed = set(project_service.get_project(project_id).kqr_ids)
        except KeyError:
            # Kein persistierter Project-Datensatz zu project_id (z. B.
            # Testfixtures, die "default" nur als Konvention verwenden, ohne
            # project_service.create_project() aufzurufen) -- Rueckfall auf
            # das bisherige globale Verhalten statt hart zu scheitern.
            allowed = None
        if allowed is not None:
            kqrs = [kqr for kqr in kqrs if kqr.id in allowed]
    concepts: list[Concept] = []
    for kqr in kqrs:
        try:
            concepts.extend(kqr_service.get_concepts(kqr.id))
        except ValueError:
            continue  # noch nicht formalisiert -- keine Konzepte verfügbar
    return concepts


def _matched_concept_uris(project_id: str) -> set[str]:
    """URIs aller Konzepte, die auf Subjekt- oder Objektseite eines
    K-Mappings (exactMatch/broadMatch/narrowMatch) vorkommen, projektweit
    über alle KQR-Paar-Läufe hinweg. Für eine paarbezogene Betrachtung
    _matched_concept_uris_for_pair() verwenden -- ein Konzept mit einem
    K-Mapping aus einem anderen Paar gilt hier bereits als "nicht
    disjunkt", was für die Aussage zu einem einzelnen Paar A↔B falsch ist."""
    uris: set[str] = set()
    for mapping in mapping_service.list_mappings(project_id=project_id):
        if mapping.predicate_id in _K_PREDICATES:
            uris.add(mapping.subject_id)
            uris.add(mapping.object_id)
    return uris


def _matched_concept_uris_for_pair(kqr_a_id: str, kqr_b_id: str, project_id: str) -> set[str]:
    """URIs aller Konzepte, die auf Subjekt- oder Objektseite eines
    K-Mappings vorkommen, das exakt zum Paar (kqr_a_id, kqr_b_id) gehört."""
    uris: set[str] = set()
    for mapping in mapping_service.list_mappings_for_pair(kqr_a_id, kqr_b_id, project_id=project_id):
        if mapping.predicate_id in _K_PREDICATES:
            uris.add(mapping.subject_id)
            uris.add(mapping.object_id)
    return uris


def list_disjoint_concepts(kqr_id: str | None = None, project_id: str = "default") -> list[Concept]:
    """
    Alle Konzepte aus allen registrierten KQR, die in keinem K-Mapping
    (exactMatch/broadMatch/narrowMatch) auf Subjekt- oder Objektseite
    vorkommen. Reihenfolge: zuerst Konzepte aus D1 (Nicht-Hub-KQR), dann D2
    (Hub). kqr_id grenzt optional auf ein einzelnes KQR ein.

    Projektweite Grundmenge (vgl. _matched_concept_uris()) -- für die
    paarbezogene Aussage list_disjoint_concepts_for_pair() verwenden.
    """
    matched = _matched_concept_uris(project_id)
    concepts = [c for c in _all_concepts_by_layer(project_id=project_id) if c.uri not in matched]
    if kqr_id is not None:
        concepts = [c for c in concepts if c.kqr_id == kqr_id]
    return concepts


def list_disjoint_concepts_for_pair(
    kqr_a_id: str, kqr_b_id: str, project_id: str = "default"
) -> list[Concept]:
    """
    Disjunkte Konzepte bezogen auf genau ein KQR-Paar: Konzepte aus KQR A
    oder KQR B, die in keinem K-Mapping vorkommen, das exakt zu diesem
    Paar gehört. Im Unterschied zu list_disjoint_concepts() zählt ein
    K-Mapping aus einem anderen Paar (z. B. A↔C) hier NICHT als "nicht
    disjunkt" -- ein Konzept aus KQR A ohne Mapping in A↔B ist bezogen
    auf dieses Paar disjunkt, unabhängig vom Status in A↔C.
    """
    matched = _matched_concept_uris_for_pair(kqr_a_id, kqr_b_id, project_id)
    pair_kqr_ids = {kqr_a_id, kqr_b_id}
    return [
        c
        for c in _all_concepts_by_layer(project_id=project_id)
        if c.kqr_id in pair_kqr_ids and c.uri not in matched
    ]


def suggest_strategy(concept: Concept, project_id: str = "default") -> DisjointStrategy:
    """
    Heuristik ohne LLM-Aufruf (Mixed Initiative: System schlägt vor,
    Nutzer entscheidet):
    - Hat das Konzept ein RELATED-Mapping → ATTACH_TO_SKELETON
      (es gibt eine semantische Nähe, aber keine Äquivalenz).
    - Sonst (UNRESOLVED oder kein Mapping) → OWN_CLASS.
    Bewusst konservativ: OUT_OF_SCOPE wird nie automatisch vorgeschlagen, und
    MAP_TO_NEAREST ebenfalls nicht -- diese Strategie erzwingt einen
    Kontextverlust-Vermerk, den nur ein Mensch verantworten kann.
    """
    if concept.uri in mapping_service.get_related_concept_uris(project_id=project_id):
        return DisjointStrategy.ATTACH_TO_SKELETON
    return DisjointStrategy.OWN_CLASS


def find_concept(concept_id: str, project_id: str | None = None) -> Concept:
    """Löst eine Concept.uri zu ihrem Concept-Objekt auf (Grundlage für
    suggest_strategy() und decide() aus der API-Route).

    Mit project_id wird zuerst nur unter den KQR gesucht, die dieses Projekt
    tatsächlich referenziert (project.kqr_ids). Das verhindert eine falsche
    kqr_id-Zuordnung, wenn mehrere registrierte KQR dieselbe Konzept-URI
    führen. Ohne project_id -- oder wenn zu project_id kein Project-Datensatz
    existiert (z. B. Testfixtures) -- fällt _all_concepts_by_layer() auf die
    globale Suche über alle registrierten KQR zurück (gleiches
    Fallback-Muster wie dort)."""
    for concept in _all_concepts_by_layer(project_id=project_id):
        if concept.uri == concept_id:
            return concept
    raise KeyError(f"Konzept '{concept_id}' nicht gefunden.")


def decide(
    concept_id: str,
    strategy: DisjointStrategy,
    justification: str,
    author: str,
    anchor_class: str | None = None,
    context_loss_note: str | None = None,
    fallback_label: str | None = None,
    fallback_kqr_id: str | None = None,
    project_id: str = "default",
) -> DisjointConceptDecision:
    """
    Persistiert eine Entscheidung. Justification ist verpflichtend
    (Accountability-Prinzip). Eine bestehende Entscheidung für dasselbe
    concept_id wird überschrieben (kein stilles Duplizieren).

    MAP_TO_NEAREST verlangt einen context_loss_note: Beim Anhängen an das
    nächstgelegene Hub-Konzept geht Bedeutung verloren, und dieser Verlust
    muss dokumentiert sein, statt in der Ontologie unsichtbar zu bleiben.

    fallback_label/fallback_kqr_id greifen, wenn das Konzept nicht mehr über
    die KQR-Registry auflösbar ist. Der Review-Weg
    (mapping_service.review_mapping) kennt Label und Herkunfts-KQR aus dem
    Mapping selbst und soll nicht daran scheitern, dass ein KQR
    zwischenzeitlich abgemeldet wurde.
    """
    project_service.ensure_writable(project_id)
    if strategy == DisjointStrategy.MAP_TO_NEAREST and not (context_loss_note or "").strip():
        raise ValueError(
            "context_loss_note ist bei strategy='map_to_nearest' ein Pflichtfeld."
        )
    try:
        concept = find_concept(concept_id, project_id=project_id)
        concept_label, kqr_id = concept.pref_label, concept.kqr_id
    except KeyError:
        if fallback_label is None:
            raise
        concept_label, kqr_id = fallback_label, fallback_kqr_id or "unbekannt"

    # KQR-Kombination festhalten, gegen die entschieden wird. Sortiert, damit
    # suggest_reusable_decision() Teilmengen unabhängig von der Reihenfolge in
    # project.kqr_ids vergleichen kann. Ohne Project-Datensatz (Testfixtures)
    # bleibt die Liste leer -- ein solcher Datensatz wird später nicht zur
    # Wiederverwendung vorgeschlagen, weil seine Vergleichsmenge unbekannt ist.
    try:
        context_kqr_ids = sorted(project_service.get_project(project_id).kqr_ids)
    except KeyError:
        context_kqr_ids = []

    decision = DisjointConceptDecision(
        concept_id=concept_id,
        concept_label=concept_label,
        kqr_id=kqr_id,
        strategy=strategy,
        anchor_class=anchor_class,
        context_loss_note=context_loss_note,
        context_kqr_ids=context_kqr_ids,
        justification=justification,
        author=author,
    )

    decisions = _get_decisions(project_id)
    decisions[:] = [d for d in decisions if d.concept_id != concept_id]
    decisions.append(decision)
    _save_decisions(project_id)
    return decision


def get_decision(concept_id: str, project_id: str = "default") -> DisjointConceptDecision | None:
    """None wenn noch keine Entscheidung für concept_id vorliegt."""
    for decision in _get_decisions(project_id):
        if decision.concept_id == concept_id:
            return decision
    return None


def list_decisions(project_id: str = "default") -> list[DisjointConceptDecision]:
    return list(_get_decisions(project_id))


def suggest_reusable_decision(
    concept_id: str, current_kqr_ids: list[str]
) -> DisjointConceptDecision | None:
    """Durchsucht alle Projekte nach einer bestehenden Entscheidung fuer
    concept_id, deren context_kqr_ids eine Obermenge (oder Gleichmenge)
    von current_kqr_ids ist -- die Entscheidung wurde also gegen
    mindestens dieselbe Vergleichsmenge getroffen wie die aktuell
    vorliegende, damit bleibt sie gueltig. Entscheidungen mit leerem
    context_kqr_ids (nicht migrierte Altdatensaetze, vgl. Schritt 4)
    werden ausdruecklich NICHT vorgeschlagen, da ihre urspruengliche
    Vergleichsmenge unbekannt ist. Bei mehreren passenden Kandidaten wird
    die zuletzt erstellte (created_at) zurueckgegeben. None wenn nichts
    passt. Reine Lesefunktion, veraendert keine Daten, ruft nicht
    decide() auf -- die tatsaechliche Uebernahme (inkl. neuer
    Begruendung und Autor fuer den neuen Datensatz) bleibt bewusst ein
    expliziter, separater Aufruf von decide() durch die aufrufende
    Stelle, damit das Accountability-Prinzip (Pflichtfeld justification)
    nicht umgangen wird."""
    current = set(current_kqr_ids)
    projects_dir = project_service._projects_dir()
    if not projects_dir.exists():
        return None

    candidates: list[DisjointConceptDecision] = []
    for entry in sorted(projects_dir.iterdir()):
        if not entry.is_dir():
            continue
        path = entry / "disjoint_decisions.json"
        if not path.exists():
            continue
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for record in records:
            if record.get("concept_id") != concept_id:
                continue
            context = record.get("context_kqr_ids") or []
            if not context:
                continue
            if current <= set(context):
                candidates.append(DisjointConceptDecision(**record))

    if not candidates:
        return None
    return max(candidates, key=lambda d: d.created_at)


def get_summary(project_id: str = "default") -> dict:
    """Zähler: {total_disjoint, decided, open, by_strategy: {<Strategiewert>: Anzahl}}."""
    total = len(list_disjoint_concepts(project_id=project_id))
    decisions = _get_decisions(project_id)
    decided_ids = {d.concept_id for d in decisions}
    decided = len(decided_ids)
    return {
        "total_disjoint": total,
        "decided": decided,
        "open": max(total - decided, 0),
        # Schlüssel sind die Strategiewerte selbst, damit Backend und
        # Oberfläche nicht zwei Vokabulare pflegen müssen.
        "by_strategy": {
            strategy.value: sum(1 for d in decisions if d.strategy == strategy)
            for strategy in DisjointStrategy
        },
    }


def get_summary_for_pair(kqr_a_id: str, kqr_b_id: str, project_id: str = "default") -> dict:
    """
    Wie get_summary(), aber bezogen auf ein einzelnes KQR-Paar (Grundmenge
    aus list_disjoint_concepts_for_pair() statt der projektweiten
    list_disjoint_concepts()). Rückgabeformat identisch zu get_summary():
    {total_disjoint, decided, open, by_strategy: {...}}.

    Modellierungsentscheidung: Die Entscheidung (DisjointConceptDecision)
    selbst ist NICHT paarbezogen, sondern bleibt global pro concept_id --
    ein Konzept bekommt genau eine Integrationsstrategie für die
    harmonisierte Gesamtontologie, unabhängig davon, in wie vielen Paaren
    es als disjunkt auftaucht (betrifft v. a. Hub-Konzepte, die in
    mehreren Paaren vorkommen können). Wurde ein Konzept bereits in einem
    anderen Paar-Kontext entschieden, gilt es daher auch hier als
    "entschieden" (Transparency-Prinzip: dieselbe Entscheidung soll überall
    sichtbar sein, wo das Konzept als disjunkt geführt wird, statt lokal
    pro Paar erneut entschieden werden zu müssen).
    """
    concepts = list_disjoint_concepts_for_pair(kqr_a_id, kqr_b_id, project_id=project_id)
    concept_uris = {c.uri for c in concepts}
    decisions = [d for d in _get_decisions(project_id) if d.concept_id in concept_uris]
    total = len(concepts)
    decided = len(decisions)
    return {
        "total_disjoint": total,
        "decided": decided,
        "open": max(total - decided, 0),
        # Schlüssel sind die Strategiewerte selbst, damit Backend und
        # Oberfläche nicht zwei Vokabulare pflegen müssen.
        "by_strategy": {
            strategy.value: sum(1 for d in decisions if d.strategy == strategy)
            for strategy in DisjointStrategy
        },
    }


def count_decisions_for_pair(kqr_a_id: str, kqr_b_id: str, project_id: str = "default") -> int:
    """
    Anzahl bereits getroffener Integrationsentscheidungen, deren Konzept aus
    kqr_a_id oder kqr_b_id stammt. Dient als Hinweis fuer
    classification_service.reset_pair(): ein Paar-Reset laesst diese
    Entscheidungen bewusst unveraendert (DisjointConceptDecision ist
    konzept-, nicht paarbezogen, vgl. get_summary_for_pair), meldet aber
    zurueck, wie viele davon betroffen sein koennten, damit eine Kuratorin
    sie nach der Neu-Klassifikation gezielt pruefen kann.
    """
    pair_kqr_ids = {kqr_a_id, kqr_b_id}
    return sum(1 for d in _get_decisions(project_id) if d.kqr_id in pair_kqr_ids)


def reset(project_id: str = "default") -> None:
    """Leert den In-Memory-Store eines Projekts (primär für Tests)."""
    _decisions.pop(project_id, None)
