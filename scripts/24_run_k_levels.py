"""
K_levels-Lauf: DQR-Dimensionsdeskriptoren (``dqr_2d``) gegen einen reinen
EQF-Referenzrahmen (``eqf_1d``) harmonisieren -- ohne ANN/LLM.

Mechanik (Sign-off 2026-09-06, ``data/structural_shortcut_predicates.json``
bleibt unveraendert):

  - Die 8 DQR-Niveau-Anker ``dqr:L{n}`` erhalten ihren EQF-Match ueber einen
    Struktur-Shortcut: ``classification_service._run_job`` behandelt
    ``skos:exactMatch`` fuer diesen Lauf per In-Memory-Override als
    Shortcut-Praedikat (nur Richtung Satellit -> Hub).
  - Die 32 DQR-Deskriptoren ``dqr:L{n}_{Dimension}`` laufen nicht durch
    ANN/LLM (``prefilter.child_level_concept_uris``); ihr Mapping wird aus
    dem Match des Eltern-Ankers abgeleitet
    (``prefilter.derive_child_level_mappings``): ``skos:narrowMatch``,
    ``semapv:LogicalReasoning``, ``review_status=conjunct``.

Der Lauf legt ein neues, zeitgestempeltes Projekt unter ``data/projects/``
an und prueft anschliessend die Abnahmekriterien aus der Kapitel-5-Vorgabe.
Exit-Code 0 nur, wenn alle Kriterien erfuellt sind.

    python scripts/24_run_k_levels.py
    python scripts/24_run_k_levels.py --satellite dqr_2d --hub eqf_2d
    python scripts/24_run_k_levels.py --cleanup      # Projekt nach Pruefung wieder loeschen
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.models.schemas import Mapping, MappingJustification, ReviewStatus
from app.services import classification_service, kqr_service, mapping_service, project_service

TOOL_EXPECTED = Mapping.model_fields["mapping_tool"].default  # K_skills-Tool-String


def _predicate(mapping: Mapping) -> str | None:
    return mapping.predicate_id.value if mapping.predicate_id else None


def _wait_for_job(job_id: str, project_id: str, timeout_s: float = 120.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while True:
        progress = classification_service.get_job_progress(job_id, project_id=project_id)
        if progress["status"] in ("completed", "failed", "paused", "interrupted"):
            return progress
        if time.monotonic() > deadline:
            progress["status"] = "timeout"
            return progress
        time.sleep(0.1)


def run(satellite: str, hub: str, project_name: str, cleanup: bool) -> bool:
    for kqr_id in (satellite, hub):
        kqr = kqr_service.get_kqr(kqr_id)
        print(f"KQR {kqr_id:10s} status={kqr.status.value:12s} "
              f"concepts={kqr.concept_count} is_hub={kqr.is_hub}")

    project = project_service.create_project(
        name=project_name,
        kqr_ids=[satellite, hub],
        description=(
            "DQR-Dimensionsdeskriptoren <-> EQF: Niveau-Crosswalk (Struktur-Shortcut) "
            "+ Eltern-Ableitung, kein ANN/LLM."
        ),
        hub_kqr_id=hub,
    )
    project_id = project.project_id
    print(f"\nProjekt-ID: {project_id}")

    warm_start = time.monotonic()
    kqr_service.get_embeddings(satellite)
    kqr_service.get_embeddings(hub)
    print(f"Embedding-Vorlauf (einmalig, nicht Teil der Run-Zeit): "
          f"{time.monotonic() - warm_start:.1f}s")

    # _satellite_kqr_id() waehlt kqr_a, wenn keiner is_hub ist -> Satellit zuerst.
    run_start = time.monotonic()
    job_id = classification_service.start_classification_job(
        satellite, hub, project_id=project_id
    )
    progress = _wait_for_job(job_id, project_id)
    runtime = time.monotonic() - run_start

    print(f"\nJob-Status: {progress.get('status')}   error={progress.get('error')}")
    print(f"Run-Laufzeit: {runtime:.2f} s")
    print(f"total_pairs(ANN/LLM)={progress.get('total_pairs')}  "
          f"container_concepts={progress.get('container_concepts')}  "
          f"child_level_concepts={progress.get('child_level_concepts')}  "
          f"child_level_mappings_derived={progress.get('child_level_mappings_derived')}")

    mappings = mapping_service.list_mappings_for_pair(satellite, hub, project_id=project_id)
    struct = [m for m in mappings if m.mapping_justification == MappingJustification.STRUCTURAL_MATCHING]
    logic = [m for m in mappings if m.mapping_justification == MappingJustification.LOGICAL_REASONING]
    llm = [m for m in mappings if m.mapping_justification == MappingJustification.LLM_BASED_MATCHING]
    threshold = settings.mapping_confidence_threshold

    checks: list[tuple[bool, str]] = []

    print(f"\nMappings gesamt: {len(mappings)}   (erwartet 40)")
    print("\n--- MUSS STIMMEN ---")

    ok = (len(struct) == 8
          and all(_predicate(m) == "skos:exactMatch" for m in struct)
          and all(m.mapping_confidence == 1.0 for m in struct))
    checks.append((ok, "8x StructuralMatching / skos:exactMatch / conf 1.0"))
    print(f"[{'OK ' if ok else 'XXX'}] 8x StructuralMatching / skos:exactMatch / conf 1.0"
          f"  -> n={len(struct)} preds={sorted({_predicate(m) for m in struct})} "
          f"confs={sorted({m.mapping_confidence for m in struct})}")

    ok = (len(logic) == 32
          and all(_predicate(m) == "skos:narrowMatch" for m in logic)
          and all(m.mapping_confidence == 1.0 for m in logic))
    checks.append((ok, "32x LogicalReasoning / skos:narrowMatch / conf 1.0"))
    print(f"[{'OK ' if ok else 'XXX'}] 32x LogicalReasoning / skos:narrowMatch / conf 1.0"
          f" -> n={len(logic)} preds={sorted({_predicate(m) for m in logic})} "
          f"confs={sorted({m.mapping_confidence for m in logic})}")

    tools = sorted({m.mapping_tool for m in mappings})
    ok = tools == [TOOL_EXPECTED]
    checks.append((ok, f"mapping_tool == {TOOL_EXPECTED!r}"))
    print(f"[{'OK ' if ok else 'XXX'}] mapping_tool == K_skills-String ({TOOL_EXPECTED!r}) -> {tools}")

    open_queue = [m for m in mappings if m.review_status == ReviewStatus.OPEN]
    below = [m for m in mappings if m.mapping_confidence < threshold]
    ok = not open_queue and not below
    checks.append((ok, "Review-Queue leer"))
    print(f"[{'OK ' if ok else 'XXX'}] Review-Queue leer -> "
          f"ReviewStatus.OPEN={len(open_queue)}  conf<{threshold}={len(below)}")

    print("\n--- DARF NICHT VORKOMMEN ---")
    ok = len(llm) == 0
    checks.append((ok, "kein semapv:LLMBasedMatching"))
    print(f"[{'OK ' if ok else 'XXX'}] semapv:LLMBasedMatching in DQR/EQF-Mapping -> {len(llm)}")

    eqf_subject = [m for m in mappings if m.subject_kqr_id == hub]
    ok = not eqf_subject
    checks.append((ok, "kein EQF-Konzept als subject_id"))
    print(f"[{'OK ' if ok else 'XXX'}] EQF-Konzept als subject_id -> {len(eqf_subject)}")

    related = [m for m in mappings if _predicate(m) == "skos:relatedMatch"]
    ok = not related
    checks.append((ok, "kein skos:relatedMatch"))
    print(f"[{'OK ' if ok else 'XXX'}] skos:relatedMatch unter den Mappings -> {len(related)}")

    print("\n--- DOKUMENTATION (Synthese-Tabelle Kap. 4) ---")
    print(f"  Projekt-ID:      {project_id}")
    print(f"  Run-Laufzeit:    {runtime:.2f} s")
    print(f"  Mappings gesamt: {len(mappings)}")
    print(f"  Verteilung:      {dict(Counter(m.mapping_justification.value for m in mappings))}")

    print("\nBeispiele:")
    for mapping in sorted(struct, key=lambda m: m.subject_id)[:2] + sorted(logic, key=lambda m: m.subject_id)[:2]:
        print(f"  {mapping.subject_id.rsplit('/', 1)[-1]:18s} {_predicate(mapping):16s} -> "
              f"{mapping.object_id:40s} conf={mapping.mapping_confidence} "
              f"just={mapping.mapping_justification.value}")

    all_ok = all(passed for passed, _ in checks)
    if cleanup:
        project_service.delete_project(project_id)
        print(f"\n(Projekt {project_id} nach Pruefung geloescht -- --cleanup)")

    print(f"\n{'>>> ALLE KRITERIEN ERFUELLT -- Kapitel-5-faehig' if all_ok else '>>> KRITERIEN NICHT ERFUELLT'}")
    if not all_ok:
        for passed, label in checks:
            if not passed:
                print(f"    verletzt: {label}")
    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--satellite", default="dqr_2d", help="Satelliten-KQR-ID (Default dqr_2d)")
    parser.add_argument("--hub", default="eqf_1d", help="Referenzrahmen-KQR-ID (Default eqf_1d)")
    parser.add_argument("--project-name", default="K_levels", help="Name des angelegten Projekts")
    parser.add_argument("--cleanup", action="store_true", help="Projekt nach der Pruefung wieder loeschen")
    args = parser.parse_args()

    ok = run(args.satellite, args.hub, args.project_name, args.cleanup)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
