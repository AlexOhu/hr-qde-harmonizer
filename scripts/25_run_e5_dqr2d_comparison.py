"""Reproduzierbarer E5-Neulauf: e-CF-Dimension 3 gegen DQR-2D.

Der Lauf beantwortet ausschliesslich den bislang nicht belegten Teil des
Granularitaetsvergleichs: Die 106 e-CF-Niveaukonzepte werden gegen die 40
DQR-2D-Niveau- und Dimensionskonzepte klassifiziert.  Anders als
``24_run_k_levels.py`` ist dies kein struktureller Crosswalk; jedes
ANN-Kandidatenpaar durchlaeuft die konfigurierte Dreifachklassifikation.

Es wird stets ein neues Projekt angelegt.  ``run_manifest.json`` im
Projektverzeichnis und das Ergebnis unter ``eval/results/`` halten die
Konfiguration, die Eingabefingerabdruecke und die verwendeten Nenner fest.

    python scripts/25_run_e5_dqr2d_comparison.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from rdflib import RDF, URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.models.schemas import MappingJustification, RelationType, ReviewStatus
from app.pipeline.step2_embedding_prefilter.prefilter import HARM, concept_role
from app.services import classification_service, kqr_service, mapping_service, project_service

SATELLITE = "ecf_level"
HUB = "dqr_2d"


def sha256_16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def git_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return "unbekannt"


def level_uris(kqr_id: str) -> set[str]:
    graph = kqr_service.get_graph(kqr_id)
    return {
        concept.uri for concept in kqr_service.get_concepts(kqr_id)
        if concept_role(concept.uri, graph) == HARM.LevelConcept
    }


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    preconditions = classification_service.check_preconditions()
    if not preconditions["llm_configured"]:
        raise SystemExit("Kein LLM-Provider konfiguriert; kein externer Lauf gestartet.")

    satellite_levels = level_uris(SATELLITE)
    hub_levels = level_uris(HUB)
    if len(satellite_levels) != 106 or len(hub_levels) != 40:
        raise SystemExit(
            f"Unerwartete Levelpopulation: {SATELLITE}={len(satellite_levels)}, "
            f"{HUB}={len(hub_levels)} (erwartet 106 bzw. 40)."
        )

    project = project_service.create_project(
        name="E5 dqr_2d Vergleich (ecf_level)",
        kqr_ids=[SATELLITE, HUB],
        kqr_scopes={SATELLITE: "level_only"},
        hub_kqr_id=HUB,
        description=(
            "E5-Neulauf zur getrennten Belegung des Granularitaetsvergleichs: "
            "106 e-CF-Dimension-3-Niveaukonzepte gegen 40 dqr_2d-Konzepte. "
            "ANN top-k und dreifache LLM-Klassifikation gemaess Laufkonfiguration."
        ),
    )
    project_dir = project_service.get_project_data_dir(project.project_id)
    prompt = ROOT / "prompts" / "classification_prompt_template.txt"
    manifest_path = project_dir / "run_manifest.json"
    manifest = {
        "purpose": "E5 dqr_2d granularity comparison; fresh external classification run",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "project_id": project.project_id,
        "git_head": git_head(),
        "kqr_pair": {"satellite": SATELLITE, "hub": HUB},
        "scope": {SATELLITE: "level_only"},
        "input_population": {
            "ecf_level_all_concepts": len(kqr_service.get_concepts(SATELLITE)),
            "ecf_level_level_concepts": len(satellite_levels),
            "dqr_2d_all_concepts": len(kqr_service.get_concepts(HUB)),
            "dqr_2d_level_concepts": len(hub_levels),
        },
        "candidate_space": {
            "ann_top_k": settings.ann_top_k,
            "maximum_pairs": len(satellite_levels) * min(settings.ann_top_k, len(hub_levels)),
            "classification_runs_per_pair": settings.classification_runs_per_pair,
        },
        "configuration": {
            "llm_providers": settings.llm_providers,
            "mistral_model": settings.mistral_model,
            "classification_temperature": settings.classification_temperature,
            "embedding_model": settings.embedding_model,
            "mapping_confidence_threshold": settings.mapping_confidence_threshold,
        },
        "input_sha256_16": {
            "data/formalized/ecf_level.ttl": sha256_16(ROOT / "data/formalized/ecf_level.ttl"),
            "data/formalized/dqr_2d.ttl": sha256_16(ROOT / "data/formalized/dqr_2d.ttl"),
            "prompts/classification_prompt_template.txt": sha256_16(prompt),
        },
        "status": "started",
    }
    write_json(manifest_path, manifest)
    print(f"Projekt: {project.project_id}", flush=True)
    print(f"Manifest: {manifest_path}", flush=True)

    job_id = classification_service.start_classification_job(SATELLITE, HUB, project_id=project.project_id)
    print(f"Job: {job_id}", flush=True)
    last = None
    while True:
        progress = classification_service.get_job_progress(job_id, project_id=project.project_id)
        snapshot = (progress["status"], progress["done_pairs"], progress["total_pairs"])
        if snapshot != last:
            print(
                f"Fortschritt: {progress['status']} "
                f"{progress['done_pairs']}/{progress['total_pairs']} ({progress['percent']}%)",
                flush=True,
            )
            last = snapshot
        if progress["status"] in {"completed", "failed", "paused", "interrupted"}:
            break
        time.sleep(10)

    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["job"] = progress
    manifest["status"] = progress["status"]
    write_json(manifest_path, manifest)
    if progress["status"] != "completed":
        raise SystemExit(f"Lauf nicht abgeschlossen: {progress['status']}; siehe {manifest_path}")

    mappings = mapping_service.list_mappings_for_pair(SATELLITE, HUB, project_id=project.project_id)
    results = mapping_service._get_classification_results(project.project_id)
    result_counts = Counter(
        result.final_relation.value if result.final_relation is not None else "NO_CONSENSUS"
        for result in results
    )
    conjunct = [
        mapping for mapping in mappings
        if mapping.review_status == ReviewStatus.CONJUNCT
        and mapping.mapping_justification == MappingJustification.LLM_BASED_MATCHING
        and mapping.subject_id in satellite_levels
    ]
    by_subject: dict[str, list] = defaultdict(list)
    for mapping in conjunct:
        by_subject[mapping.subject_id].append(mapping)
    mapped_subjects = len(by_subject)
    exactly_one = sum(len(items) == 1 for items in by_subject.values())

    output = ROOT / "eval" / "results" / f"E5_dqr_2d_{project.project_id}.json"
    report = {
        "purpose": manifest["purpose"],
        "project_id": project.project_id,
        "manifest": str(manifest_path.relative_to(ROOT)),
        "job_id": job_id,
        "result_definition": (
            "Conjunct LLM mappings only: final relation EQUIVALENT, A_SUBSUMES_B, or "
            "B_SUBSUMES_A; RELATED and no-consensus remain outside the accepted mapping set."
        ),
        "denominators": {
            "eligible_ecf_level_concepts": len(satellite_levels),
            "candidate_pairs": progress["total_pairs"],
            "accepted_mapped_subjects": mapped_subjects,
        },
        "metrics": {
            "accepted_mappings": len(conjunct),
            "subjects_with_at_least_one_accepted_mapping": mapped_subjects,
            "coverage_of_eligible_subjects": mapped_subjects / len(satellite_levels),
            "subjects_with_exactly_one_accepted_mapping": exactly_one,
            "exactly_one_among_mapped_subjects": exactly_one / mapped_subjects if mapped_subjects else None,
            "mean_accepted_mappings_per_mapped_subject": len(conjunct) / mapped_subjects if mapped_subjects else None,
        },
        "classification_result_distribution": dict(sorted(result_counts.items())),
        "mapping_distribution": {
            "all_persisted_mappings": len(mappings),
            "by_review_status": dict(Counter(mapping.review_status.value for mapping in mappings)),
            "by_predicate": dict(Counter(mapping.predicate_id.value if mapping.predicate_id else "NONE" for mapping in mappings)),
        },
    }
    write_json(output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    print(f"Ergebnis: {output}", flush=True)


if __name__ == "__main__":
    main()
