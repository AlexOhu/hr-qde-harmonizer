"""Extrahiert die beiden Mini-KQR-Dateien fuer den Cognitive-Walkthrough-
Slice mit vollstaendigen SKOS-Feldern (prefLabel + definition), damit
validate_formalization(strict=False) und parse_concepts() sie akzeptieren,
und registriert beide ueber die laufende API (POST /kqr/)."""

import json
import urllib.request

from rdflib import RDF, SKOS, Graph, URIRef

API = "http://127.0.0.1:8000"

DQR_LOCALS = ["L6_Knowledge", "L6_Skills", "L6_SocialCompetence", "L6_Autonomy"]

targets = {
    "http://data.bmbf.de/dqr/L6_Knowledge",
    "http://data.bmbf.de/dqr/L6_Skills",
    "http://data.bmbf.de/dqr/L6_SocialCompetence",
    "http://data.bmbf.de/dqr/L6_Autonomy",
}
mappings = json.load(open("data/projects/default/mappings.json", encoding="utf-8"))
subset = [r for r in mappings if r["subject_id"] in targets]
esco_uris = sorted({r["object_id"] for r in subset})
print("ESCO-Ziel-URIs:", len(esco_uris))

# --- DQR-Mini-KQR extrahieren ---
g_dqr = Graph()
g_dqr.parse("data/formalized/dqr_2.ttl", format="turtle")

dqr_out = Graph()
dqr_out.bind("skos", SKOS)
for local in DQR_LOCALS:
    uri = URIRef(f"http://data.bmbf.de/dqr/{local}")
    for p, o in g_dqr.predicate_objects(uri):
        dqr_out.add((uri, p, o))
dqr_ttl = dqr_out.serialize(format="turtle")
open("data/walkthrough_slice/mini_kqr_dqr_l6.ttl", "w", encoding="utf-8").write(dqr_ttl)
print("DQR-Mini-KQR geschrieben,", len(list(dqr_out.subjects(RDF.type, SKOS.Concept))), "Konzepte")

# --- ESCO-Mini-KQR extrahieren ---
g_esco = Graph()
g_esco.parse("data/raw/esco_v1_2_ict_ausschnitt.ttl", format="turtle")

esco_out = Graph()
esco_out.bind("skos", SKOS)
for uri_str in esco_uris:
    uri = URIRef(uri_str)
    for p, o in g_esco.predicate_objects(uri):
        esco_out.add((uri, p, o))
    esco_out.add((uri, RDF.type, SKOS.Concept))
esco_ttl = esco_out.serialize(format="turtle")
open("data/walkthrough_slice/mini_kqr_esco_ict.ttl", "w", encoding="utf-8").write(esco_ttl)
print("ESCO-Mini-KQR geschrieben,", len(list(esco_out.subjects(RDF.type, SKOS.Concept))), "Konzepte")

def post_kqr(name, path, is_hub=False):
    import mimetypes
    boundary = "----walkthrough_boundary"
    content = open(path, "rb").read()
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"name\"\r\n\r\n{name}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"source_format\"\r\n\r\nturtle\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"is_hub\"\r\n\r\n{str(is_hub).lower()}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.split('/')[-1]}\"\r\n"
        f"Content-Type: text/turtle\r\n\r\n"
    ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        f"{API}/kqr/", data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

dqr_kqr = post_kqr("DQR L6 Walkthrough Slice", "data/walkthrough_slice/mini_kqr_dqr_l6.ttl")
print("registriert:", dqr_kqr["id"], dqr_kqr["status"], dqr_kqr["concept_count"])

esco_kqr = post_kqr("ESCO IKT Walkthrough Slice", "data/walkthrough_slice/mini_kqr_esco_ict.ttl", is_hub=True)
print("registriert:", esco_kqr["id"], esco_kqr["status"], esco_kqr["concept_count"])

# --- Projekt neu aufsetzen, alte, zu breite Instanz ersetzen ---
import sys
sys.path.insert(0, ".")
from app.services import project_service

# Alte Instanz (an dqr_2/esco_v1_2_ict_ausschnitt in voller Breite) entsorgen
old_id = "cognitive_walkthrough_dqr_l6_20260825T200655Z"
project_service.delete_project(old_id) if hasattr(project_service, "delete_project") else None

proj = project_service.create_project(
    name="Cognitive Walkthrough DQR-L6 (Mini-KQR)",
    kqr_ids=[esco_kqr["id"], dqr_kqr["id"]],
    description="Isolierte Walkthrough-Instanz, nur die 51 relevanten ESCO- und 4 DQR-Level-6-Konzepte, keine ungemappten Fremdkonzepte.",
    hub_kqr_id=esco_kqr["id"],
)
print("Neues Projekt:", proj.project_id)

# Mappings kopieren, subject_kqr_id/object_kqr_id auf die neuen Mini-KQR-IDs ummuenzen
for r in subset:
    r["subject_kqr_id"] = dqr_kqr["id"]
    r["object_kqr_id"] = esco_kqr["id"]

out_dir = f"data/projects/{proj.project_id}"
json.dump(subset, open(f"{out_dir}/mappings.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

import uuid
from datetime import datetime, timezone
job_id = str(uuid.uuid4())
now = datetime.now(timezone.utc).isoformat()
jobs = {job_id: {
    "job_id": job_id, "kqr_a_id": dqr_kqr["id"], "kqr_b_id": esco_kqr["id"],
    "status": "completed", "total_pairs": len(subset), "done_pairs": len(subset),
    "created_at": now, "updated_at": now,
}}
json.dump(jobs, open(f"{out_dir}/classification_jobs.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("Mappings + Job geschrieben:", len(subset), "Records")
