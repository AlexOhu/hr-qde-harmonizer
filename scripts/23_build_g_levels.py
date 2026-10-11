"""Build the normative G_levels gold set from the e-CF/DQR Turtle files."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from rdflib import Graph, Namespace, RDF


ROOT = Path(__file__).resolve().parents[1]
ECF_PATH = ROOT / "data/raw/ecf_levelproposal_crosswalk.ttl"
DQR_PATH = ROOT / "data/formalized/dqr_1d.ttl"
OUTPUT_PATH = ROOT / "eval/G_levels.json"
README_PATH = ROOT / "eval/README.md"

HARM = Namespace("http://hr-qde.org/harmonised/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
ECF_PREFIX = "http://hr-qde.org/harmonised/source/ecf/"
DQR_PREFIX = "http://hr-qde.org/harmonised/source/dqr/"


def read_level_nodes() -> dict[str, str]:
    graph = Graph()
    graph.parse(ECF_PATH, format="turtle")
    level_nodes: dict[str, str] = {}

    for subject in graph.subjects(RDF.type, HARM.LevelConcept):
        identifiers = list(graph.objects(subject, HARM.sourceIdentifier))
        if len(identifiers) != 1:
            raise AssertionError(f"Expected one sourceIdentifier for {subject}")
        match = re.search(r"Niveau\s+([1-5])$", str(identifiers[0]))
        if match is None:
            raise AssertionError(f"Cannot derive proficiency from {identifiers[0]}")
        level_nodes[str(subject)] = f"e-{match.group(1)}"

    if len(level_nodes) != 106:
        raise AssertionError(
            f"Expected 106 e-CF level nodes, found {len(level_nodes)}; "
            f"first={list(level_nodes)[:5]}, last={list(level_nodes)[-5:]}"
        )
    return level_nodes


def read_dqr_anchors() -> dict[int, str]:
    graph = Graph()
    graph.parse(DQR_PATH, format="turtle")
    anchors: dict[int, str] = {}

    for subject in graph.subjects(RDF.type, SKOS.Concept):
        for identifier in graph.objects(subject, HARM.sourceIdentifier):
            match = re.fullmatch(r"L([1-8])", str(identifier))
            if match:
                # dqr_1d.ttl carries the harmonised source namespace
                # http://hr-qde.org/harmonised/source/dqr/LN natively
                # (Namespace-Revision 2026-09-06; owl:sameAs bridges to the
                # data.bmbf.de authority URI). G_levels uses it verbatim.
                uri = str(subject)
                assert uri.startswith(DQR_PREFIX), uri
                anchors[int(match.group(1))] = uri

    if set(anchors) != set(range(1, 9)):
        raise AssertionError(f"Expected DQR anchors L1-L8, found {anchors}")
    return anchors


def build_gold_entries(level_nodes: dict[str, str], dqr_anchors: dict[int, str]) -> list[dict[str, object]]:
    crosswalk = {
        "e-1": [dqr_anchors[3], dqr_anchors[4]],
        "e-2": [dqr_anchors[5]],
        "e-3": [dqr_anchors[6]],
        "e-4": [dqr_anchors[7]],
        "e-5": [dqr_anchors[8]],
    }
    dqr_numbers = {uri: number for number, uri in dqr_anchors.items()}
    entries: list[dict[str, object]] = []

    for ecf_uri, proficiency in level_nodes.items():
        for dqr_uri in crosswalk[proficiency]:
            dqr_number = dqr_numbers[dqr_uri]
            entries.append(
                {
                    "subject_id": ecf_uri,
                    "subject_label": ecf_uri.rsplit("/", 1)[-1],
                    "object_id": dqr_uri,
                    "object_label": f"DQR-Niveau {dqr_number}",
                    # ``predicate`` is retained for compatibility with G_struct;
                    # ``predicate_id`` is the current SSSOM/API field name.
                    "predicate": "skos:closeMatch",
                    "predicate_id": "skos:closeMatch",
                    "mapping_justification": "semapv:ManualMappingCuration",
                    "mapping_confidence": 1.0,
                    "comment": (
                        f"e-CF 3.0 (CWA 16234-1:2014): {proficiency} "
                        f"→ DQR {dqr_number}"
                    ),
                }
            )
    return entries


def validate(entries: list[dict[str, object]], dqr_anchors: dict[int, str]) -> None:
    assert len(entries) == 113
    assert all(str(entry["subject_id"]).startswith(ECF_PREFIX) for entry in entries)
    assert all(entry["object_id"] in dqr_anchors.values() for entry in entries)
    assert all(entry["subject_id"] != entry["object_id"] for entry in entries)
    assert {entry["predicate_id"] for entry in entries} == {"skos:closeMatch"}
    assert {entry["predicate"] for entry in entries} == {"skos:closeMatch"}
    assert {
        entry["mapping_justification"] for entry in entries
    } == {"semapv:ManualMappingCuration"}
    assert {entry["mapping_confidence"] for entry in entries} == {1.0}

    e1_entries = [entry for entry in entries if ".Niveau" in str(entry["subject_id"])
                  and str(entry["subject_id"]).endswith(("Niveau1",))]
    assert len(e1_entries) == 14
    e1_subject_counts = Counter(str(entry["subject_id"]) for entry in e1_entries)
    assert e1_subject_counts and set(e1_subject_counts.values()) == {2}


def update_readme() -> None:
    section = """\n## G_levels.json\nGoldmenge für K_levels: e-CF Dimension-3-Proficiency-Beschreibungen ↔\nDQR-Niveau-Anker.\nQuelle: e-CF 3.0 (CWA 16234-1:2014) (normative Crosswalk-Tabelle).\nMapping_justification: semapv:ManualMappingCuration\nPaare: 113 (106 e-CF-Levelknoten × 1 DQR-Anker, außer e-1 × 2 DQR-Anker)\nErstellt: 2026-09-06\n"""
    readme = README_PATH.read_text(encoding="utf-8")
    if "## G_levels.json" not in readme:
        README_PATH.write_text(readme.rstrip() + "\n" + section, encoding="utf-8")


def main() -> None:
    level_nodes = read_level_nodes()
    dqr_anchors = read_dqr_anchors()
    entries = build_gold_entries(level_nodes, dqr_anchors)
    validate(entries, dqr_anchors)

    payload = {
        "_comment": [
            "Normative Goldmenge G_levels fuer den K_levels-Evaluationslauf.",
            "Quelle: e-CF 3.0 (CWA 16234-1:2014) -- normative Crosswalk-Tabelle.",
            "e-CF Dimension-3-Proficiency-Levelknoten werden DQR-Niveauankern",
            "zugeordnet; e-1 referenziert DQR 3 und DQR 4.",
        ],
        "description": "Normative e-CF-Proficiency<->DQR-Niveau-Paare (G_levels)",
        "source": "e-CF 3.0 (CWA 16234-1:2014)",
        "confidence": 1.0,
        "match_type": "manual",
        "uri_status": "resolved",
        "pairs": entries,
    }
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    update_readme()

    distribution = Counter(
        (entry["comment"].split(": ", 1)[1].split(" → ", 1)[0], entry["object_label"])
        for entry in entries
    )
    print(f"level_nodes: {len(level_nodes)}")
    print(f"entries: {len(entries)}")
    print(f"proficiency_counts: {dict(sorted(Counter(level_nodes.values()).items()))}")
    for key, count in sorted(distribution.items()):
        print(f"{key[0]} -> {key[1]}: {count}")
    print("all validations: passed")


if __name__ == "__main__":
    main()
