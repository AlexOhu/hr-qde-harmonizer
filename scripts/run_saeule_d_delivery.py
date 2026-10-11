"""
Abgabepfad Saeule D: Export gegen die gelieferte ESCO-Referenzmenge
(``esco_skeleton_oberhuber``, 1302 Skills) und Erzeugung der drei
Lieferartefakte.

  Paar 1  e-CF  <-> ESCO-Skelett   scope=all            -> volle Pipeline
  Paar 2  e-CF-Dimension-3 <-> dqr_1d -> deterministischer Level-Shortcut

Ergebnis (in ``data/projects/<pid>/delivery/``, Kopie samt run_config.json
unter ``data/deliverables/v{V}-{JJJJMMTT}/``):
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
ECF_LEVEL = "ecf_level"
DQR = "dqr_1d"
KQR_SCOPES = {ECF: "all"}
PROJECT_NAME = "Saeule D Lieferung (Informatik-Korridor)"
VERSION = "0.3"

SHAPE = ROOT / "hrqde-shape-harmonisation.ttl"
SCHEMA = ROOT / "hrqde-harmonisation-schema.ttl"

LIMITATIONS_FIXED = [
    "Offene Reviews (RELATED/UNRESOLVED) fallen aus den Artefakten; die "
    "Einzelentscheidungen stehen aus (Coverage-Nenner beruecksichtigt sie).",
    "Kein `harm:HarmonisedCluster`: HDBSCAN erreichte keine navigierbare "
    "Hierarchie (Negativbefund, Kapitel 6).",
    "Die e-CF-Dimension-3-zu-DQR-Mappings sind normative, deterministische "
    "LevelMappings aus e-CF 3.0 (CWA 16234-1:2014), kein LLM-Ergebnis.",
]


def build_limitations(project_id: str) -> list[str]:
    """Feste Einschraenkungen plus eine am Ergebnis gemessene Aussage zu
    EQUIVALENT, damit der Text nie etwas behauptet, das die Daten des Laufs
    nicht tragen."""
    results = mapping_service._get_classification_results(project_id)
    n_equiv = sum(1 for r in results if r.final_relation and r.final_relation.value == "EQUIVALENT")
    if n_equiv == 0:
        equiv = ("Kein `EQUIVALENT`-Mapping im Gesamtdatensatz: Das Klassifikationsmodell "
                 "ordnet keines der Paare als aequivalent ein (Kapitel 5 und 6).")
    else:
        equiv = (f"Nur {n_equiv} von {len(results)} klassifizierten Paaren erhielten "
                 "`EQUIVALENT`; die Erkennung von Aequivalenz bleibt unzuverlaessig "
                 "(Kapitel 5 und 6).")
    return [*LIMITATIONS_FIXED, disjoint_limitation(project_id), equiv]


def disjoint_limitation(project_id: str) -> str:
    """Aussage zu den Integrationsentscheidungen, gemessen am Projektbestand.
    Ohne gespeicherte Entscheidung schreibt der Export die Rueckfallstrategie
    `own_class`; das ist kein Vorschlag von suggest_strategy()."""
    disjoint = [c for c in disjoint_service.list_disjoint_concepts_for_pair(
        ECF, HUB, project_id=project_id) if c.kqr_id == ECF]
    decided = {d.concept_id: d for d in disjoint_service.list_decisions(project_id)}
    n_total = len(disjoint)
    n_decided = sum(1 for c in disjoint if c.uri in decided)
    if n_total == 0:
        return "Keine disjunkten e-CF-Konzepte im Paar e-CF <-> ESCO-Skelett."
    if n_decided == n_total:
        authors = sorted({decided[c.uri].author for c in disjoint})
        return (f"Die Integrationsstrategien der {n_total} disjunkten e-CF-Konzepte sind "
                f"einzeln entschieden und begruendet (Autor: {', '.join(authors)}). "
                "Das Schema kennt keine eigene Property fuer die Ankerklasse; sie steht "
                "im `rdfs:comment` des `harm:HarmonisedConcept` und in Abschnitt 2.")
    return (f"{n_total - n_decided} von {n_total} disjunkten e-CF-Konzepten haben keine "
            "gespeicherte Integrationsentscheidung und tragen die Rueckfallstrategie "
            "`own_class` des Exports, nicht den Vorschlag von "
            "`disjoint_service.suggest_strategy`.")


def _dirty_count() -> int | str:
    """Anzahl uncommitteter Aenderungen an getrackten Dateien (der Lauf gilt
    fuer den Stand der Arbeitskopie, nicht nur fuer den Commit)."""
    import subprocess

    try:
        out = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=no"],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout
        return len(out.splitlines())
    except Exception:
        return "unbekannt"


def write_run_config(project_id: str) -> Path:
    """Haelt die Konfiguration des Laufs neben den Lieferdateien fest."""
    import hashlib
    import json
    import subprocess
    from datetime import datetime, timezone

    from app.config import settings

    template = ROOT / "prompts" / "classification_prompt_template.txt"
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.strip()
    except Exception:
        commit = "unbekannt"
    cfg = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "project_name": PROJECT_NAME,
        "version": VERSION,
        "git_head": commit,
        "git_dirty_tracked_files": _dirty_count(),
        "llm_providers": settings.llm_providers,
        "mistral_model": settings.mistral_model,
        "classification_temperature": settings.classification_temperature,
        "classification_runs_per_pair": settings.classification_runs_per_pair,
        "ann_top_k": settings.ann_top_k,
        "embedding_model": settings.embedding_model,
        "prompt_template_sha256_16": hashlib.sha256(template.read_bytes()).hexdigest()[:16],
        "few_shot": "aus Struktur-Shortcuts des Paares (e-CF <-> ESCO-Skelett: 0 Treffer, "
                    "Prompt-Text '(keine Crosswalk-Beispiele verfuegbar)')",
    }
    out_dir = project_service.get_project_data_dir(project_id) / "delivery"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "run_config.json"
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def ensure_project() -> str:
    for project in project_service.list_projects():
        if project.name == PROJECT_NAME:
            print(f"Projekt vorhanden: {project.project_id}")
            return project.project_id
    project = project_service.create_project(
        name=PROJECT_NAME,
        kqr_ids=[HUB, ECF, ECF_LEVEL, DQR],
        kqr_scopes=KQR_SCOPES,
        description=(
            "Abgabepfad Saeule D. Hub = esco_skeleton_oberhuber (1302 Skills, "
            "gelieferte Referenzmenge). e-CF scope=all durch die volle "
            "Pipeline; Dimension 3 wird deterministisch gegen dqr_1d materialisiert. "
            f"Grundlage fuer oberhuber-harmonised-ontology-v{VERSION}.ttl."
        ),
        hub_kqr_id=HUB,
    )
    print(f"Projekt angelegt: {project.project_id}  (kqr_scopes={KQR_SCOPES})")
    return project.project_id


def run_pipeline(project_id: str, poll_s: float) -> dict[str, dict]:
    mapping_service.reload(project_id)
    final: dict[str, dict] = {}
    for sat in (ECF,):
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
    ecf_graph = kqr_service.get_graph(ECF_LEVEL)
    disjoint_decisions = disjoint_service.list_decisions(project_id)
    coverage = mapping_service.get_coverage_summary(project_id=project_id)

    out_dir = project_service.get_project_data_dir(project_id) / "delivery"
    bundle = write_delivery(
        out_dir, ecf_graph, k_mappings, disjoint_decisions,
        coverage=coverage, limitations=build_limitations(project_id), version=VERSION,
    )
    # Snapshot unter data/deliverables/ (versioniert), nicht im Repo-Root.
    from datetime import datetime, timezone
    snapshot_dir = (ROOT / "data" / "deliverables"
                    / f"v{VERSION}-{datetime.now(timezone.utc):%Y%m%d}")
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for stats in bundle.values():
        dst = snapshot_dir / Path(stats["path"]).name
        shutil.copyfile(stats["path"], dst)
        stats["snapshot_copy"] = str(dst)
    export_config = write_export_config(project_id, bundle)
    for cfg in (out_dir / "run_config.json", export_config):
        if cfg.exists():
            shutil.copyfile(cfg, snapshot_dir / cfg.name)
    # data/projects/ ist nicht versioniert. Die Integrationsentscheidungen und
    # die Herkunft eines abgeleiteten Projekts gehoeren aber zur Provenienz der
    # Lieferung und werden deshalb neben die Artefakte kopiert.
    project_dir = project_service.get_project_data_dir(project_id)
    for name in ("disjoint_decisions.json", "derivation.json"):
        if (project_dir / name).exists():
            shutil.copyfile(project_dir / name, snapshot_dir / name)
    return bundle


def write_export_config(project_id: str, bundle: dict) -> Path:
    """Haelt den Stand des Exports fest. run_config.json beschreibt den
    Klassifikationslauf; bei --export-only (oder einem abgeleiteten Projekt)
    stammt sie aus einem frueheren Lauf und sagt nichts ueber den Code des
    Exports aus."""
    import json
    import subprocess
    from datetime import datetime, timezone

    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.strip()
    except Exception:
        commit = "unbekannt"
    project = project_service.get_project(project_id)
    decisions = disjoint_service.list_decisions(project_id)
    cfg = {
        "exported_utc": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "project_id": project_id,
        "project_name": project.name,
        "parent_project_id": project.parent_project_id,
        "git_head": commit,
        "git_dirty_tracked_files": _dirty_count(),
        "disjoint_decisions_in_project": len(decisions),
        "disjoint_decisions_in_delivery": bundle["integration_strategy"].get("disjoint_documented"),
        "harmonised_by_strategy": bundle["ontology"].get("harmonised_by_strategy"),
        "note": "run_config.json beschreibt den Klassifikationslauf, diese Datei den Export.",
    }
    path = project_service.get_project_data_dir(project_id) / "delivery" / "export_config.json"
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


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
    print(f"  {onto['snapshot_copy']}")
    print(f"  Tripel {onto['triples']}   e-CF-Konzepte {onto['ecf_concepts']} "
          f"(+ {onto['ecf_areas']} Bereiche), LevelConcept {onto.get('ecf_level_concepts', 0)} "
          f"   HarmonisedConcept {onto['harmonised_concepts']}")
    print(f"  Strategien: {onto['harmonised_by_strategy']}")
    print("\nARTEFAKT 2  Mappings")
    print(f"  {maps['snapshot_copy']}")
    print(f"  HubMapping {maps['hub_mappings']}  (>= 0,67: {maps['hub_mappings_above_threshold_067']})  "
          f"LevelMapping {maps['level_mappings']}  OccupationMapping {maps['occupation_mappings']}")
    print(f"  Praedikate: {maps['hub_mappings_by_predicate']}")
    print("\nARTEFAKT 3  Integrationsstrategie")
    print(f"  {strat['snapshot_copy']}")

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
    parser.add_argument("--project-name", default=None,
                        help="Projektname (Standard: Name des Abgabeprojekts v0.3). "
                             "Ein neuer Name legt ein neues Projekt an, das nichts "
                             "aus frueheren Klassifikationen wiederverwendet.")
    parser.add_argument("--version", default=None,
                        help="Lieferversion (Standard 0.3)")
    args = parser.parse_args()

    global PROJECT_NAME, VERSION
    if args.project_name:
        PROJECT_NAME = args.project_name
    if args.version:
        VERSION = args.version

    project_id = ensure_project()
    if not args.plan_only and not args.export_only:
        print(f"Laufkonfiguration: {write_run_config(project_id)}")

    if args.plan_only:
        # Job starten und pollen, bis die Kandidatenableitung (total_pairs)
        # steht, dann pausieren -> keine LLM-Kosten. Das Embedding von 1302
        # Hub-Konzepten braucht laenger als ein fixes sleep.
        mapping_service.reload(project_id)
        for sat in (ECF,):
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
