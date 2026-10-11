"""
Aufgabe 1 (korrigierte Architektur): rdf:type-Rollen je Konzept in die
TTL-Formalisierungen schreiben. Die Rolle ist damit aus den Eingangsdaten
lesbar; kein Code muss implizit wissen, dass ein KQR ein Niveaurahmen ist.

  ecf.ttl   -> 40 Dimension-2-Kompetenzen (A.1 .. E.9)  = harm:CompetenceConcept
               (die 5 Bereiche PLAN/BUILD/RUN/ENABLE/MANAGE bleiben ohne Rolle)
  esco...ttl -> alle skos:Concept (Skills + Occupations) = harm:CompetenceConcept

dqr_3.ttl wird separat gepflegt (8 x harm:LevelConcept, bereits gesetzt).
eqf_2017.ttl wird nicht annotiert (kein Run-KQR mehr).

Textbasiert und zeilenweise, mit Normalisierung der Zeilenenden auf \\n.
Idempotent: ist der entsprechende rdf:type bereits vorhanden, passiert nichts.
"""

from __future__ import annotations

import re
from pathlib import Path

FORMALIZED = Path(__file__).resolve().parents[1] / "data" / "formalized"

_INDIVIDUAL_LINES = [
    "harm:CompetenceConcept a owl:NamedIndividual ;",
    '    skos:prefLabel "Competence concept — enters pipeline"@en .',
    "",
    "harm:LevelConcept a owl:NamedIndividual ;",
    '    skos:prefLabel "Level concept — skeleton import only"@en .',
]

_EXTRA_PREFIXES = [
    "@prefix harm: <http://hr-qde.org/harmonised/> .",
    "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
]


def _normalise(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _ensure_header(lines: list[str]) -> list[str]:
    """Fuegt fehlende @prefix-Zeilen und die zwei Rollen-Individuen nach dem
    letzten @prefix-Block ein."""
    joined = "\n".join(lines)
    last_prefix = max(
        (i for i, ln in enumerate(lines) if ln.startswith("@prefix ")), default=-1
    )
    to_add = [p for p in _EXTRA_PREFIXES if p.split()[1] not in joined]
    insert_at = last_prefix + 1
    block: list[str] = []
    if to_add:
        block.extend(to_add)
    if "harm:CompetenceConcept" not in joined:
        block.append("")
        block.extend(_INDIVIDUAL_LINES)
    if not block:
        return lines
    return lines[:insert_at] + block + lines[insert_at:]


def annotate_ecf() -> None:
    path = FORMALIZED / "ecf.ttl"
    lines = _normalise(path.read_text(encoding="utf-8")).split("\n")
    if any("a harm:CompetenceConcept" in ln for ln in lines):
        print("ecf.ttl: harm:CompetenceConcept bereits vorhanden -- uebersprungen.")
        return
    lines = _ensure_header(lines)

    out: list[str] = []
    n = 0
    comp_re = re.compile(r'hrqde:sourceIdentifier\s+"([A-E]\.\d+)"\s*;')
    for line in lines:
        out.append(line)
        if comp_re.search(line):
            indent = line[: len(line) - len(line.lstrip())]
            out.append(f"{indent}a harm:CompetenceConcept ;")
            n += 1
    path.write_text("\n".join(out) + ("\n" if not out[-1].endswith("\n") else ""),
                    encoding="utf-8", newline="\n")
    print(f"ecf.ttl: {n} Kompetenzen als harm:CompetenceConcept annotiert.")


def annotate_esco() -> None:
    path = FORMALIZED / "esco_v1_2_ict_ausschnitt.ttl"
    lines = _normalise(path.read_text(encoding="utf-8")).split("\n")
    if any("a harm:CompetenceConcept" in ln for ln in lines):
        print("esco...ttl: harm:CompetenceConcept bereits vorhanden -- uebersprungen.")
        return
    lines = _ensure_header(lines)

    out: list[str] = []
    n = 0
    concept_re = re.compile(r"^<[^>]+>\s+a\s+skos:Concept\s*;")
    for line in lines:
        out.append(line)
        if concept_re.match(line):
            out.append("    a harm:CompetenceConcept ;")
            n += 1
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print(f"esco...ttl: {n} Konzepte als harm:CompetenceConcept annotiert.")


def verify() -> None:
    from rdflib import Graph, Namespace, RDF, URIRef
    from rdflib.namespace import SKOS
    HARM = Namespace("http://hr-qde.org/harmonised/")
    for name in ("ecf.ttl", "dqr_3.ttl", "esco_v1_2_ict_ausschnitt.ttl"):
        g = Graph()
        g.parse(data=_normalise((FORMALIZED / name).read_text(encoding="utf-8")), format="turtle")
        comp = len(list(g.subjects(RDF.type, HARM.CompetenceConcept)))
        lvl = len(list(g.subjects(RDF.type, HARM.LevelConcept)))
        total = len(list(g.subjects(RDF.type, SKOS.Concept)))
        print(f"  {name:34s} concepts={total:4d}  CompetenceConcept={comp:4d}  LevelConcept={lvl}")


if __name__ == "__main__":
    annotate_ecf()
    annotate_esco()
    print("Verifikation (rdflib):")
    verify()
