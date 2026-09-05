"""
Filtert den ESCO-Gesamtdump (data/raw/esco-v1.2.1.ttl, ~750 MB) auf den
Teilbaum der ICT-Wurzel-Skill-Group und schreibt das Ergebnis als deutlich
kleineres, eigenstaendiges Turtle nach
data/raw/esco-v1.2.1-ict-filtered.ttl.

Welche URI ist die Wurzel? Der vom Auftrag vorgeschlagene Kandidat
<http://data.europa.eu/esco/skillGroup/6> existiert im Dump nicht. ESCO
modelliert seine Skills-Hierarchie stattdessen ueber die ISCED-F-2013-
Klassifikation (Concept-Scheme <.../concept-scheme/skills-hierarchy>):
der Wissens-Wurzelknoten "K" (<.../skill/c46fcb45-...>, skos:notation
"K") verzweigt per skos:narrower direkt in die ISCED-F-Hauptfelder, u.a.
<http://data.europa.eu/esco/isced-f/06> mit skos:notation "06" und
skos:prefLabel "information and communication technologies (icts)"@en.
Das ist die tatsaechliche Wurzel-Skill-Group "6.0 ICT" und wird hier als
Default verwendet (per --root ueberschreibbar).

Warum kein rdflib.Graph().parse() auf die Gesamtdatei: wie in
01_esco_formalize.py beschrieben, sprengen die ~1,7 Mio. durch Leerzeilen
getrennten Bloecke beim klassischen Turtle-Parsing den Arbeitsspeicher.
Das Skript nutzt daher denselben zeilenweisen Streaming-Ansatz und zieht
rdflib nur fuer den Aufbau und die Serialisierung des kleinen
Ergebnisgraphen heran (kein SPARQL auf dem Volltext moeglich, da dafuer
ohnehin der komplette Graph im Speicher stehen muesste).

Ablauf (vier sequentielle Streaming-Durchgaenge, tqdm zeigt je Durchgang
den Byte-Fortschritt):

  1. Baue eine kompakte Map aller ISCED-F-Konzepte -> ihre
     skos:narrower-Ziele (Skill-Groups koennen sowohl weitere
     Skill-Groups als auch einzelne Skills als narrower referenzieren).
  2. Tiefensuche ab der Wurzel (visited-Set gegen Zyklen): sammelt alle
     ICT-Skill-Groups und alle darunter haengenden Skill-URIs.
  3. Lade die vollen Bloecke dieser Skills + Skill-Groups; sammle dabei
     ueber esco:isEssentialSkillFor / esco:isOptionalSkillFor alle
     referenzierten Occupation-URIs und lade deren Bloecke.
  4. Loese die dct:description-Verweise (Skills, Skill-Groups,
     Occupations) auf die ausgelagerten node-literal-Bloecke auf.

Taxonomie-Beziehungen (skos:broader/narrower, isEssentialSkillFor/
isOptionalSkillFor) werden nur zwischen Konzepten geschrieben, die beide
im gefilterten Set enthalten sind -- keine Verweise ins Leere.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from rdflib import RDF, SKOS, Graph, Literal, Namespace, URIRef
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "raw" / "esco-v1.2.1.ttl"
OUTPUT_PATH = ROOT / "data" / "raw" / "esco-v1.2.1-ict-filtered.ttl"
ROOT_SKILL_GROUP_URI = "http://data.europa.eu/esco/isced-f/06"

ESCO = Namespace("http://data.europa.eu/esco/model#")

_SUBJECT_RE = re.compile(r"^<([^>]+)>")
_URI_RE = re.compile(r"<(https?://[^>\s,;]+)>")
# Jedes Praedikat steht im ESCO-Dump auf einer eigenen physischen Zeile
# (vgl. 01_esco_formalize.py) -- bis Zeilenende matchen genuegt.
_NARROWER_RE = re.compile(r"^[ \t]*skos:narrower\s+(.+)$", re.MULTILINE)
_ESSENTIAL_RE = re.compile(r"^[ \t]*esco:isEssentialSkillFor\s+(.+)$", re.MULTILINE)
_OPTIONAL_RE = re.compile(r"^[ \t]*esco:isOptionalSkillFor\s+(.+)$", re.MULTILINE)
_PREFLABEL_RE = re.compile(r"^[ \t]*skos:prefLabel\s+(.+)$", re.MULTILINE)
_DESC_PROP_RE = re.compile(r"^[ \t]*dct:description\s+(.+)$", re.MULTILINE)
_LABEL_ENTRY_RE = re.compile(r'"((?:[^"\\]|\\.)*)"@([a-zA-Z-]+)')
_LANG_RE = re.compile(r'esco:language\s+"([a-z]{2})"')
_NODELIT_RE = re.compile(r'esco:nodeLiteral\s+"((?:[^"\\]|\\.)*)"', re.DOTALL)


def _iter_blocks(path: Path, desc: str):
    """Streamt (Subjekt-URI, Blocktext)-Paare, ohne die Datei komplett zu laden.

    Bloecke sind durch Leerzeilen getrennte Zeilengruppen, die (Konvention
    des ESCO-Dumps) jeweils alle Triples zu genau einem Subjekt enthalten.
    """
    total_bytes = path.stat().st_size
    buffer: list[str] = []
    with path.open(encoding="utf-8") as fh, tqdm(
        total=total_bytes, unit="B", unit_scale=True, unit_divisor=1024, desc=desc
    ) as bar:
        for raw_line in fh:
            bar.update(len(raw_line.encode("utf-8")))
            if raw_line.strip() == "":
                if buffer:
                    match = _SUBJECT_RE.match(buffer[0])
                    if match:
                        yield match.group(1), "".join(buffer)
                    buffer = []
                continue
            if raw_line.startswith("@prefix"):
                continue
            buffer.append(raw_line)
        if buffer:
            match = _SUBJECT_RE.match(buffer[0])
            if match:
                yield match.group(1), "".join(buffer)


def _extract_uris(prop_re: re.Pattern, block: str) -> set[str]:
    uris: set[str] = set()
    for match in prop_re.finditer(block):
        uris.update(_URI_RE.findall(match.group(1)))
    return uris


def _extract_labels(block: str) -> list[tuple[str, str]]:
    match = _PREFLABEL_RE.search(block)
    if not match:
        return []
    return [(text.replace('\\"', '"'), lang) for text, lang in _LABEL_ENTRY_RE.findall(match.group(1))]


def _build_iscedf_narrower_map(path: Path) -> dict[str, list[str]]:
    """uri (nur /isced-f/-Konzepte) -> Liste der skos:narrower-Ziele."""
    narrower_map: dict[str, list[str]] = {}
    for uri, block in _iter_blocks(path, "1/4 ISCED-F-Hierarchie"):
        if "/isced-f/" not in uri:
            continue
        match = _NARROWER_RE.search(block)
        if match:
            narrower_map[uri] = _URI_RE.findall(match.group(1))
    return narrower_map


def _collect_ict_subtree(root: str, narrower_map: dict[str, list[str]]) -> tuple[set[str], set[str]]:
    """Tiefensuche ab `root`: trennt ISCED-F-Skill-Groups von Skill-Blattknoten.

    Skill-Groups (URIs mit /isced-f/) koennen laut Dump gleichzeitig
    weitere Skill-Groups UND einzelne Skills als skos:narrower listen
    (z.B. isced-f/068). Nur Skill-Groups werden weiter aufgeklappt --
    Skills selbst tragen kein skos:narrower (sie sind die Blattebene).
    """
    skill_groups: set[str] = set()
    skill_uris: set[str] = set()
    visited: set[str] = set()
    stack = [root]
    while stack:
        uri = stack.pop()
        if uri in visited:
            continue
        visited.add(uri)
        if "/isced-f/" in uri:
            skill_groups.add(uri)
            stack.extend(narrower_map.get(uri, []))
        else:
            skill_uris.add(uri)
    return skill_groups, skill_uris


def _fetch_blocks(path: Path, wanted: set[str], desc: str) -> dict[str, str]:
    """Liest die vollen Bloecke der gesuchten Subjekt-URIs (frueher Abbruch, sobald alle gefunden)."""
    found: dict[str, str] = {}
    if not wanted:
        return found
    remaining = set(wanted)
    for uri, block in _iter_blocks(path, desc):
        if uri in remaining:
            found[uri] = block
            remaining.discard(uri)
            if not remaining:
                break
    return found


def _build_graph(
    group_blocks: dict[str, str],
    skill_blocks: dict[str, str],
    occupation_blocks: dict[str, str],
    narrower_map: dict[str, list[str]],
    skill_essential: dict[str, set[str]],
    skill_optional: dict[str, set[str]],
    node_literals: dict[str, tuple[str, str]],
) -> Graph:
    graph = Graph()
    graph.bind("skos", SKOS)
    graph.bind("esco", ESCO)

    def add_concept(uri: str, block: str, *extra_types: URIRef) -> None:
        subject = URIRef(uri)
        graph.add((subject, RDF.type, SKOS.Concept))
        for extra_type in extra_types:
            graph.add((subject, RDF.type, extra_type))
        for text, lang in _extract_labels(block):
            graph.add((subject, SKOS.prefLabel, Literal(text, lang=lang)))
        for desc_uri in _extract_uris(_DESC_PROP_RE, block):
            if desc_uri in node_literals:
                lang, text = node_literals[desc_uri]
                graph.add((subject, SKOS.definition, Literal(text, lang=lang)))

    for uri, block in group_blocks.items():
        add_concept(uri, block)
    for uri, block in skill_blocks.items():
        add_concept(uri, block, ESCO.Skill)
    for uri, block in occupation_blocks.items():
        add_concept(uri, block, ESCO.Occupation)

    retained = set(group_blocks) | set(skill_blocks)
    for parent, children in narrower_map.items():
        if parent not in retained:
            continue
        for child in children:
            if child not in retained:
                continue
            graph.add((URIRef(parent), SKOS.narrower, URIRef(child)))
            graph.add((URIRef(child), SKOS.broader, URIRef(parent)))

    for skill_uri, occ_uris in skill_essential.items():
        for occ_uri in occ_uris:
            if occ_uri not in occupation_blocks:
                continue
            graph.add((URIRef(skill_uri), ESCO.isEssentialSkillFor, URIRef(occ_uri)))
            graph.add((URIRef(occ_uri), ESCO.relatedEssentialSkill, URIRef(skill_uri)))
    for skill_uri, occ_uris in skill_optional.items():
        for occ_uri in occ_uris:
            if occ_uri not in occupation_blocks:
                continue
            graph.add((URIRef(skill_uri), ESCO.isOptionalSkillFor, URIRef(occ_uri)))
            graph.add((URIRef(occ_uri), ESCO.relatedOptionalSkill, URIRef(skill_uri)))

    return graph


def build_filtered_dump(source: Path, root: str) -> Graph:
    print("Durchgang 1/4: Baue ISCED-F-Hierarchie (skos:narrower) ...")
    narrower_map = _build_iscedf_narrower_map(source)
    print(f"  -> {len(narrower_map)} ISCED-F-Konzepte mit skos:narrower gefunden.")

    if root not in narrower_map:
        raise SystemExit(f"Wurzel-Skill-Group nicht gefunden (kein skos:narrower vorhanden): {root}")

    skill_groups, skill_uris = _collect_ict_subtree(root, narrower_map)
    print(f"Traversal ab {root}: {len(skill_groups)} Skill-Groups, {len(skill_uris)} Skills im Teilbaum.")

    print("Durchgang 2/4: Lade Skill- und Skill-Group-Bloecke ...")
    concept_blocks = _fetch_blocks(source, skill_groups | skill_uris, "2/4 Skills + Skill-Groups")
    skill_blocks = {uri: block for uri, block in concept_blocks.items() if uri in skill_uris}
    group_blocks = {uri: block for uri, block in concept_blocks.items() if uri in skill_groups}
    missing = (skill_groups | skill_uris) - concept_blocks.keys()
    print(f"  -> {len(skill_blocks)} Skills, {len(group_blocks)} Skill-Groups geladen" + (f" ({len(missing)} nicht gefunden)" if missing else "") + ".")

    occupation_uris: set[str] = set()
    skill_essential: dict[str, set[str]] = {}
    skill_optional: dict[str, set[str]] = {}
    for uri, block in skill_blocks.items():
        essential = {u for u in _extract_uris(_ESSENTIAL_RE, block) if "/occupation/" in u}
        optional = {u for u in _extract_uris(_OPTIONAL_RE, block) if "/occupation/" in u}
        if essential:
            skill_essential[uri] = essential
        if optional:
            skill_optional[uri] = optional
        occupation_uris.update(essential | optional)

    print(f"Durchgang 3/4: Suche {len(occupation_uris)} referenzierte Occupations ...")
    occupation_blocks = _fetch_blocks(source, occupation_uris, "3/4 Occupations")
    print(f"  -> {len(occupation_blocks)}/{len(occupation_uris)} Occupations gefunden.")

    description_uris: set[str] = set()
    for block in (*skill_blocks.values(), *group_blocks.values(), *occupation_blocks.values()):
        description_uris.update(_extract_uris(_DESC_PROP_RE, block))
    print(f"Durchgang 4/4: Loese {len(description_uris)} node-literal-Beschreibungen auf ...")
    node_literals: dict[str, tuple[str, str]] = {}
    for uri, block in _fetch_blocks(source, description_uris, "4/4 Beschreibungen").items():
        lang_match = _LANG_RE.search(block)
        text_match = _NODELIT_RE.search(block)
        if lang_match and text_match:
            node_literals[uri] = (lang_match.group(1), text_match.group(1).replace('\\"', '"'))

    return _build_graph(
        group_blocks,
        skill_blocks,
        occupation_blocks,
        narrower_map,
        skill_essential,
        skill_optional,
        node_literals,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Pfad zum ESCO-TTL-Gesamtdump")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Zielpfad fuer das gefilterte Turtle")
    parser.add_argument("--root", default=ROOT_SKILL_GROUP_URI, help="URI der Wurzel-Skill-Group")
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"ESCO-Quelldatei nicht gefunden: {args.source}")

    graph = build_filtered_dump(args.source, args.root)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(graph.serialize(format="turtle"), encoding="utf-8")

    n_skills = len(set(graph.subjects(RDF.type, ESCO.Skill)))
    n_occupations = len(set(graph.subjects(RDF.type, ESCO.Occupation)))
    n_groups = len(set(graph.subjects(RDF.type, SKOS.Concept))) - n_skills - n_occupations

    print(f"\nGeschrieben: {args.output}")
    print(f"{n_skills} Skills, {n_occupations} Occupations, {n_groups} Skill-Groups gefiltert")


if __name__ == "__main__":
    main()
