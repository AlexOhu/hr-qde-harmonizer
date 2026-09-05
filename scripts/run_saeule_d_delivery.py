"""
Abgabepfad Saeule D: voller Pipeline-Lauf gegen die gelieferte
ESCO-Referenzmenge (``esco_skeleton_oberhuber``, 1302 Skills) und Erzeugung
der drei Lieferartefakte nach ``MASTERAND_OBERHUBER.md`` v0.2.

  Paar 1  e-CF  <-> ESCO-Skelett   scope=all            -> volle Pipeline
  Paar 2  dqr_3 <-> ESCO-Skelett   scope=container_only  -> nur Skelett-Ableitung

Ergebnis (in ``data/projects/<pid>/delivery/`` und im Repo-Root):
  oberhuber-harmonised-ontology-v{V}.ttl
  oberhuber-mappings-v{V}.ttl
  oberhuber-integration-strategy-v{V}.md

Zum Abschluss SHACL-Validierung der beiden TTL gegen die kanonischen
Bezugsdokumente (``hrqde-shape-harmonisation.ttl`` +
``hrqde-harmonisation-schema.ttl``). Abbruch bei > 0 Violations.

    python scripts/run_saeule_d_delivery.py --plan-only
    python scripts/run_saeule_d_delivery.py
    python scripts/run_saeule_d_delivery.py --export-only
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Rate-Limit-Schutz fuer den grossen Mistral-Lauf: vor dem app.config-Import.
os.environ.setdefault("MISTRAL_MIN_REQUEST_INTERVAL_S", "0.8")
os.environ.setdefault("MISTRAL_MAX_ATTEMPTS", "10")
os.environ.setdefault("MISTRAL_RETRY_BACKOFF_SECONDS", "6.0")

from app.models.schemas import ReviewStatus
from app.pipeline.step4_export.saeule_d_delivery import write_delivery
from app.services import (
    classification_service,
    disjoint_service,
    kqr_service,
    mapping_service,
    project_service,
)

ROOT = Path(__file__).resolve().parents[1]
HUB = "esco_skeleton_oberhuber"
ECF = "ecf"
DQR = "dqr_3"
KQR_SCOPES = {ECF: "all", DQR: "container_only"}
PROJECT_NAME = "Saeule D Lieferung (Informatik-Korridor)"
VERSION = "0.2"

SHAPE = ROOT / "hrqde-shape-harmonisation.ttl"
SCHEMA = ROOT / "hrqde-harmonisation-schema.ttl"

LIMITATIONS = [
    "Offene Reviews (RELATED/UNRESOLVED) fallen aus den Artefakten; die "
    "Einzelentscheidungen stehen aus (Coverage-Nenner beruecksichtigt sie).",
    "Disjunkte e-CF-Konzepte tragen den automatischen Vorschlag `own_class` "
    "(`disjoint_service.suggest_strategy`); die vollstaendige manuelle "
    "Einzelpruefung steht aus.",
    "Kein `harm:HarmonisedCluster`: HDBSCAN erreichte keine navigierbare "
    "Hierarchie (Negativbefund, Kapitel 6).",
    "Kein `EQUIVALENT`-Mapping im Gesamtdatensatz (LLM-Richtungsverzerrung, "
    "Kapitel 6).",
]


def ensure_project() -> str:
    for project in project_service.list_projects():
        if project.name == PROJECT_NAME:
            print(f"Projekt vorhanden: {project.project_id}")
            return project.project_id
    project = project_service.create_project(
        name=PROJECT_NAME,
        kqr_ids=[HUB, ECF, DQR],
        kqr_scopes=KQR_SCOPES,
        description=(
            "Abgabepfad Saeule D. Hub = esco_skeleton_oberhuber (1302 Skills, "
            "gelieferte Referenzmenge). e-CF scope=all durch die volle "
            "Pipeline; dqr_3 scope=container_only -> Skelett. Grundlage fuer "
            "oberhuber-harmonised-ontology-v0.2.ttl."
        ),
        hub_kqr_id=HUB,
    )
    print(f"Projekt angelegt: {project.project_id}  (kqr_scopes={KQR_SCOPES})")
    return project.project_id


def run_pipeline(project_id: str, poll_s: float) -> dict[str, dict]:
    mapping_service.reload(project_id)
    final: dict[str, dict] = {}
    for sat in (ECF, DQR):
        job_id = classification_service.start_classification_job(sat, HUB, project_id=project_id)
        while True:
            time.sleep(poll_s)
            prog = classification_service.get_job_progress(job_id, project_id=project_id)
            if prog["status"] in ("completed", "failed", "paused", "interrupted"):
                break
        tag = prog.get("skipped_reason", "pipeline")
        print(f"  {sat:24s} status={prog['status']:10s} "
              f"pairs={prog['done_pairs']}/{prog['total_pairs']}  "
              f"scope={prog.get('scope', '-')}  [{tag}]  "
              f"skeleton={prog.get('skeleton_concepts', '-')}  "
              f"container={prog.get('container_concepts', '-')}")
        final[sat] = prog
    return final


def do_export(project_id: str) -> dict:
    mapping_service.reload(project_id)
    k_mappings = mapping_service._get_mappings(project_id)
    ecf_graph = kqr_service.get_graph(ECF)
    disjoint_decisions = disjoint_service.list_decisions(project_id)
    coverage = mapping_service.get_coverage_summary(project_id=project_id)

    out_dir = project_service.get_project_data_dir(project_id) / "delivery"
    bundle = write_delivery(
        out_dir, ecf_graph, k_mappings, disjoint_decisions,
        coverage=coverage, limitations=LIMITATIONS, version=VERSION,
    )
    for stats in bundle.values():
        dst = ROOT / Path(stats["path"]).name
        shutil.copyfile(stats["path"], dst)
        stats["root_copy"] = str(dst)
    return bundle


def run_shacl(ttl_path: str) -> dict:
    try:
        from pyshacl import validate
    except ImportError:
        return {"available": False}
    conforms, _g, text = validate(
        ttl_path, shacl_graph=str(SHAPE), ont_graph=str(SCHEMA),
        data_graph_format="turtle", shacl_graph_format="turtle",
        ont_graph_format="turtle", inference="rdfs", advanced=True,
    )
    return {
        "available": True,
        "conforms": conforms,
        "violations": text.count("Constraint Violation"),
        "text": text,
    }


def stats_block(project_id: str, jobs: dict[str, dict], bundle: dict) -> bool:
    mapping_service.reload(project_id)
    mappings = mapping_service._get_mappings(project_id)
    results = mapping_service._get_classification_results(project_id)
    rel_dist = Counter(
        r.final_relation.value if r.final_relation else "NO_CONSENSUS" for r in results
    )
    open_m = [m for m in mappings if m.review_status == ReviewStatus.OPEN]
    unresolved = [m for m in open_m if m.predicate_id is None]

    onto, maps, strat = bundle["ontology"], bundle["mappings"], bundle["integration_strategy"]

    print("\n" + "=" * 72)
    print(f"STATISTIK  {PROJECT_NAME}")
    print("=" * 72)
    print(f"Hub {HUB}: {kqr_service.get_graph(HUB).__len__()} Tripel")
    print(f"e-CF <-> ESCO   auto-klassifiziert: {len(results)}   "
          f"({dict(rel_dist)})")
    print(f"  Review offen: {len(open_m)}   davon ohne Mehrheitsentscheid: {len(unresolved)}")
    print(f"  Mappings gesamt: {len(mappings)}")
    print("\nARTEFAKT 1  Ontologie")
    print(f"  {onto['root_copy']}")
    print(f"  Tripel {onto['triples']}   e-CF-Konzepte {onto['ecf_concepts']} "
          f"(+ {onto['ecf_areas']} Bereiche)   HarmonisedConcept {onto['harmonised_concepts']}")
    print(f"  Strategien: {onto['harmonised_by_strategy']}")
    print("\nARTEFAKT 2  Mappings")
    print(f"  {maps['root_copy']}")
    print(f"  HubMapping {maps['hub_mappings']}  (>= 0,67: {maps['hub_mappings_above_threshold_067']})  "
          f"LevelMapping {maps['level_mappings']}  OccupationMapping {maps['occupation_mappings']}")
    print(f"  Praedikate: {maps['hub_mappings_by_predicate']}")
    print("\nARTEFAKT 3  Integrationsstrategie")
    print(f"  {strat['root_copy']}")

    print("\nSHACL-VALIDIERUNG (kanonisch: hrqde-shape-harmonisation.ttl + Schema)")
    ok = True
    for key in ("ontology", "mappings"):
        res = run_shacl(bundle[key]["path"])
        if not res.get("available"):
            print("  pyshacl nicht verfuegbar -- Validierung uebersprungen.")
            ok = False
            break
        flag = "OK" if res["conforms"] else f"FAIL ({res['violations']} Violations)"
        print(f"  {key:10s} conforms={res['conforms']}  {flag}")
        if not res["conforms"]:
            print(res["text"])
            ok = False
    print("=" * 72)
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--plan-only", action="store_true",
                        help="nur Projekt + Kandidatenzaehlung, kein LLM")
    parser.add_argument("--export-only", action="store_true",
                        help="nur Artefakte aus vorhandenem Projektbestand")
    parser.add_argument("--poll-interval", type=float, default=10.0)
    args = parser.parse_args()

    project_id = ensure_project()

    if args.plan_only:
        # Job starten und pollen, bis die Kandidatenableitung (total_pairs)
        # steht, dann pausieren -> keine LLM-Kosten. Das Embedding von 1302
        # Hub-Konzepten braucht laenger als ein fixes sleep.
        mapping_service.reload(project_id)
        for sat in (ECF, DQR):
            job_id = classification_service.start_classification_job(sat, HUB, project_id=project_id)
            deadline = time.time() + 600
            prog = classification_service.get_job_progress(job_id, project_id=project_id)
            while time.time() < deadline:
                prog = classification_service.get_job_progress(job_id, project_id=project_id)
                if prog.get("total_pairs") or prog["status"] in (
                    "completed", "failed", "paused", "interrupted"
                ):
                    break
                time.sleep(5.0)
            try:
                classification_service.pause_job(job_id, project_id=project_id)
            except (ValueError, KeyError):
                pass  # Job bereits fertig (z. B. dqr_3 container_only -> 0 Paare)
            time.sleep(1.0)
            prog = classification_service.get_job_progress(job_id, project_id=project_id)
            print(f"  {sat:24s} total_pairs={prog['total_pairs']}  "
                  f"container={prog.get('container_concepts')}  "
                  f"skeleton={prog.get('skeleton_concepts')}  status={prog['status']}")
        return

    if args.export_only:
        jobs = {j["kqr_a_id"]: j for j in classification_service.list_jobs(project_id=project_id)}
    else:
        jobs = run_pipeline(project_id, poll_s=args.poll_interval)

    bundle = do_export(project_id)
    ok = stats_block(project_id, jobs, bundle)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
