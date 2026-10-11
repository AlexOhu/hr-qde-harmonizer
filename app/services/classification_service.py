"""
Orchestrierung für Funktionsgruppe 2 (Klassifikationsprozess steuern).

Kombiniert Schritt 2 (regelbasierter Struktur-Vorfilter + FAISS-ANN-Suche)
und Schritt 3 (LLM-Klassifikation mit Mehrheitsentscheid) zu einem
Hintergrundjob, dessen Fortschritt über get_job_progress() abgefragt werden
kann (adressiert die "Gulf of Evaluation", Abschnitt 3.8.3). Läuft als
Python-Thread statt FastAPI BackgroundTasks, damit dieses Modul nicht an
den Request-Lifecycle gebunden ist und unabhängig testbar bleibt.

Kosten-/Absturzschutz: jedes klassifizierte Paar wird sofort über
mapping_service persistiert (nicht erst am Schleifenende), und vor jedem
LLM-Aufruf wird geprüft, ob für das Paar bereits ein ClassificationResult
vorliegt (mapping_service.get_classified_pairs()). Ein erneuter Aufruf von
start_classification_job() für dasselbe KQR-Paar -- etwa nach einem
uvicorn---reload-Neustart, der _jobs geleert hat -- klassifiziert dadurch
nur noch die verbliebenen Paare, statt bereits bezahlte LLM-Läufe zu
wiederholen. Zusätzlich ist ein laufender Job über pause_job()/resume_job()
gezielt unterbrechbar (threading.Event, vor jedem Paar geprüft).

Jobs sind je Projekt partitioniert (ADR-13): _jobs bildet
project_id -> job_id -> Job-Dict ab, persistiert unter
data/projects/{project_id}/classification_jobs.json.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.graph.neo4j_client import get_driver
from app.models.schemas import KQR, Mapping, MappingJustification, PairResetEvent
from app.pipeline.step3_classification.llm_provider import get_providers_from_config, is_any_provider_configured
from app.pipeline.step2_embedding_prefilter.prefilter import (
    child_level_concept_uris,
    derive_child_level_mappings,
    derive_container_mappings,
    detect_container_concepts,
    exclude_occupation_embeddings,
    filter_by_scope,
    find_candidate_pairs,
    find_structural_shortcuts,
    partition_by_role,
)
from app.pipeline.step3_classification.classify import classify_pair
from app.pipeline.step4_export.sssom_writer import classification_results_to_mappings
from app.services import kqr_service, mapping_service, project_service

logger = logging.getLogger(__name__)

_jobs: dict[str, dict[str, dict]] = {}  # project_id -> job_id -> job
_pause_events: dict[str, dict[str, threading.Event]] = {}  # project_id -> job_id -> Event


def _now_iso() -> str:
    """UTC-Zeitstempel im ISO-8601-Format. Job-Zeitstempel machen die
    Run-Historie eines KQR-Paares in der UI sortier- und lesbar (mehrere
    Laeufe pro Paar sind moeglich, vgl. list_jobs)."""
    return datetime.now(timezone.utc).isoformat()


def _jobs_path(project_id: str) -> Path:
    return project_service.get_project_data_dir(project_id) / "classification_jobs.json"


def _load_jobs(project_id: str) -> dict[str, dict]:
    """Lädt persistierte Jobs eines Projekts von der Platte. Ein Job mit
    status='running' kann zu diesem Zeitpunkt unmöglich einen laufenden
    Thread haben -- Threads überleben keinen Prozess-Neustart --, würde
    sonst aber für immer als 'running' erscheinen (Transparency-Prinzip:
    keine irreführenden Dauerzustände in der UI). Er wird daher beim Laden
    auf 'interrupted' gesetzt; ein erneuter start_classification_job()-
    Aufruf für dasselbe KQR-Paar setzt ihn dank get_classified_pairs()
    kostenfrei fort."""
    path = _jobs_path(project_id)
    if not path.exists():
        return {}
    jobs: dict[str, dict] = json.loads(path.read_text(encoding="utf-8"))
    for job in jobs.values():
        if job["status"] == "running":
            job["status"] = "interrupted"
    return jobs


def _save_jobs(project_id: str) -> None:
    path = _jobs_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jobs.get(project_id, {}), indent=2, ensure_ascii=False), encoding="utf-8")


def _get_project_jobs(project_id: str) -> dict[str, dict]:
    if project_id not in _jobs:
        loaded = _load_jobs(project_id)
        _jobs[project_id] = loaded
        if loaded:
            _save_jobs(project_id)  # persistiert eine ggf. vorgenommene running->interrupted-Korrektur
    return _jobs[project_id]


def _reset_events_path(project_id: str) -> Path:
    return project_service.get_project_data_dir(project_id) / "pair_reset_events.json"


def _load_reset_events(project_id: str) -> list[dict]:
    path = _reset_events_path(project_id)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _append_reset_event(event: PairResetEvent, project_id: str) -> None:
    path = _reset_events_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    events = _load_reset_events(project_id)
    events.append(event.model_dump(mode="json"))
    path.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")


def list_reset_events(project_id: str = "default") -> list[dict]:
    """Alle protokollierten Paar-Resets eines Projekts, neueste zuerst
    (Transparency-Prinzip: sichtbar machen, DASS und WARUM ein Paar
    zurueckgesetzt wurde, statt es einfach wieder als 'not_started'
    erscheinen zu lassen)."""
    return sorted(_load_reset_events(project_id), key=lambda e: e["created_at"], reverse=True)


def reset_pair(
    kqr_a_id: str, kqr_b_id: str, justification: str, author: str, project_id: str = "default"
) -> dict:
    """
    Setzt ein KQR-Paar vollstaendig zurueck: entfernt alle Mappings UND die
    zugrunde liegenden ClassificationResult-Eintraege dieses Paares, damit
    ein erneuter start_classification_job() das Paar komplett neu
    klassifiziert, statt es ueber get_classified_pairs() zu ueberspringen
    (der normale Kostenschutz fuer Resume-Laeufe, hier bewusst umgangen).

    Absichtlich NICHT angetastet:
    - Die Job-Historie (classification_jobs.json): ein neuer Lauf erhaelt
      eine neue job_id, alte Laeufe bleiben als Run-Historie sichtbar (vgl.
      runCount in status.ts). Das dokumentiert den Reset, statt ihn zu
      verschleiern.
    - Disjoint-Entscheidungen: DisjointConceptDecision ist konzept-, nicht
      paarbezogen (vgl. disjoint_service.get_summary_for_pair). Eine bereits
      begruendete menschliche Entscheidung soll nicht durch einen
      Seiteneffekt verschwinden; count_decisions_for_pair() meldet nur, wie
      viele davon betroffen sein koennten.

    Der Reset ist selbst eine protokollpflichtige Kuratoren-Entscheidung
    (Accountability-Prinzip): justification und author sind Pflichtfelder,
    das Ereignis wird in pair_reset_events.json festgehalten.
    """
    project_service.ensure_writable(project_id)
    if not justification.strip():
        raise ValueError("justification ist beim Paar-Reset ein Pflichtfeld.")
    if not author.strip():
        raise ValueError("author ist beim Paar-Reset ein Pflichtfeld.")

    removed_mappings = mapping_service.delete_mappings_for_pair(
        kqr_a_id, kqr_b_id, project_id=project_id
    )
    removed_results = mapping_service.delete_classification_results_for_pair(
        kqr_a_id, kqr_b_id, project_id=project_id
    )

    # Lokaler Import: disjoint_service importiert seinerseits mapping_service
    # auf Modulebene, ein Modulimport in Gegenrichtung waere zirkulaer
    # (gleiches Muster wie mapping_service.review_mapping).
    from app.services import disjoint_service

    affected_decisions = disjoint_service.count_decisions_for_pair(
        kqr_a_id, kqr_b_id, project_id=project_id
    )

    event = PairResetEvent(
        kqr_a_id=kqr_a_id,
        kqr_b_id=kqr_b_id,
        removed_mappings=len(removed_mappings),
        removed_classification_results=removed_results,
        affected_disjoint_decisions=affected_decisions,
        justification=justification,
        author=author,
    )
    _append_reset_event(event, project_id)

    return {
        "removed_mappings": len(removed_mappings),
        "removed_classification_results": removed_results,
        "affected_disjoint_decisions": affected_decisions,
    }


def _build_few_shot_text(shortcut_mappings: list[Mapping], limit: int = 3) -> str:
    """Nutzt strukturell abgeleitete Shortcut-Mappings als Crosswalk-Few-Shot-
    Anker für den Klassifikationsprompt (Abschnitt "Crosswalks als
    Kalibrierungsanker")."""
    if not shortcut_mappings:
        return "(keine Crosswalk-Beispiele verfügbar)"
    lines = [
        f'- "{m.subject_label}" {m.predicate_id.value if m.predicate_id else "?"} "{m.object_label}"'
        for m in shortcut_mappings[:limit]
    ]
    return "\n".join(lines)


def _select_hub_and_satellite(
    kqr_a: KQR, kqr_b: KQR, embeddings_a: dict, embeddings_b: dict
) -> tuple[dict, dict]:
    """
    Setzt die Hub/Satellit-Schichtregel um (Tabelle "kqr_schichten"):
    Nicht-Hub-Konzepte werden gegen den Hub-Rahmen verglichen. Ist keines
    der beiden KQR als Hub markiert, wird KQR B als Ziel-/Objektseite
    behandelt (Tabelle 3.9: object_id ist "in der Regel ESCO").

    Rückgabe: (embeddings der Nicht-Hub-/Quellseite, embeddings der
    Hub-/Zielseite) — passend als (embeddings_a, embeddings_b) für
    find_candidate_pairs, sodass concept_b stets die Hub-/Zielseite ist.
    """
    if kqr_b.is_hub and not kqr_a.is_hub:
        return embeddings_a, embeddings_b
    if kqr_a.is_hub and not kqr_b.is_hub:
        return embeddings_b, embeddings_a
    return embeddings_a, embeddings_b


def _satellite_kqr_id(kqr_a: KQR, kqr_b: KQR, kqr_a_id: str, kqr_b_id: str) -> str:
    """KQR-ID der Satelliten-/Quellseite (analog _select_hub_and_satellite):
    der Nicht-Hub. Ist keiner als Hub markiert, gilt KQR A als Quelle."""
    if kqr_b.is_hub and not kqr_a.is_hub:
        return kqr_a_id
    if kqr_a.is_hub and not kqr_b.is_hub:
        return kqr_b_id
    return kqr_a_id


def _kqr_scope(project_id: str, kqr_id: str) -> str:
    """Scope-Wert fuer ein KQR aus der Projektkonfiguration (Default 'all').
    Ein nicht persistiertes Projekt (Testkonvention) gilt als 'all'."""
    try:
        project = project_service.get_project(project_id)
    except KeyError:
        return "all"
    return (project.kqr_scopes or {}).get(kqr_id, "all")


def _run_job(
    job_id: str, kqr_a_id: str, kqr_b_id: str, pause_event: threading.Event, project_id: str
) -> None:
    job = _jobs[project_id][job_id]
    try:
        kqr_a = kqr_service.get_kqr(kqr_a_id)
        kqr_b = kqr_service.get_kqr(kqr_b_id)

        concepts_a = kqr_service.get_concepts(kqr_a_id)
        concepts_b = kqr_service.get_concepts(kqr_b_id)
        embeddings_a = kqr_service.get_embeddings(kqr_a_id)
        embeddings_b = kqr_service.get_embeddings(kqr_b_id)

        concept_lookup = {
            concept.uri: {
                "pref_label": concept.pref_label,
                "definition": concept.definition or "",
                "kqr_id": concept.kqr_id,
            }
            for concept in [*concepts_a, *concepts_b]
        }

        # Satellit/Hub frueh bestimmen: die Richtungsangabe wird schon beim
        # Struktur-Shortcut fuer den Niveau-Crosswalk gebraucht (nur
        # Satellit -> Hub, s. u.).
        satellite_id = _satellite_kqr_id(kqr_a, kqr_b, kqr_a_id, kqr_b_id)
        hub_id = kqr_b_id if satellite_id == kqr_a_id else kqr_a_id

        # Befund 2026-09-05: find_structural_shortcuts() kennt -- anders als
        # die LLM-Klassifikation (already_classified weiter unten) -- keinen
        # Wiederaufnahme-Schutz. Ohne Filterung würde ein erneuter Aufruf von
        # start_classification_job() fuer dasselbe Paar (Server-Neustart,
        # erneuter Klick) dieselben strukturellen Shortcuts ein zweites Mal
        # anlegen (Duplikate in mappings.json). Bereits vorhandene
        # Shortcut-Mappings fuer dieses Paar werden daher uebersprungen,
        # analog zum already_classified-Schutz fuer LLM-Paare.
        merged_graph = kqr_service.get_graph(kqr_a_id) + kqr_service.get_graph(kqr_b_id)
        existing_shortcut_pairs = {
            (m.subject_id, m.object_id)
            for m in mapping_service.list_mappings_for_pair(kqr_a_id, kqr_b_id, project_id=project_id)
            if m.mapping_justification == MappingJustification.STRUCTURAL_MATCHING
        }
        shortcut_mappings = [
            m
            for m in find_structural_shortcuts(merged_graph, concept_lookup)
            if (m.subject_id, m.object_id) not in existing_shortcut_pairs
        ]

        # Niveau-Crosswalk gegen einen reinen Referenzrahmen (z. B. EQF):
        # skos:exactMatch-Kanten zwischen zwei Niveau-Ankern werden als
        # StructuralMatching-Shortcut behandelt, OHNE
        # data/structural_shortcut_predicates.json zu veraendern (Sign-off
        # 2026-09-06 "EQF als Shortcut-Ziel-KQR im K_levels-Lauf"). Nur
        # Richtung Satellit -> Hub (der Referenzrahmen erzeugt keine eigenen
        # Mappings); Deskriptor-Niveauknoten (child_level_concept_uris) sind
        # ausgenommen -- deren Mapping leitet derive_child_level_mappings()
        # aus dem Eltern-Anker ab.
        #
        # Nur die Satellitenseite: integriert werden die Deskriptoren des
        # einzupflegenden KQR, nicht die Facetten des Referenzrahmens (EQF
        # traegt seine Dimensionsfacetten ebenfalls als Blatt-LevelConcepts
        # unter einem verzweigenden Anker -- die bleiben hier aussen vor).
        _satellite_concept_uris = {
            c.uri for c in (concepts_a if satellite_id == kqr_a_id else concepts_b)
        }
        child_level_uris = child_level_concept_uris(merged_graph) & _satellite_concept_uris
        _existing_pairs = existing_shortcut_pairs | {
            (m.subject_id, m.object_id) for m in shortcut_mappings
        }
        level_crosswalk_mappings = [
            m
            for m in find_structural_shortcuts(
                merged_graph,
                concept_lookup,
                predicates={
                    "http://www.w3.org/2004/02/skos/core#exactMatch": "skos:exactMatch"
                },
                exclude_subjects=child_level_uris,
            )
            if m.subject_kqr_id == satellite_id
            and (m.subject_id, m.object_id) not in _existing_pairs
        ]
        shortcut_mappings = shortcut_mappings + level_crosswalk_mappings

        mapping_service.add_mappings(shortcut_mappings, project_id=project_id)
        shortcut_pairs = existing_shortcut_pairs | {
            (m.subject_id, m.object_id) for m in shortcut_mappings
        }
        shortcut_pairs = shortcut_pairs | {(b, a) for a, b in shortcut_pairs}

        # Deskriptor-Niveauknoten (harm:LevelConcept mit harm:LevelConcept-
        # Elternteil, selbst Blatt -- z. B. die 32 DQR-Dimensionsfacetten)
        # laufen nicht durch ANN/LLM. Ihr Mapping wird direkt aus dem
        # Struktur-Shortcut des Eltern-Ankers abgeleitet: skos:narrowMatch,
        # semapv:LogicalReasoning, review_status CONJUNCT (durch Inferenz
        # determiniert, nie im Review-Queue). Grundlage sind alle
        # Struktur-Shortcuts des Paares (frisch + bereits persistiert), damit
        # die Ableitung auch bei fortgesetzten Laeufen greift; bereits
        # abgeleitete Kinder werden ueber already_derived_subjects
        # uebersprungen (idempotent). child_level_uris ist oben (Niveau-
        # Crosswalk) bereits bestimmt.
        if child_level_uris:
            pair_mappings_so_far = mapping_service.list_mappings_for_pair(
                kqr_a_id, kqr_b_id, project_id=project_id
            )
            pair_shortcut_mappings = [
                m
                for m in pair_mappings_so_far
                if m.mapping_justification == MappingJustification.STRUCTURAL_MATCHING
            ]
            already_derived_children = {
                m.subject_id
                for m in pair_mappings_so_far
                if m.mapping_justification == MappingJustification.LOGICAL_REASONING
            }
            child_level_concepts = [
                c for c in (*concepts_a, *concepts_b) if c.uri in child_level_uris
            ]
            child_level_mappings = derive_child_level_mappings(
                child_level_concepts,
                pair_shortcut_mappings,
                already_derived_subjects=already_derived_children,
            )
            if child_level_mappings:
                mapping_service.add_mappings(child_level_mappings, project_id=project_id)
            job["child_level_mappings_derived"] = job.get(
                "child_level_mappings_derived", 0
            ) + len(child_level_mappings)

        source_embeddings, target_embeddings = _select_hub_and_satellite(
            kqr_a, kqr_b, embeddings_a, embeddings_b
        )
        filtered_target_embeddings = exclude_occupation_embeddings(target_embeddings)
        # ADR-14: Hub-Embeddings auf Skills einschränken, Occupations ausschließen.

        # Projekt-Scope-Konfiguration (Kapitel 4): der Vorfilter teilt die
        # Quellkonzepte VOR dem Embedding in Pipeline- und Skelett-Konzepte,
        # gemaess dem projekt-konfigurierten Scope (Default "all" = alle
        # Konzepte, unabhaengig von der Rolle). Rollentrennung
        # (rdf:type harm:CompetenceConcept/harm:LevelConcept) ist
        # NICHT Teil dieses Scope-Filters -- ein KQR-Paar ohne expliziten
        # strukturellen Shortcut wird vollstaendig rollengleich ausgewertet
        # (partition_by_role weiter unten), s. Befund 2026-09-05.
        # satellite_id / hub_id sind oben bereits bestimmt.
        satellite_graph = kqr_service.get_graph(satellite_id)
        hub_graph = kqr_service.get_graph(hub_id)
        scope = _kqr_scope(project_id, satellite_id)
        pipeline_uris, skeleton_uris = filter_by_scope(
            list(source_embeddings.keys()), satellite_graph, scope
        )
        pipeline_set = set(pipeline_uris)
        source_embeddings = {
            uri: vec for uri, vec in source_embeddings.items() if uri in pipeline_set
        }
        job["scope"] = scope
        job["skeleton_concepts"] = len(skeleton_uris)
        if not source_embeddings:
            job["status"] = "completed"
            job["total_pairs"] = 0
            job["done_pairs"] = 0
            job["skipped_reason"] = "all_concepts_skeleton"
            job["finished_at"] = _now_iso()
            _save_jobs(project_id)
            logger.info(
                "Job '%s' (%s <-> %s): alle Quellkonzepte in der Skelett-Schicht "
                "(scope=%s), kein Pipeline-Lauf.",
                job_id, kqr_a_id, kqr_b_id, scope,
            )
            return

        # Container-Konzepte der Quellseite (Konzepte mit skos:narrower-/
        # skos:broader-Kindern) laufen nicht in die ANN-Suche. Ihr Mapping
        # wird nach der Blatt-Klassifikation aus den Kindmappings abgeleitet
        # (derive_container_mappings), damit ein Container nicht mit denselben
        # Hub-Konzepten wie seine Kinder konkurriert.
        container_uris, container_children = detect_container_concepts(merged_graph)
        source_container_uris = {u for u in container_uris if u in source_embeddings}
        # Container mit eigenem Struktur-Shortcut (direkter Crosswalk-Treffer,
        # z. B. die DQR-Niveau-Anker gegen EQF) sind bereits aufgeloest: wie
        # jeder Container aus dem ANN-Pool nehmen, aber NICHT aus den
        # Kindmappings aggregieren (derive_container_mappings) -- sonst wuerde
        # die skos:broader-Kette der Anker jeden Anker faelschlich aus dem
        # Shortcut des naechsthoeheren Ankers ableiten.
        resolved_shortcut_subjects = {m.subject_id for m in shortcut_mappings} | {
            s for s, _o in existing_shortcut_pairs
        }
        source_container_children = {
            container: children
            for container, children in container_children.items()
            if container in source_container_uris
            and container not in resolved_shortcut_subjects
        }
        source_embeddings = {
            uri: vec
            for uri, vec in source_embeddings.items()
            if uri not in source_container_uris
        }
        job["container_concepts"] = len(source_container_uris)

        # Deskriptor-Niveauknoten aus dem ANN-Pool nehmen (child_level_uris,
        # s. Eltern-Ableitung oben). Ihr Mapping ist bereits aus dem
        # Eltern-Anker abgeleitet; sie duerfen nicht zusaetzlich als
        # Quellkonzepte gegen den Hub klassifiziert werden.
        source_child_level_uris = {
            uri for uri in child_level_uris if uri in source_embeddings
        }
        source_embeddings = {
            uri: vec
            for uri, vec in source_embeddings.items()
            if uri not in source_child_level_uris
        }
        job["child_level_concepts"] = len(source_child_level_uris)

        # Rollengleiches Pairing (Befund 2026-09-05): harm:CompetenceConcept
        # wird nur gegen harm:CompetenceConcept verglichen, harm:LevelConcept
        # nur gegen harm:LevelConcept -- unabhaengig davon, ob fuer dieses
        # KQR-Paar ein struktureller Shortcut existiert. Fehlt einer Rolle auf
        # einer Seite (z. B. ESCO: nur CompetenceConcept), entsteht fuer sie
        # schlicht kein Kandidatenpaar, weil find_candidate_pairs() mit einem
        # leeren Dict aufgerufen wird bzw. der Rollen-Bucket fehlt.
        source_by_role = partition_by_role(source_embeddings, satellite_graph)
        target_by_role = partition_by_role(filtered_target_embeddings, hub_graph)

        candidate_pairs = []
        for role, role_source_embeddings in source_by_role.items():
            role_target_embeddings = target_by_role.get(role)
            if not role_target_embeddings:
                continue
            candidate_pairs.extend(
                find_candidate_pairs(role_source_embeddings, role_target_embeddings, settings.ann_top_k)
            )
        candidate_pairs = [
            pair
            for pair in candidate_pairs
            if (pair.concept_a, pair.concept_b) not in shortcut_pairs
        ]

        few_shot_examples = _build_few_shot_text(shortcut_mappings)
        providers = get_providers_from_config(settings)
        already_classified = mapping_service.get_classified_pairs(project_id=project_id)

        job["total_pairs"] = len(candidate_pairs)
        _save_jobs(project_id)
        for index, pair in enumerate(candidate_pairs):
            if pause_event.is_set():
                job["status"] = "paused"
                job["finished_at"] = _now_iso()
                _save_jobs(project_id)
                return

            if (pair.concept_a, pair.concept_b) not in already_classified:
                result = classify_pair(
                    pair,
                    concept_lookup[pair.concept_a],
                    concept_lookup[pair.concept_b],
                    few_shot_examples,
                    providers,
                    settings.classification_runs_per_pair,
                )
                # Sofort persistieren statt am Schleifenende zu sammeln --
                # ein Absturz/Neustart mitten im Lauf verliert damit
                # höchstens das gerade in Bearbeitung befindliche Paar,
                # nicht den gesamten bisherigen Fortschritt.
                mapping_service.add_classification_results([result], project_id=project_id)
                mapping_service.add_mappings(
                    classification_results_to_mappings([result], concept_lookup), project_id=project_id
                )

            job["done_pairs"] = index + 1
            _save_jobs(project_id)

        # Blattknoten sind klassifiziert -- jetzt die abgeleiteten
        # Container-Mappings (skos:narrowMatch, semapv:LogicalReasoning) aus
        # den Kindmappings bilden. Idempotent: bereits abgeleitete Container
        # werden bei einem fortgesetzten Lauf uebersprungen.
        if source_container_children:
            pair_mappings = mapping_service.list_mappings_for_pair(
                kqr_a_id, kqr_b_id, project_id=project_id
            )
            already_derived = {
                m.subject_id
                for m in pair_mappings
                if m.mapping_justification == MappingJustification.LOGICAL_REASONING
            }
            derived = derive_container_mappings(
                source_container_children, pair_mappings, concept_lookup, already_derived
            )
            if derived:
                mapping_service.add_mappings(derived, project_id=project_id)
            job["container_mappings_derived"] = job.get("container_mappings_derived", 0) + len(derived)
            _save_jobs(project_id)

        job["status"] = "completed"
        job["finished_at"] = _now_iso()
        _save_jobs(project_id)
    except Exception as exc:  # Hintergrundjob: Fehler müssen im Job-Status sichtbar werden.
        logger.exception("Klassifikationsjob '%s' fehlgeschlagen", job_id)
        job["status"] = "failed"
        job["error"] = str(exc)
        job["finished_at"] = _now_iso()
        _save_jobs(project_id)
    finally:
        _pause_events.get(project_id, {}).pop(job_id, None)


def start_classification_job(kqr_a_id: str, kqr_b_id: str, project_id: str = "default") -> str:
    """Startet Schritt 2 (Vorfilter/ANN) gefolgt von Schritt 3 (LLM-Klassifikation)
    als Hintergrundjob für zwei ausgewählte KQR innerhalb eines Projekts und
    gibt die Job-ID zurück.

    Bereits klassifizierte Paare (mapping_service.get_classified_pairs())
    werden übersprungen -- ein erneuter Aufruf für dasselbe KQR-Paar nach
    einem Absturz/Neustart kostet daher nur noch die verbliebenen Paare."""
    project_service.ensure_writable(project_id)
    job_id = str(uuid.uuid4())
    jobs = _get_project_jobs(project_id)
    jobs[job_id] = {
        "job_id": job_id,
        "kqr_a_id": kqr_a_id,
        "kqr_b_id": kqr_b_id,
        "status": "running",
        "done_pairs": 0,
        "total_pairs": 0,
        "error": None,
        "started_at": _now_iso(),
        "finished_at": None,
    }
    _save_jobs(project_id)
    pause_event = threading.Event()
    _pause_events.setdefault(project_id, {})[job_id] = pause_event
    thread = threading.Thread(
        target=_run_job, args=(job_id, kqr_a_id, kqr_b_id, pause_event, project_id), daemon=True
    )
    thread.start()
    return job_id


def pause_job(job_id: str, project_id: str = "default") -> dict:
    """Fordert das Pausieren eines laufenden Jobs an (Mixed-Initiative:
    Nutzer kann einen teuren LLM-Lauf gezielt anhalten). Wirkt erst vor dem
    nächsten Paar, nicht mitten in einem laufenden LLM-Aufruf."""
    jobs = _get_project_jobs(project_id)
    if job_id not in jobs:
        raise KeyError(f"Job '{job_id}' nicht gefunden.")
    pause_events = _pause_events.get(project_id, {})
    if job_id not in pause_events:
        raise ValueError(f"Job '{job_id}' läuft nicht in diesem Prozess und kann nicht pausiert werden.")
    pause_events[job_id].set()
    return {"job_id": job_id, "pause_requested": True}


def resume_job(job_id: str, project_id: str = "default") -> dict:
    """Setzt einen pausierten oder unterbrochenen (Prozess-Neustart, vgl.
    _load_jobs) Job unter derselben Job-ID fort. candidate_pairs werden
    deterministisch neu berechnet (kein LLM-Aufruf); dank
    get_classified_pairs() werden bereits erledigte Paare übersprungen, der
    Job macht also exakt dort weiter, wo er stehen geblieben ist."""
    project_service.ensure_writable(project_id)
    jobs = _get_project_jobs(project_id)
    job = jobs.get(job_id)
    if job is None:
        raise KeyError(f"Job '{job_id}' nicht gefunden.")
    if job["status"] not in ("paused", "interrupted"):
        raise ValueError(f"Job '{job_id}' ist nicht fortsetzbar (status={job['status']}).")

    job["status"] = "running"
    job["started_at"] = _now_iso()
    job["finished_at"] = None
    _save_jobs(project_id)
    pause_event = threading.Event()
    _pause_events.setdefault(project_id, {})[job_id] = pause_event
    thread = threading.Thread(
        target=_run_job,
        args=(job_id, job["kqr_a_id"], job["kqr_b_id"], pause_event, project_id),
        daemon=True,
    )
    thread.start()
    return {"job_id": job_id, "status": "running"}


def list_jobs(project_id: str = "default") -> list[dict]:
    """Alle bekannten Jobs eines Projekts (nicht nur der zuletzt in einer
    einzelnen Browser-Session gestartete) mit Fortschritts-Prozent --
    Grundlage für eine UI, die alle parallel laufenden Klassifikationsjobs
    anzeigt. Jobs laufen bereits heute unabhängig in eigenen Threads, ein
    zweiter start_classification_job()-Aufruf blockiert nicht auf einen
    ersten."""
    return [get_job_progress(job_id, project_id=project_id) for job_id in _get_project_jobs(project_id)]


def get_job_progress(job_id: str, project_id: str = "default") -> dict:
    jobs = _get_project_jobs(project_id)
    if job_id not in jobs:
        raise KeyError(f"Job '{job_id}' nicht gefunden.")
    job = jobs[job_id]
    total = job["total_pairs"]
    if total:
        percent = round(100 * job["done_pairs"] / total, 1)
    else:
        percent = 100.0 if job["status"] == "completed" else 0.0
    # Alt-Jobs (vor Einfuehrung der Zeitstempel) haben die Schluessel nicht --
    # setdefault haelt das Response-Schema fuer die UI trotzdem stabil.
    return {
        "started_at": None,
        "finished_at": None,
        **job,
        "percent": percent,
    }


def check_preconditions() -> dict:
    """Prüft Neo4j-Verbindung und LLM-Endpunkt-Konfiguration vor Prozessstart
    (Funktionsgruppe 2, Statuszeilen). Neo4j-Nichterreichbarkeit ist laut
    Persistenz-Design kein Blocker, wird dem Benutzer aber transparent
    angezeigt (Visibility of System State). Projektunabhängig -- betrifft
    globale Infrastruktur, nicht projektspezifische Daten."""
    neo4j_reachable = False
    try:
        driver = get_driver(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
        driver.verify_connectivity()
        driver.close()
        neo4j_reachable = True
    except Exception:
        neo4j_reachable = False

    llm_configured = is_any_provider_configured(settings)

    return {
        "neo4j_reachable": neo4j_reachable,
        "llm_configured": llm_configured,
        "llm_providers": settings.llm_providers,
    }
