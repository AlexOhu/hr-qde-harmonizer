"""
Orchestrierung für Funktionsgruppe 3 (Ergebnisliste, manuelle Entscheidungen)
und Funktionsgruppe 4 (SSSOM-Vorschau).

Store für Mapping-Objekte sowie die vollständigen ClassificationResult-Objekte.
Seit v0.2 wird JEDES klassifizierte Kandidatenpaar als Mapping mit stabiler
mapping_id persistiert, auch RELATED-Ergebnisse und Paare ohne
LLM-Mehrheitsentscheid: diese tragen ReviewStatus.OPEN, erscheinen in
GET /mappings/ und sind über PUT /mappings/{mapping_id}/review entscheidbar.
Vorher existierten sie nur als flüchtige Objekte im Prüfbericht, waren also
weder adressierbar noch entscheidbar.

Persistenz-Design (analog kqr_service._save_registry): beide Listen werden
als JSON unter data/projects/{project_id}/mappings.json bzw.
classification_results.json gehalten (ADR-13), bei jedem add_* für
das jeweilige Projekt vollständig neu geschrieben. Grund: ein
klassifizierender Threading-Backgroundjob läuft im selben uvicorn-
Worker-Prozess wie die API (vgl. classification_service) und würde bei
einem --reload-Neustart sonst bereits bezahlte LLM-Klassifikationen
stillschweigend verlieren.

In-Memory-Caches sind nach project_id kodiert (ADR-13), damit mehrere
Projekte im selben Prozess sich nicht vermischen.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.config import settings
from app.models.schemas import (
    ClassificationResult,
    DisjointStrategy,
    Mapping,
    MappingJustification,
    MappingPredicate,
    ReviewStatus,
    SSSOMRecord,
)
from app.services import project_service


def _mappings_path(project_id: str) -> Path:
    return project_service.get_project_data_dir(project_id) / "mappings.json"


def _classification_results_path(project_id: str) -> Path:
    return project_service.get_project_data_dir(project_id) / "classification_results.json"


def _load_mappings(project_id: str) -> list[Mapping]:
    path = _mappings_path(project_id)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Mapping(**item) for item in data]


def _save_mappings(project_id: str) -> None:
    path = _mappings_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [m.model_dump(mode="json") for m in _get_mappings(project_id)], indent=2, ensure_ascii=False
        ),
        encoding="utf-8",
    )


def _load_classification_results(project_id: str) -> list[ClassificationResult]:
    path = _classification_results_path(project_id)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ClassificationResult(**item) for item in data]


def _save_classification_results(project_id: str) -> None:
    path = _classification_results_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [r.model_dump(mode="json") for r in _get_classification_results(project_id)],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


_mappings: dict[str, list[Mapping]] = {}
_classification_results: dict[str, list[ClassificationResult]] = {}


def _get_mappings(project_id: str) -> list[Mapping]:
    if project_id not in _mappings:
        _mappings[project_id] = _load_mappings(project_id)
    return _mappings[project_id]


def _get_classification_results(project_id: str) -> list[ClassificationResult]:
    if project_id not in _classification_results:
        _classification_results[project_id] = _load_classification_results(project_id)
    return _classification_results[project_id]


def reload(project_id: str = "default") -> None:
    """Lädt beide Listen eines Projekts neu von der Platte (primär für Tests
    nützlich, analog kqr_service.reload_registry())."""
    _mappings[project_id] = _load_mappings(project_id)
    _classification_results[project_id] = _load_classification_results(project_id)


def reset(project_id: str = "default") -> None:
    """Leert den In-Memory-Store eines Projekts (primär für Tests nützlich).
    Schreibt bewusst nicht auf die Platte -- Tests zeigen über
    isolated_services auf einen tmp_path, echte data/-Dateien bleiben
    unberührt."""
    _mappings.pop(project_id, None)
    _classification_results.pop(project_id, None)


def add_mappings(mappings: list[Mapping], project_id: str = "default") -> None:
    project_service.ensure_writable(project_id)
    _get_mappings(project_id).extend(mappings)
    _save_mappings(project_id)


def add_classification_results(results: list[ClassificationResult], project_id: str = "default") -> None:
    project_service.ensure_writable(project_id)
    _get_classification_results(project_id).extend(results)
    _save_classification_results(project_id)


def get_classified_pairs(project_id: str = "default") -> set[tuple[str, str]]:
    """(concept_a, concept_b)-Paare, für die bereits ein ClassificationResult
    vorliegt. Grundlage für den Kosten-/Resume-Schutz in
    classification_service._run_job: verhindert, dass nach einem
    Prozess-Neustart (z. B. uvicorn --reload) bereits bezahlte
    LLM-Klassifikationen erneut angestoßen werden."""
    return {(r.pair.concept_a, r.pair.concept_b) for r in _get_classification_results(project_id)}


def list_mappings_for_pair(
    kqr_a_id: str, kqr_b_id: str, project_id: str = "default"
) -> list[Mapping]:
    """
    Mappings, die exakt zu diesem KQR-Paar gehören (Subjekt- und
    Objektseite entsprechen zusammen genau {kqr_a_id, kqr_b_id},
    reihenfolgeunabhängig). Gemeinsame Grundlage für
    project_service.get_pipeline_status() (pair_mappings) und
    disjoint_service.list_disjoint_concepts_for_pair(), damit dieser
    Set-Vergleich nicht mehrfach dupliziert wird.
    """
    pair_ids = {kqr_a_id, kqr_b_id}
    return [
        m for m in _get_mappings(project_id) if {m.subject_kqr_id, m.object_kqr_id} == pair_ids
    ]


def list_mappings(
    only_manual_review: bool = False,
    min_confidence: float | None = None,
    kqr_id: str | None = None,
    kqr_a_id: str | None = None,
    kqr_b_id: str | None = None,
    review_status: ReviewStatus | None = None,
    project_id: str = "default",
) -> list[Mapping]:
    """
    Liefert die Ergebnisliste (Funktionsgruppe 3), inklusive der noch offenen
    RELATED/UNRESOLVED-Paare (ReviewStatus.OPEN). Diese werden seit v0.2
    mitgeliefert statt ausgeblendet: ein Reviewer soll sehen, was noch auf eine
    Entscheidung wartet, und es an Ort und Stelle entscheiden können.

    only_manual_review grenzt auf Einträge ein, die eine menschliche
    Entscheidung brauchen, also offener Review-Status ODER Konfidenz unterhalb
    der Schwelle (Mixed-Initiative-Prinzip). review_status grenzt zusätzlich
    auf genau einen Entscheidungsstand ein.

    kqr_id grenzt auf Mappings ein, an denen das gegebene KQR auf Subjekt-
    oder Objektseite beteiligt ist (Transparency-Prinzip: Herkunft der
    Kandidatenpaare nachvollziehbar machen). Sind kqr_a_id UND kqr_b_id
    gesetzt, wird stattdessen die paarbezogene Grundmenge aus
    list_mappings_for_pair() verwendet; kqr_id wird in diesem Fall ignoriert.
    """
    if kqr_a_id is not None and kqr_b_id is not None:
        items = list_mappings_for_pair(kqr_a_id, kqr_b_id, project_id=project_id)
    else:
        items = list(_get_mappings(project_id))
        if kqr_id is not None:
            items = [m for m in items if kqr_id in (m.subject_kqr_id, m.object_kqr_id)]
    if min_confidence is not None:
        items = [m for m in items if m.mapping_confidence >= min_confidence]
    if review_status is not None:
        items = [m for m in items if m.review_status == review_status]
    if only_manual_review:
        items = [m for m in items if needs_review(m)]
    return items


def _concept_uris_for_kqrs(kqr_a_id: str, kqr_b_id: str) -> set[str]:
    """URIs aller Konzepte der beiden angegebenen KQR. Lokaler Import von
    kqr_service (nur fuer die paarbezogene Reset-Operation benoetigt, keine
    generelle Kopplung von mapping_service an die KQR-Registry). Ein KQR
    ohne (mehr) auflösbare Konzepte liefert schlicht keine URIs -- ein
    Reset soll nicht daran scheitern, dass ein KQR zwischenzeitlich
    abgemeldet oder noch nicht formalisiert wurde."""
    from app.services import kqr_service

    uris: set[str] = set()
    for kqr_id in (kqr_a_id, kqr_b_id):
        try:
            uris.update(concept.uri for concept in kqr_service.get_concepts(kqr_id))
        except (KeyError, ValueError):
            continue
    return uris


def delete_mappings_for_pair(
    kqr_a_id: str, kqr_b_id: str, project_id: str = "default"
) -> list[Mapping]:
    """
    Entfernt alle Mappings, die exakt zu diesem KQR-Paar gehoeren (Grundlage
    fuer classification_service.reset_pair). Gibt die entfernten Mappings
    zurueck, u. a. damit der Aufrufer die betroffene Konzeptmenge kennt.

    Ergaenzt delete_classification_results_for_pair(): dieses hier entfernt
    nur die daraus abgeleiteten Mapping-Objekte, nicht die zugrunde
    liegenden Klassifikationen -- ohne Letzteres wuerde
    get_classified_pairs() das Paar beim naechsten Lauf weiterhin
    ueberspringen, ein geloeschtes Mapping also stillschweigend wieder
    auftauchen, sobald der naechste Job startet.
    """
    project_service.ensure_writable(project_id)
    removed = list_mappings_for_pair(kqr_a_id, kqr_b_id, project_id=project_id)
    removed_ids = {m.mapping_id for m in removed}
    mappings = _get_mappings(project_id)
    mappings[:] = [m for m in mappings if m.mapping_id not in removed_ids]
    _save_mappings(project_id)
    return removed


def delete_classification_results_for_pair(
    kqr_a_id: str, kqr_b_id: str, project_id: str = "default"
) -> int:
    """
    Entfernt alle ClassificationResult-Eintraege, deren beide Konzepte aus
    diesem KQR-Paar stammen. Gibt die Anzahl der entfernten Eintraege
    zurueck.

    Strukturelle Shortcut-Mappings (find_structural_shortcuts) erzeugen nie
    ein ClassificationResult -- fuer sie besteht hier nichts zu loeschen,
    delete_mappings_for_pair() entfernt trotzdem das daraus abgeleitete
    Mapping-Objekt.
    """
    project_service.ensure_writable(project_id)
    uris = _concept_uris_for_kqrs(kqr_a_id, kqr_b_id)
    results = _get_classification_results(project_id)
    before = len(results)
    results[:] = [
        r for r in results if not (r.pair.concept_a in uris and r.pair.concept_b in uris)
    ]
    _save_classification_results(project_id)
    return before - len(results)


def needs_review(mapping: Mapping) -> bool:
    """Ein Eintrag verlangt eine menschliche Entscheidung, wenn er entweder
    noch offen ist (RELATED/UNRESOLVED) oder die Konfidenz-Schwelle nicht
    erreicht. Gemeinsame Definition für list_mappings(only_manual_review),
    get_open_review_summary() und project_service.get_pipeline_status(),
    damit die Zähler in Liste, Gatekeeping und Projektstatus übereinstimmen."""
    if mapping.review_status == ReviewStatus.OPEN:
        return True
    return (
        mapping.mapping_source != "manual"
        and mapping.mapping_confidence < settings.mapping_confidence_threshold
    )


def get_mapping(mapping_id: str, project_id: str = "default") -> Mapping:
    for mapping in _get_mappings(project_id):
        if mapping.mapping_id == mapping_id:
            return mapping
    raise KeyError(f"Mapping '{mapping_id}' nicht gefunden.")


def _replace_mapping(mapping_id: str, updated: Mapping, project_id: str) -> Mapping:
    mappings = _get_mappings(project_id)
    for index, mapping in enumerate(mappings):
        if mapping.mapping_id == mapping_id:
            mappings[index] = updated
            _save_mappings(project_id)
            return updated
    raise KeyError(f"Mapping '{mapping_id}' nicht gefunden.")


def update_mapping(
    mapping_id: str, predicate: str, justification: str, author: str, project_id: str = "default"
) -> Mapping:
    """
    Manuelle Mapping-Entscheidung korrigieren/bestätigen (FA3), inkl.
    verpflichtender Provenance-Angaben (FA4: Begründung, Zeitstempel, Autor).
    Eine manuelle Entscheidung überschreibt niemals stillschweigend die
    ursprüngliche mapping_confidence des LLM-Laufs im Sinne der
    Nachvollziehbarkeit. Sie wird auf 1.0 gesetzt, da eine explizite
    menschliche Bestätigung/Korrektur per Definition maximale Konfidenz hat.

    predicate ist ein MappingPredicate-CURIE. Alle fünf sind wählbar; ein
    korrigiertes skos:relatedMatch ist eine bewusste Reviewer-Entscheidung
    und schließt den Review trotzdem ab (ReviewStatus.CONJUNCT), es zählt
    über _K_PREDICATES nur nicht zur konjunkten Menge K.

    Seit v0.2 setzt der Vorgang außerdem mapping_justification auf
    semapv:MappingReview: das Ergebnis ist nach der Entscheidung ein
    verbindliches Mapping, kein algorithmischer Vorschlag mehr.
    """
    project_service.ensure_writable(project_id)
    predicate_value = MappingPredicate(predicate)
    mapping = get_mapping(mapping_id, project_id=project_id)
    return _replace_mapping(
        mapping_id,
        mapping.model_copy(
            update={
                "predicate_id": predicate_value,
                "justification": justification,
                "author": author,
                "mapping_source": "manual",
                "mapping_confidence": 1.0,
                "mapping_justification": MappingJustification.MAPPING_REVIEW,
                "review_status": ReviewStatus.CONJUNCT,
            }
        ),
        project_id,
    )


def review_mapping(
    mapping_id: str,
    decision: str,
    predicate: MappingPredicate | None = None,
    confidence: float = 1.0,
    strategy: DisjointStrategy | None = None,
    context_loss_note: str | None = None,
    justification: str | None = None,
    author: str | None = None,
    project_id: str = "default",
) -> Mapping:
    """
    Entscheidet ein offenes Kandidatenpaar (FZ3.2-Weiche konjunkt/disjunkt).

    decision="conjunct": Das Paar wird mit dem gewählten SKOS-Prädikat
    finalisiert, mapping_justification=semapv:MappingReview, Konfidenz
    standardmäßig 1.0. Eine menschliche Entscheidung ist nicht unsicherer
    als ein Regelmatch.

    decision="disjunct": Das Paar ist kein Mapping. Stattdessen bekommt das
    Subjektkonzept (die Satellitenseite des Paares) eine Integrationsstrategie
    und damit den Typ harm:HarmonisedConcept im Ontologie-Export.

    Sonderfall MAP_TO_NEAREST: Das Konzept wird an das nächstgelegene
    Hub-Konzept gehängt, und genau dieses Hub-Konzept ist die Objektseite des
    gerade geprüften Paares. Das geprüfte Mapping wird deshalb zum
    skos:relatedMatch mit mapping_justification=semapv:MappingReview
    umgewidmet, statt ein zweites Mapping-Objekt für dasselbe Konzeptpaar
    anzulegen. Ein zweites Objekt würde den Nenner der Coverage-Quote
    verfälschen. Der Pflichtvermerk zum Kontextverlust hängt an beiden
    Objekten, am Mapping und an der Integrationsentscheidung.

    Fehlerhafte Eingaben werfen ValueError; die Route bildet das auf HTTP 400 ab.
    """
    project_service.ensure_writable(project_id)
    mapping = get_mapping(mapping_id, project_id=project_id)

    if decision == "conjunct":
        if predicate is None:
            raise ValueError("predicate ist im Konjunkt-Zweig ein Pflichtfeld.")
        return _replace_mapping(
            mapping_id,
            mapping.model_copy(
                update={
                    "predicate_id": predicate,
                    "mapping_confidence": confidence,
                    "mapping_justification": MappingJustification.MAPPING_REVIEW,
                    "mapping_source": "manual",
                    "review_status": ReviewStatus.CONJUNCT,
                    "author": author or mapping.author,
                    "justification": justification or mapping.justification,
                }
            ),
            project_id,
        )

    if decision != "disjunct":
        raise ValueError(f"Unbekannte decision '{decision}' (erlaubt: conjunct, disjunct).")

    if strategy is None:
        raise ValueError("strategy ist im Disjunkt-Zweig ein Pflichtfeld.")
    if strategy == DisjointStrategy.MAP_TO_NEAREST and not (context_loss_note or "").strip():
        raise ValueError(
            "context_loss_note ist bei strategy='map_to_nearest' ein Pflichtfeld: "
            "der Kontextverlust beim Anhängen an das nächstgelegene Konzept ist zu vermerken."
        )

    # Lokaler Import: disjoint_service importiert mapping_service auf
    # Modulebene, ein Modulimport in Gegenrichtung wäre zirkulär.
    from app.services import disjoint_service

    decision_note = (
        justification
        or mapping.justification
        or f"Im Review als disjunkt entschieden ({strategy.value})."
    )
    disjoint_service.decide(
        concept_id=mapping.subject_id,
        strategy=strategy,
        justification=decision_note,
        author=author or mapping.author or "unbekannt",
        context_loss_note=context_loss_note,
        fallback_label=mapping.subject_label,
        fallback_kqr_id=mapping.subject_kqr_id,
        project_id=project_id,
    )

    is_map_to_nearest = strategy == DisjointStrategy.MAP_TO_NEAREST
    return _replace_mapping(
        mapping_id,
        mapping.model_copy(
            update={
                "predicate_id": MappingPredicate.RELATED_MATCH,
                "mapping_confidence": (
                    confidence if is_map_to_nearest else mapping.mapping_confidence
                ),
                "mapping_justification": MappingJustification.MAPPING_REVIEW,
                "mapping_source": "manual",
                "review_status": (
                    ReviewStatus.CONJUNCT if is_map_to_nearest else ReviewStatus.DISJUNCT
                ),
                "author": author or mapping.author,
                "justification": decision_note,
                "context_loss_note": context_loss_note,
            }
        ),
        project_id,
    )


def sssom_preview(limit: int = 5, project_id: str = "default") -> dict:
    """Strukturierte Vorschau der SSSOM-Metadaten (Funktionsgruppe 4, Transparency).

    Zeigt nur entschiedene Mappings (ReviewStatus.CONJUNCT): die Vorschau soll
    dem tatsächlichen Inhalt der Exportdatei entsprechen, und write_sssom_tsv()
    schreibt offene sowie disjunkt entschiedene Paare nicht mit.
    """
    exportable = [m for m in _get_mappings(project_id) if m.review_status == ReviewStatus.CONJUNCT]
    records = [SSSOMRecord.from_mapping(m) for m in exportable[:limit]]
    return {
        "total_count": len(exportable),
        "fields": list(SSSOMRecord.model_fields.keys()),
        "sample": [r.model_dump(mode="json") for r in records],
    }


def get_unresolved_mappings(project_id: str = "default") -> list[Mapping]:
    """
    Die noch offenen Fälle ohne LLM-Mehrheitsentscheid (predicate_id=None)
    für den Prüfbericht (export_audit_report).

    Seit v0.2 sind das persistierte Mapping-Objekte mit stabiler mapping_id,
    keine synthetisch aus ClassificationResult-Objekten zusammengebauten
    Kopien mehr. Der Prüfbericht kann deshalb die mapping_id nennen, unter der
    ein Fall per PUT /mappings/{mapping_id}/review entscheidbar ist.
    """
    return [
        m
        for m in _get_mappings(project_id)
        if m.review_status == ReviewStatus.OPEN and m.predicate_id is None
    ]


def get_related_concept_uris(project_id: str = "default") -> set[str]:
    """URIs aller Konzepte, die auf Subjekt- oder Objektseite eines noch
    offenen RELATED-Ergebnisses vorkommen. Grundlage für
    disjoint_service.suggest_strategy(): ein RELATED-Ergebnis impliziert
    semantische Nähe ohne Äquivalenz, also ATTACH_TO_SKELETON statt OWN_CLASS."""
    uris: set[str] = set()
    for mapping in _get_mappings(project_id):
        if (
            mapping.review_status == ReviewStatus.OPEN
            and mapping.predicate_id == MappingPredicate.RELATED_MATCH
        ):
            uris.add(mapping.subject_id)
            uris.add(mapping.object_id)
    return uris


def get_open_review_summary(project_id: str = "default") -> dict:
    """
    Offene Fälle für das Gatekeeping vor dem Export (Funktionsgruppe 5,
    Accountability-Prinzip): noch nicht entschiedene Paare (RELATED oder ohne
    LLM-Mehrheitsentscheid) sowie Mappings unterhalb der Confidence-Schwelle.

    no_consensus_pairs = offene Paare mit predicate_id=None (majority_vote
    fand keine Mehrheit). related_pairs = offene Paare mit skos:relatedMatch.
    """
    mappings = _get_mappings(project_id)
    open_mappings = [m for m in mappings if m.review_status == ReviewStatus.OPEN]
    no_consensus = sum(1 for m in open_mappings if m.predicate_id is None)
    related = sum(1 for m in open_mappings if m.predicate_id == MappingPredicate.RELATED_MATCH)
    low_confidence = sum(
        1
        for m in mappings
        if m.review_status != ReviewStatus.OPEN
        and m.mapping_source != "manual"
        and m.mapping_confidence < settings.mapping_confidence_threshold
    )
    return {
        "no_consensus_pairs": no_consensus,
        "related_pairs": related,
        "low_confidence_mappings": low_confidence,
        "total_open": no_consensus + related + low_confidence,
    }


def get_coverage_summary(project_id: str = "default") -> dict:
    """
    Coverage-Bilanz für /export/summary und das Begleitprotokoll.

    Der Nenner ist K vereinigt C_conf, also jedes persistierte Kandidatenpaar,
    ausdrücklich einschließlich der Paare mit offenem Review-Status. Fielen
    offene Paare aus dem Nenner, meldete ein Projekt mit sieben entschiedenen
    und drei offenen Paaren eine Quote von 1,0 statt 0,7 und behauptete damit
    eine Vollständigkeit, die es nicht gibt.

    Der Zähler enthält nur tatsächlich entschiedene Einträge (ReviewStatus
    CONJUNCT oder DISJUNCT). open_review_count ist die Differenz, redundant
    ausgewiesen, damit die Oberfläche "wie viel ist offen" nicht erst aus zwei
    anderen Zahlen berechnen muss.
    """
    mappings = _get_mappings(project_id)
    total = len(mappings)
    resolved = sum(1 for m in mappings if m.review_status != ReviewStatus.OPEN)
    return {
        "coverage_resolved": resolved,
        "coverage_total": total,
        "coverage_ratio": (resolved / total) if total else 0.0,
        "open_review_count": total - resolved,
    }
