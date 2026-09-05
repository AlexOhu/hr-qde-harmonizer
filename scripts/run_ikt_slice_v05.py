"""
Aufgabe 3 (Kapitel 5): Re-Run der Harmonisierungspipeline fuer den IKT-Slice
mit den Aenderungen aus Aufgabe 1 (reduziertes DQR: dqr_3, 8 Niveaus) und
Aufgabe 2 (Container-Erkennung im Vorfilter).

Faehrt die Service-Schicht direkt an (kein laufender uvicorn noetig), damit
der frisch gestartete Prozess garantiert den geaenderten Pipeline-Code
verwendet.

    python scripts/run_ikt_slice_v05.py --plan-only   # nur Kandidatenzaehlung
    python scripts/run_ikt_slice_v05.py               # voller Lauf + Statistik
    python scripts/run_ikt_slice_v05.py --stats-only  # nur Statistik aus Bestand
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Rate-Limit-Schutz fuer den grossen Mistral-Lauf: muss VOR dem Import von
# app.config / mistral_provider gesetzt sein (die Werte werden beim Import
# als Modulkonstanten gelesen). Sequenzieller Ein-Strom-Betrieb + moderater
# Mindestabstand halten den Lauf unter dem 429-Limit; grosszuegige Retries
# fangen verbleibende Blips ab, ohne den Job zu killen.
os.environ.setdefault("MISTRAL_MIN_REQUEST_INTERVAL_S", "0.8")
os.environ.setdefault("MISTRAL_MAX_ATTEMPTS", "10")
os.environ.setdefault("MISTRAL_RETRY_BACKOFF_SECONDS", "6.0")

from app.config import settings
from app.models.schemas import MappingJustification, MappingPredicate, ReviewStatus
from app.services import classification_service, mapping_service, project_service

HUB = "esco_v1_2_ict_ausschnitt"
SATELLITES = ["ecf", "dqr_3", "eqf_2017"]
PROJECT_NAME = "HR-QDE Basisontologie - IKT Slice V0.5"
PREV_PROJECT_ID = "hr_qde_basisontologie_ikt_slice_20260830T050546Z"


def ensure_project() -> str:
    for project in project_service.list_projects():
        if project.name == PROJECT_NAME:
            print(f"Projekt vorhanden: {project.project_id}")
            return project.project_id
    project = project_service.create_project(
        name=PROJECT_NAME,
        kqr_ids=[HUB, *SATELLITES],
        description=(
            "Aufgabe 3: Re-Run mit reduziertem DQR (dqr_3, 8 Niveaus) und "
            "Container-Erkennung im Vorfilter. skos:narrower-/skos:broader-"
            "Eltern laufen nicht in die ANN-Suche; ihr Mapping wird als "
            "skos:broadMatch (semapv:LogicalReasoning) aus den Kindmappings "
            "abgeleitet. KQR-Set und ANN_TOP_K=20 wie Vorgaengerprojekt."
        ),
        hub_kqr_id=HUB,
    )
    print(f"Projekt angelegt: {project.project_id}")
    return project.project_id


def _run_one_pair(project_id: str, sat: str, poll_s: float, max_restarts: int = 6) -> dict:
    """Klassifiziert genau ein KQR-Paar (sat <-> HUB) und wartet auf das Ende.

    Ein fehlgeschlagener Job (z. B. hartnaeckiges 429 nach allen Retries)
    wird durch einen frischen start_classification_job() fortgesetzt: bereits
    klassifizierte Paare ueberspringt der Job kostenfrei ueber
    get_classified_pairs(), der Lauf macht also dort weiter, wo er stand.
    """
    restarts = 0
    while True:
        job_id = classification_service.start_classification_job(sat, HUB, project_id=project_id)
        print(f"gestartet: {sat} <-> {HUB}  job={job_id}  (restart {restarts})")
        while True:
            time.sleep(poll_s)
            prog = classification_service.get_job_progress(job_id, project_id=project_id)
            print(
                f"  [{sat:9s}] {prog['done_pairs']:>5}/{prog['total_pairs']:<5} "
                f"{prog['percent']:>5}%  status={prog['status']}"
                f"  container={prog.get('container_concepts', '-')}"
                f" abgeleitet={prog.get('container_mappings_derived', '-')}"
            )
            if prog["status"] in ("completed", "failed", "paused", "interrupted"):
                break
        if prog["status"] == "completed":
            return prog
        restarts += 1
        if restarts > max_restarts:
            print(f"  [{sat}] nach {max_restarts} Neustarts weiterhin {prog['status']} "
                  f"({prog.get('error')!r}) -- Teilstand wird uebernommen")
            return prog
        wait = min(60.0, 15.0 * restarts)
        print(f"  [{sat}] {prog['status']} ({prog.get('error')!r}) -- Neustart in {wait:.0f}s")
        time.sleep(wait)


def run_jobs(project_id: str, poll_s: float = 15.0) -> dict[str, dict]:
    """Sequenziell, ein KQR-Paar nach dem anderen (Ein-Strom-Betrieb gegen
    das Mistral-429-Limit; drei parallele Jobs ueberschreiten es sofort)."""
    final: dict[str, dict] = {}
    for sat in SATELLITES:
        final[sat] = _run_one_pair(project_id, sat, poll_s)
    return final


def _relevant_jobs(project_id: str) -> list[dict]:
    """Je KQR-Paar nur ein Job. Ein Paar kann mehrere Job-Eintraege haben
    (fehlgeschlagener Erstversuch + erfolgreicher Neustart); fuer die
    Statistik zaehlt der weiteste (completed vor mehr done_pairs), damit
    total_pairs / container_concepts nicht doppelt summiert werden."""
    best: dict[tuple, dict] = {}
    for job in classification_service.list_jobs(project_id=project_id):
        key = tuple(sorted((job["kqr_a_id"], job["kqr_b_id"])))
        rank = (job["status"] == "completed", job.get("done_pairs", 0))
        cur = best.get(key)
        if cur is None or rank > (cur["status"] == "completed", cur.get("done_pairs", 0)):
            best[key] = job
    return list(best.values())


def _stats_for_project(project_id: str) -> dict:
    mapping_service.reload(project_id)
    mappings = mapping_service._get_mappings(project_id)
    results = mapping_service._get_classification_results(project_id)
    jobs = _relevant_jobs(project_id)

    total_candidate_pairs = sum(j.get("total_pairs", 0) for j in jobs)
    container_concepts = sum(j.get("container_concepts", 0) or 0 for j in jobs)

    result_dist = Counter(
        r.final_relation.value if r.final_relation else "NO_CONSENSUS" for r in results
    )
    mapping_pred = Counter(
        m.predicate_id.value if m.predicate_id else "none" for m in mappings
    )
    just_dist = Counter(m.mapping_justification.value for m in mappings)

    open_mappings = [m for m in mappings if m.review_status == ReviewStatus.OPEN]
    unresolved = [m for m in open_mappings if m.predicate_id is None]
    related_open = [
        m for m in open_mappings if m.predicate_id == MappingPredicate.RELATED_MATCH
    ]
    low_conf = [
        m
        for m in mappings
        if m.review_status == ReviewStatus.CONJUNCT
        and m.mapping_source != "manual"
        and m.mapping_confidence < settings.mapping_confidence_threshold
    ]
    container_derived = [
        m
        for m in mappings
        if m.mapping_justification == MappingJustification.LOGICAL_REASONING
    ]
    shortcuts = [
        m
        for m in mappings
        if m.mapping_justification == MappingJustification.STRUCTURAL_MATCHING
    ]
    coverage = mapping_service.get_coverage_summary(project_id)

    return {
        "project_id": project_id,
        "jobs": [(j["kqr_a_id"], j["status"], j.get("total_pairs"), j.get("done_pairs")) for j in jobs],
        "total_candidate_pairs": total_candidate_pairs,
        "container_concepts_excluded": container_concepts,
        "classification_results": len(results),
        "result_relation_distribution": dict(result_dist),
        "mappings_total": len(mappings),
        "mapping_predicate_distribution": dict(mapping_pred),
        "mapping_justification_distribution": dict(just_dist),
        "review_open_total": len(open_mappings) + len(low_conf),
        "review_open_related": len(related_open),
        "review_open_unresolved": len(unresolved),
        "review_open_low_confidence": len(low_conf),
        "unresolved": len(unresolved),
        "container_derived_mappings": len(container_derived),
        "structural_shortcuts": len(shortcuts),
        "coverage": coverage,
    }


def print_plan_walkthrough(project_id: str) -> None:
    """Durchlaufbeispiel e-CF PLAN + Kindkonzepte A.1-A.9 (Aufgabe 2)."""
    from rdflib import RDF, SKOS
    from app.pipeline.step2_embedding_prefilter.prefilter import detect_container_concepts
    from app.services import kqr_service

    mapping_service.reload(project_id)
    mappings = mapping_service._get_mappings(project_id)

    graph = kqr_service.get_graph("ecf")
    containers, children = detect_container_concepts(graph)
    plan = next(c for c in containers if c.endswith("plan"))
    plan_kids = children[plan]

    label = {}
    for c in graph.subjects(RDF.type, SKOS.Concept):
        en = [str(o) for o in graph.objects(c, SKOS.prefLabel) if getattr(o, "language", None) == "en"]
        label[str(c)] = en[0] if en else str(c).rsplit("/", 1)[-1]

    print("\n" + "=" * 72)
    print("DURCHLAUFBEISPIEL  e-CF PLAN  (Aufgabe 2)")
    print("=" * 72)
    print(f"Container erkannt:  {plan.rsplit('/', 1)[-1]}  ->  {len(plan_kids)} Kinder")
    print("  Kinder:", ", ".join(k.rsplit("/", 1)[-1] for k in plan_kids))
    print("  => PLAN laeuft NICHT in die ANN-Suche (nur A.1-A.9 werden klassifiziert).")

    by_subj: dict[str, list] = {}
    for m in mappings:
        by_subj.setdefault(m.subject_id, []).append(m)

    print("\n  Blatt-Klassifikation der Kinder (nur CONJUNCT-Mappings):")
    for kid in plan_kids:
        kms = [m for m in by_subj.get(kid, []) if m.review_status.value == "conjunct"
               and m.mapping_justification.value == "semapv:LLMBasedMatching"]
        kid_short = kid.rsplit("/", 1)[-1]
        print(f"    {kid_short} \"{label.get(kid, '')}\":  {len(kms)} CONJUNCT-Mapping(s) nach ESCO")
        for m in sorted(kms, key=lambda x: -x.mapping_confidence)[:3]:
            print(f"        {m.predicate_id:18s} -> \"{m.object_label}\"  (conf {m.mapping_confidence:.2f})")

    derived = [m for m in mappings
               if m.subject_id == plan and m.mapping_justification.value == "semapv:LogicalReasoning"]
    print(f"\n  Abgeleitetes Container-Mapping fuer PLAN: {len(derived)} Stueck")
    print("  (predicate_id=skos:broadMatch, mapping_justification=semapv:LogicalReasoning,")
    print("   mapping_confidence = Mittel der auf dieses Ziel zeigenden Kind-Konfidenzen)")
    for m in sorted(derived, key=lambda x: -x.mapping_confidence)[:12]:
        print(f"      PLAN  skos:broadMatch  \"{m.object_label}\"   conf {m.mapping_confidence:.3f}")
    if len(derived) > 12:
        print(f"      ... und {len(derived) - 12} weitere")


def print_stats(project_id: str) -> None:
    cur = _stats_for_project(project_id)
    print("\n" + "=" * 72)
    print(f"STATISTIK  {PROJECT_NAME}")
    print(f"project_id: {project_id}")
    print("=" * 72)
    for sat, status, total, done in cur["jobs"]:
        print(f"  Job {sat:9s} status={status:10s} pairs={done}/{total}")
    print("-" * 72)
    print(f"Gesamtzahl Kandidatenpaare (ANN, nach Shortcut-Abzug): {cur['total_candidate_pairs']}")
    print(f"  Container-Konzepte aus ANN ausgeschlossen:           {cur['container_concepts_excluded']}")
    print(f"  Struktur-Shortcuts (confidence=1.0):                 {cur['structural_shortcuts']}")
    print(f"  Container-abgeleitete Mappings (LogicalReasoning):   {cur['container_derived_mappings']}")
    print("-" * 72)
    print(f"Auto-klassifiziert (ClassificationResult-Objekte):     {cur['classification_results']}")
    print(f"  Relationstyp-Verteilung (final_relation je Paar):")
    for rel, n in sorted(cur["result_relation_distribution"].items(), key=lambda kv: -kv[1]):
        print(f"      {rel:16s} {n}")
    print("-" * 72)
    print(f"Review offen (gesamt):                                 {cur['review_open_total']}")
    print(f"      davon RELATED (offen):                           {cur['review_open_related']}")
    print(f"      davon UNRESOLVED (offen):                         {cur['review_open_unresolved']}")
    print(f"      davon Konfidenz < {settings.mapping_confidence_threshold} (CONJUNCT):            {cur['review_open_low_confidence']}")
    print(f"UNRESOLVED:                                            {cur['unresolved']}")
    print("-" * 72)
    print(f"Mappings gesamt:                                       {cur['mappings_total']}")
    print(f"  Praedikat-Verteilung: {cur['mapping_justification_distribution']}")
    print(f"  {cur['mapping_predicate_distribution']}")
    print(f"  Coverage: {cur['coverage']}")
    print("=" * 72)

    print("\nVERGLEICH ZU VORHER")
    print("  Angabe Aufgabenstellung:  900 Paare, 590 Review, 25 UNRESOLVED")
    try:
        prev = _stats_for_project(PREV_PROJECT_ID)
        print(f"  Vorgaengerprojekt {PREV_PROJECT_ID}:")
        print(f"      Kandidatenpaare:           {prev['total_candidate_pairs']}")
        print(f"      Auto-klassifiziert:        {prev['classification_results']}")
        print(f"      Relationstyp-Verteilung:   {prev['result_relation_distribution']}")
        print(f"      Review offen (gesamt):     {prev['review_open_total']}")
        print(f"      UNRESOLVED:                {prev['unresolved']}")
        print(f"      Mappings gesamt:           {prev['mappings_total']}")
        print(f"      Container-abgeleitet:      {prev['container_derived_mappings']}")
        print(f"      Struktur-Shortcuts:        {prev['structural_shortcuts']}")
    except Exception as exc:  # noqa: BLE001
        print(f"  (Vorgaengerprojekt nicht auswertbar: {exc})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--stats-only", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=15.0)
    args = parser.parse_args()

    project_id = ensure_project()

    if args.stats_only:
        print_stats(project_id)
        print_plan_walkthrough(project_id)
        return

    if args.plan_only:
        # Jobs starten, sofort pausieren -> total_pairs / container_concepts
        # stehen dann fest, ohne LLM-Kosten.
        for sat in SATELLITES:
            job_id = classification_service.start_classification_job(sat, HUB, project_id=project_id)
            time.sleep(2.0)
            classification_service.pause_job(job_id, project_id=project_id)
            time.sleep(1.0)
            prog = classification_service.get_job_progress(job_id, project_id=project_id)
            print(
                f"{sat:9s}  total_pairs={prog['total_pairs']}  "
                f"container_concepts={prog.get('container_concepts')}  status={prog['status']}"
            )
        return

    results = run_jobs(project_id, poll_s=args.poll_interval)
    print("\n=== Jobs beendet ===")
    for sat in SATELLITES:
        job = results.get(sat, {})
        print(f"  {sat:9s} status={job.get('status')}  {job.get('done_pairs')}/{job.get('total_pairs')}")
    print_stats(project_id)
    print_plan_walkthrough(project_id)


if __name__ == "__main__":
    main()
