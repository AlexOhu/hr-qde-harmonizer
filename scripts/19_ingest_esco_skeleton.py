"""
Nimmt die gelieferte ESCO-Referenzmenge ``esco-skeleton-for-oberhuber.ttl``
(1302 Skill-Konzepte) als Hub-KQR in die
Pipeline auf.

  - kopiert nach ``data/formalized/esco_skeleton_oberhuber.ttl``
  - ergaenzt je ``skos:Concept`` den kanonischen RDF-Typ
    ``harm:CompetenceConcept``
    (Parität zum bisherigen Hub; ``filter_by_scope`` behandelt Knoten ohne
    Rolle ohnehin als Pipeline-Konzept, die Rolle macht die Absicht explizit)
  - traegt den KQR in ``data/kqr_registry.json`` ein (``is_hub: true``)

Kanonische ``http://data.europa.eu/esco/skill/{uuid}``-URIs bleiben
unveraendert -- nur mit ihnen verbindet sich die Lieferung im HR-QDE-Graphen
(Shape ``HubMappingShape``). Textbasiertes Einfuegen, damit Reihenfolge und
Formatierung erhalten bleiben. Idempotent.

    python scripts/19_ingest_esco_skeleton.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "esco-skeleton-for-oberhuber.ttl"
DST = ROOT / "data" / "formalized" / "esco_skeleton_oberhuber.ttl"
REGISTRY = ROOT / "data" / "kqr_registry.json"

KQR_ID = "esco_skeleton_oberhuber"
NAMESPACE_URI = "http://data.europa.eu/esco/skill/"
HARM_PREFIX = "@prefix harm: <http://hr-qde.org/harmonised/> .\n"
ROLE_LINE = "  a harm:CompetenceConcept ;\n"


def _formalize(text: str) -> tuple[str, int]:
    if "a harm:CompetenceConcept" in text:
        return text, 0
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    inserted = 0
    prefixes_done = False
    for line in lines:
        if not prefixes_done and line.startswith("@prefix") and "harm:" not in line:
            out.append(line)
            continue
        if not prefixes_done and not line.startswith("@prefix"):
            out.append(HARM_PREFIX)
            prefixes_done = True
        out.append(line)
        if line.strip() == "a skos:Concept ;":
            out.append(ROLE_LINE)
            inserted += 1
    return "".join(out), inserted


def _register() -> None:
    entries = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if any(e.get("id") == KQR_ID for e in entries):
        print(f"kqr_registry.json traegt {KQR_ID} bereits.")
        return
    for entry in entries:
        entry["is_hub"] = False
    concept_count = DST.read_text(encoding="utf-8").count("a skos:Concept ;")
    entries.append({
        "id": KQR_ID,
        "name": "ESCO-Skelett fuer Oberhuber (Informatik-Korridor)",
        "namespace_uri": NAMESPACE_URI,
        "source_format": "turtle",
        "status": "bereit",
        "concept_count": concept_count,
        "is_hub": True,
    })
    REGISTRY.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"kqr_registry.json: {KQR_ID} eingetragen ({concept_count} Konzepte, is_hub).")


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Quelle fehlt: {SRC}")
    formalized, inserted = _formalize(SRC.read_text(encoding="utf-8"))
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(formalized, encoding="utf-8")
    print(f"{DST.name}: geschrieben, harm:CompetenceConcept an {inserted} Konzepten ergaenzt.")
    _register()


if __name__ == "__main__":
    main()
