"""
Fuehrt Funktionsgruppe 2 (Klassifikationsprozess steuern) end-to-end ueber
die laufende API aus: registriert Hub (data/formalized/esco.ttl) und
Satellit (tests/fixtures/satellite_kqr.ttl) sofern noch nicht in der
Registry vorhanden, startet POST /classification/start, pollt den
Fortschritt (GET /classification/{job_id}/progress) und laedt anschliessend
den SSSOM-Export (POST /export/sssom) fuer eine Stichprobenauswertung.

Hub und Satellit werden unter den Namen "esco" bzw. "satellite" registriert,
sodass _slugify() in kqr_service diese exakten IDs vergibt (vgl.
scripts/04_register_kqrs.py fuer das Registrierungsmuster).

Hinweis: /export/sssom liefert die vollstaendige, kumulative Mapping-Liste
(inkl. etwaiger Ergebnisse frueherer Laeufe in derselben API-Instanz) --
fuer eine isolierte Auswertung API vor dem Lauf neu starten.

Voraussetzung: API laeuft (uvicorn app.api.main:app --reload).
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
FORMALIZED_DIR = ROOT / "data" / "formalized"
FIXTURES_DIR = ROOT / "tests" / "fixtures"

HUB_ID = "esco_v1_2_ict_ausschnitt"
HUB_FILE = FORMALIZED_DIR / "esco.ttl"
SATELLITE_ID = "satellite"
SATELLITE_FILE = FIXTURES_DIR / "satellite_kqr.ttl"


def _ensure_registered(base_url: str, kqr_id: str, path: Path, is_hub: bool) -> str:
    """Registriert den KQR unter dem Namen `kqr_id` (-> _slugify vergibt die
    gleichlautende id), sofern er nicht schon in der Registry steht."""
    existing = httpx.get(f"{base_url}/kqr/", timeout=30).json()
    match = next((k for k in existing if k["id"] == kqr_id), None)
    if match is not None:
        print(
            f"{kqr_id}: bereits registriert "
            f"(status={match['status']}, concepts={match.get('concept_count')})"
        )
        if match["status"] != "bereit":
            print(f"  Warnung: Status ist '{match['status']}', nicht 'bereit'.")
        return match["id"]

    if not path.exists():
        print(f"Fehler: {path} nicht gefunden.", file=sys.stderr)
        raise SystemExit(1)

    print(f"{kqr_id}: registriere {path.name} ueber POST /kqr/ (kann bei grossen Dateien dauern) ...")
    content = path.read_bytes()
    response = httpx.post(
        f"{base_url}/kqr/",
        data={"name": kqr_id, "source_format": "turtle", "is_hub": str(is_hub)},
        files={"file": (path.name, content, "text/turtle")},
        timeout=1800,
    )
    response.raise_for_status()
    kqr = response.json()
    print(f"  -> id={kqr['id']} status={kqr['status']} concepts={kqr.get('concept_count')}")
    return kqr["id"]


def _wait_until_ready(
    base_url: str, kqr_a_id: str, kqr_b_id: str, poll_interval: float = 5.0, max_attempts: int = 60
) -> None:
    """Wartet bis beide KQR Status 'bereit' melden (max. 5 Minuten), bevor
    POST /classification/start ausgeloest wird -- Embeddings koennen bei
    grossen KQR noch im Hintergrund der vorangegangenen Registrierung
    laufen. GET /kqr/{id}/status liefert den Status verschachtelt unter
    "kqr" (vgl. app/api/routes/kqr.py::get_status)."""
    for _ in range(max_attempts):
        resp_a = httpx.get(f"{base_url}/kqr/{kqr_a_id}/status", timeout=30)
        resp_b = httpx.get(f"{base_url}/kqr/{kqr_b_id}/status", timeout=30)
        resp_a.raise_for_status()
        resp_b.raise_for_status()

        status_a = resp_a.json()["kqr"]["status"]
        status_b = resp_b.json()["kqr"]["status"]

        if status_a == "bereit" and status_b == "bereit":
            print("Beide KQR bereit.")
            return
        print(f"  {kqr_a_id}: {status_a}, {kqr_b_id}: {status_b} -- warte...")
        time.sleep(poll_interval)

    print("Timeout: Ein KQR ist nach 5 Min immer noch nicht bereit.", file=sys.stderr)
    raise SystemExit(1)


def _wait_for_completion(base_url: str, job_id: str, poll_interval: float) -> dict:
    while True:
        response = httpx.get(f"{base_url}/classification/{job_id}/progress", timeout=30)
        response.raise_for_status()
        job = response.json()
        print(f"  ... {job['done_pairs']}/{job['total_pairs']} Paare klassifiziert ({job['percent']}%)")
        if job["status"] in ("completed", "failed"):
            return job
        time.sleep(poll_interval)


def _print_confidence_stats(rows: list[dict]) -> None:
    if not rows:
        print("\nKeine SSSOM-Records vorhanden.")
        return

    confidences = [float(r["mapping_confidence"]) for r in rows]
    ranked = sorted(rows, key=lambda r: float(r["mapping_confidence"]), reverse=True)

    print("\nTop 5 Mappings (hoechste Konfidenz):")
    for r in ranked[:5]:
        print(f"  {float(r['mapping_confidence']):.3f}  {r['subject_label']} -> {r['object_label']}  ({r['predicate_id']})")

    print("\nUnterste 5 Mappings (niedrigste Konfidenz):")
    for r in ranked[-5:][::-1]:
        print(f"  {float(r['mapping_confidence']):.3f}  {r['subject_label']} -> {r['object_label']}  ({r['predicate_id']})")

    print("\nConfidence-Verteilung:")
    print(
        f"  n={len(confidences)}  min={min(confidences):.3f}  max={max(confidences):.3f}  "
        f"mean={statistics.mean(confidences):.3f}  median={statistics.median(confidences):.3f}"
    )
    buckets = [0] * 5
    for c in confidences:
        buckets[min(int(c * 5), 4)] += 1
    for i, count in enumerate(buckets):
        lo, hi = i / 5, (i + 1) / 5
        print(f"  [{lo:.1f}-{hi:.1f}) {'#' * count} ({count})")


def _require_registered(base_url: str, kqr_id: str) -> str:
    """Prueft ueber GET /kqr/{id}/status, dass `kqr_id` bereits in der
    Registry existiert (im Gegensatz zu _ensure_registered wird hier nichts
    nachregistriert -- fuer Paare, die schon per 04_register_kqrs.py o.ae.
    angelegt wurden)."""
    resp = httpx.get(f"{base_url}/kqr/{kqr_id}/status", timeout=30)
    if resp.status_code == 404:
        print(f"Fehler: KQR '{kqr_id}' ist nicht registriert.", file=sys.stderr)
        raise SystemExit(1)
    resp.raise_for_status()
    kqr = resp.json()["kqr"]
    print(f"{kqr_id}: registriert (status={kqr['status']}, concepts={kqr.get('concept_count')})")
    return kqr["id"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API-Basis-URL")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Sekunden zwischen Fortschrittsabfragen")
    parser.add_argument(
        "--kqr-a", default=None,
        help="ID eines bereits registrierten KQR (statt des fest kodierten esco-Hub). "
             "Nur zusammen mit --kqr-b verwendbar.",
    )
    parser.add_argument(
        "--kqr-b", default=None,
        help="ID eines bereits registrierten KQR (statt des fest kodierten Satelliten). "
             "Nur zusammen mit --kqr-a verwendbar.",
    )
    args = parser.parse_args()

    if bool(args.kqr_a) != bool(args.kqr_b):
        parser.error("--kqr-a und --kqr-b muessen zusammen angegeben werden.")

    if args.kqr_a and args.kqr_b:
        hub_id = _require_registered(args.base_url, args.kqr_a)
        satellite_id = _require_registered(args.base_url, args.kqr_b)
    else:
        hub_id = _ensure_registered(args.base_url, HUB_ID, HUB_FILE, is_hub=True)
        satellite_id = _ensure_registered(args.base_url, SATELLITE_ID, SATELLITE_FILE, is_hub=False)

    _wait_until_ready(args.base_url, satellite_id, hub_id)

    print(f"\nStarte Klassifikation ({satellite_id} <-> {hub_id}) ueber POST /classification/start ...")
    start_resp = httpx.post(
        f"{args.base_url}/classification/start",
        params={"kqr_a_id": satellite_id, "kqr_b_id": hub_id},
        timeout=30,
    )
    start_resp.raise_for_status()
    job_id = start_resp.json()["job_id"]
    print(f"  job_id={job_id}")

    job = _wait_for_completion(args.base_url, job_id, args.poll_interval)
    if job["status"] == "failed":
        print(f"\nJob fehlgeschlagen: {job.get('error')}", file=sys.stderr)
        raise SystemExit(1)

    candidate_pairs = job["total_pairs"]
    classified = job["done_pairs"]

    print("\nExportiere SSSOM ueber POST /export/sssom ...")
    export_resp = httpx.post(f"{args.base_url}/export/sssom", timeout=60)
    export_resp.raise_for_status()

    content_disposition = export_resp.headers.get("content-disposition", "")
    filename = content_disposition.split("filename=")[-1].strip('"') or "export.tsv"
    output_path = ROOT / "data" / "sssom" / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(export_resp.content)

    rows = list(csv.DictReader(output_path.read_text(encoding="utf-8").splitlines(), delimiter="\t"))

    print(
        f"\n{candidate_pairs} Candidate Pairs gefunden, {classified} Mappings klassifiziert, "
        f"{len(rows)} SSSOM-Records erstellt (-> {output_path.relative_to(ROOT)})"
    )

    _print_confidence_stats(rows)


if __name__ == "__main__":
    main()
