"""Setzt das Cognitive-Walkthrough-Projekt vor jeder neuen Sitzung auf den
bekannten Ausgangszustand zurueck (walkthrough-baseline). Wiederholbar,
idempotent, veraendert NICHTS ausserhalb dieses einen Projektordners und
NICHTS in Neo4j (dortige Konzept-Knoten sind statische Referenzdaten, keine
Teilnehmer-Mutation).

Zurueckgesetzt werden:
  - mappings.json         -> neu aus data/projects/default/mappings.json
                              gefiltert (Quelle der Wahrheit, unveraendert
                              seit der urspruenglichen Slice-Erstellung)
  - classification_jobs.json -> ein frischer, abgeschlossener Job-Eintrag
  - disjoint_decisions.json  -> leer (jede Sitzung startet ohne
                              vorherige Integrationsentscheidungen)
  - clusters.json / clusters_dag.json -> entfernt, damit "Clustering
                              starten" fuer die naechste Person wieder ein
                              echter erster Durchlauf ist, kein bereits
                              vorliegendes Ergebnis
  - audit/, ontology/, sssom/ -> Inhalte geleert (Artefakte aus frueheren
                              Export-Klicks sollen nicht liegen bleiben)
"""

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ID = "cognitive_walkthrough_dqr_l6_mini_kqr_20260825T201601Z"
PROJECT_DIR = Path(f"data/projects/{PROJECT_ID}")
DQR_KQR_ID = "dqr_l6_walkthrough_slice"
ESCO_KQR_ID = "esco_ikt_walkthrough_slice"

TARGET_SUBJECTS = {
    "http://data.bmbf.de/dqr/L6_Knowledge",
    "http://data.bmbf.de/dqr/L6_Skills",
    "http://data.bmbf.de/dqr/L6_SocialCompetence",
    "http://data.bmbf.de/dqr/L6_Autonomy",
}


def reset_mappings():
    source = json.load(open("data/projects/default/mappings.json", encoding="utf-8"))
    subset = [r for r in source if r["subject_id"] in TARGET_SUBJECTS]
    for r in subset:
        r["subject_kqr_id"] = DQR_KQR_ID
        r["object_kqr_id"] = ESCO_KQR_ID
    json.dump(subset, open(PROJECT_DIR / "mappings.json", "w", encoding="utf-8"),
               indent=2, ensure_ascii=False)
    print(f"mappings.json zurueckgesetzt: {len(subset)} Records")
    return len(subset)


def reset_classification_jobs(n_pairs):
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    jobs = {job_id: {
        "job_id": job_id, "kqr_a_id": DQR_KQR_ID, "kqr_b_id": ESCO_KQR_ID,
        "status": "completed", "total_pairs": n_pairs, "done_pairs": n_pairs,
        "created_at": now, "updated_at": now,
    }}
    json.dump(jobs, open(PROJECT_DIR / "classification_jobs.json", "w", encoding="utf-8"),
               indent=2, ensure_ascii=False)
    print("classification_jobs.json zurueckgesetzt: 1 Job")


def reset_disjoint_decisions():
    json.dump([], open(PROJECT_DIR / "disjoint_decisions.json", "w", encoding="utf-8"))
    print("disjoint_decisions.json geleert")


def reset_clusters():
    for name in ["clusters.json", "clusters_dag.json"]:
        f = PROJECT_DIR / name
        if f.exists():
            f.unlink()
            print(f"{name} entfernt")
        else:
            print(f"{name} war bereits nicht vorhanden")


def clear_artifact_dirs():
    for name in ["audit", "ontology", "sssom"]:
        d = PROJECT_DIR / name
        if d.exists():
            for f in d.iterdir():
                if f.is_file():
                    f.unlink()
            print(f"{name}/ geleert")


if __name__ == "__main__":
    print(f"Setze Projekt zurueck: {PROJECT_ID}\n")
    n = reset_mappings()
    reset_classification_jobs(n)
    reset_disjoint_decisions()
    reset_clusters()
    clear_artifact_dirs()
    print("\nFertig. Bereit fuer die naechste Sitzung.")
