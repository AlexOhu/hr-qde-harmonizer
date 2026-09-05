"""
Startet die Klassifikationslaeufe fuer das Projekt
"HR-QDE Basisontologie - IKT Slice" ueber die laufende API.

Drei Paare, Hub jeweils esco_v1_2_ict_ausschnitt:
    ecf      <-> esco_v1_2_ict_ausschnitt
    dqr_2    <-> esco_v1_2_ict_ausschnitt
    eqf_2017 <-> esco_v1_2_ict_ausschnitt

Parameter wie im default-Projekt (ANN_TOP_K=20, CLASSIFICATION_RUNS_PER_PAIR
aus .env). Der Prompt enthaelt den Richtungs-Fix (Befund 1/2 vom 2026-08-29).

Voraussetzung: API laeuft
    uvicorn app.api.main:app --reload
Kein LLM-Aufruf ohne gesetzten MISTRAL_API_KEY (LLM_PROVIDERS=mistral).

Beispiele:
    python scripts/run_ikt_slice.py                 # sequenziell, alle 3 Paare
    python scripts/run_ikt_slice.py --parallel      # 3 Hintergrundjobs gleichzeitig
    python scripts/run_ikt_slice.py --satellites ecf   # nur ein Paar
    python scripts/run_ikt_slice.py --dry-run        # nur Vorbedingungen pruefen
"""

from __future__ import annotations

import argparse
import sys
import time

import httpx

PROJECT_ID = "hr_qde_basisontologie_ikt_slice_20260830T050546Z"
HUB_ID = "esco_v1_2_ict_ausschnitt"
SATELLITES = ["ecf", "dqr_2", "eqf_2017"]


def _check(base_url: str, project_id: str, hub_id: str, satellites: list[str]) -> None:
    """Bricht mit Exit-Code 1 ab, wenn eine Vorbedingung fehlt."""
    ok = True

    pre = httpx.get(f"{base_url}/classification/preconditions", timeout=30).json()
    print(f"Vorbedingungen: llm_configured={pre['llm_configured']} "
          f"(providers={pre['llm_providers']}), neo4j_reachable={pre['neo4j_reachable']}")
    if not pre["llm_configured"]:
        print("  FEHLER: kein LLM-Provider konfiguriert (API-Key in .env fehlt).", file=sys.stderr)
        ok = False

    resp = httpx.get(f"{base_url}/projects/{project_id}", timeout=30)
    if resp.status_code != 200:
        print(f"  FEHLER: Projekt '{project_id}' nicht gefunden (HTTP {resp.status_code}).", file=sys.stderr)
        raise SystemExit(1)
    project = resp.json()
    print(f"Projekt: {project['name']}  (kqr_ids={project['kqr_ids']}, hub={project['hub_kqr_id']})")

    for kqr_id in [hub_id, *satellites]:
        r = httpx.get(f"{base_url}/kqr/{kqr_id}/status", timeout=30)
        if r.status_code != 200:
            print(f"  FEHLER: KQR '{kqr_id}' nicht registriert.", file=sys.stderr)
            ok = False
            continue
        kqr = r.json()["kqr"]
        flag = "OK" if kqr["status"] == "bereit" else "NICHT BEREIT"
        print(f"  {kqr_id}: status={kqr['status']} concepts={kqr.get('concept_count')}  [{flag}]")
        if kqr["status"] != "bereit":
            ok = False

    if not ok:
        raise SystemExit(1)


def _start_pair(base_url: str, project_id: str, satellite_id: str, hub_id: str) -> str:
    resp = httpx.post(
        f"{base_url}/classification/start",
        params={"kqr_a_id": satellite_id, "kqr_b_id": hub_id, "project_id": project_id},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["job_id"]


def _progress(base_url: str, project_id: str, job_id: str) -> dict:
    resp = httpx.get(
        f"{base_url}/classification/{job_id}/progress",
        params={"project_id": project_id},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _wait(base_url: str, project_id: str, jobs: dict[str, str], poll_interval: float) -> dict[str, dict]:
    """jobs: {satellite_id: job_id}. Pollt, bis alle completed/failed sind."""
    final: dict[str, dict] = {}
    pending = dict(jobs)
    while pending:
        for satellite_id, job_id in list(pending.items()):
            job = _progress(base_url, project_id, job_id)
            print(f"  [{satellite_id}] {job['done_pairs']}/{job['total_pairs']} "
                  f"({job['percent']}%) status={job['status']}")
            if job["status"] in ("completed", "failed"):
                final[satellite_id] = job
                pending.pop(satellite_id)
        if pending:
            time.sleep(poll_interval)
    return final


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--project-id", default=PROJECT_ID)
    parser.add_argument("--hub", default=HUB_ID)
    parser.add_argument("--satellites", default=",".join(SATELLITES),
                        help="kommagetrennte Satelliten-KQR-IDs")
    parser.add_argument("--parallel", action="store_true",
                        help="alle Paare als gleichzeitige Hintergrundjobs (Default: sequenziell)")
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--dry-run", action="store_true", help="nur Vorbedingungen pruefen")
    args = parser.parse_args()

    satellites = [s.strip() for s in args.satellites.split(",") if s.strip()]

    _check(args.base_url, args.project_id, args.hub, satellites)
    if args.dry_run:
        print("\nDry-Run: Vorbedingungen erfuellt. Kein Job gestartet.")
        return

    results: dict[str, dict] = {}

    if args.parallel:
        jobs = {sat: _start_pair(args.base_url, args.project_id, sat, args.hub) for sat in satellites}
        for sat, job_id in jobs.items():
            print(f"Gestartet: {sat} <-> {args.hub}  job_id={job_id}")
        results = _wait(args.base_url, args.project_id, jobs, args.poll_interval)
    else:
        for sat in satellites:
            job_id = _start_pair(args.base_url, args.project_id, sat, args.hub)
            print(f"\nGestartet: {sat} <-> {args.hub}  job_id={job_id}")
            results.update(_wait(args.base_url, args.project_id, {sat: job_id}, args.poll_interval))

    print("\n=== Zusammenfassung ===")
    failed = False
    for sat in satellites:
        job = results.get(sat, {})
        status = job.get("status", "?")
        print(f"  {sat:10s} {job.get('done_pairs', '?')}/{job.get('total_pairs', '?')} "
              f"Paare  status={status}")
        if status == "failed":
            failed = True
            print(f"    Fehler: {job.get('error')}")

    print(f"\nErgebnisse unter data/projects/{args.project_id}/")
    print("Naechste Schritte:")
    print(f"  - SSSOM:   curl -X POST '{args.base_url}/export/sssom?project_id={args.project_id}'")
    print(f"  - Summary: curl '{args.base_url}/export/summary?project_id={args.project_id}'")
    print("  - Richtungs-Check erneut laufen lassen (analyze2.py auf die neue mappings.json)")

    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
