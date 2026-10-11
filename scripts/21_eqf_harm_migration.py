"""
EQF-Reformalisierung auf das aktuelle harm:-Vokabular (analog zu
data/formalized/dqr_levelProposal.ttl / ecf_levelProposal.ttl).

Liest data/formalized/eqf_2017.ttl und ergaenzt/korrigiert IN DERSELBEN
DATEI (bzw. --output). Fuer jedes der 8 eqf:Level{n}- und der 24
Dimensionsfacetten-Konzepte (eqf:L{n}_Knowledge / _Skills /
_ResponsibilityAutonomy):

  * harm:derivedFrom harm:kqr_eqf   (IRI, in hrqde-harmonisation-schema.ttl
                                     bereits deklariert -- nicht neu praegen)
  * harm:sourceIdentifier "<lokaler Name>"   (z. B. "Level1", "L1_Knowledge")
  * rdf:type harm:LevelConcept       (alle 32 -- EQF-Konzepte sind
                                     Qualifikationsniveaus, keine mit ESCO-
                                     Skills vergleichbaren Kompetenzen)
  * skos:prefLabel "..."@de    zusaetzlich zum bestehenden @en-Label
  * skos:definition "..."@de   zusaetzlich zur bestehenden @en-Definition

Deutsche Labels/Definitionen: Europass, "Beschreibung der acht EQR-Niveaus"
(https://europass.europa.eu/de/description-eight-eqf-levels), Wortlaut =
amtliche EQR-Deskriptoren Anhang II der Empfehlung 2017/C 189/03.

Ausserdem korrigiert:
  * skos:exactMatch dqr:Level{n}  ->  skos:exactMatch dqr:L{n}
    (dqr:Level{n} existiert nicht; data/formalized/dqr_3.ttl benennt seine
    Niveauknoten dqr:L1..dqr:L8 -- tote Kante seit Entstehung der Datei.)

NICHT angefasst: eqf:hasKnowledge/hasSkills/hasResponsibilityAutonomy,
eqf:descriptorType, eqf:levelNumber, skos:broader-Hierarchie, eqf:EQFScheme,
die URI-Basis http://data.europa.eu/snb/eqf/ (Praefix eqf:) und die
bestehenden @en-Literale.

Textbasiert, zeilenweise, Zeilenenden auf \\n normalisiert. Idempotent:
ist der kanonische RDF-Typ bereits in der Datei, passiert nichts.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

FORMALIZED = Path(__file__).resolve().parents[1] / "data" / "formalized"
DEFAULT_INPUT = FORMALIZED / "eqf_2017.ttl"

HARM_PREFIX_LINE = "@prefix harm:   <http://hr-qde.org/harmonised/> ."

HEADER_NOTE = [
    "",
    "# --- Reformalisierung auf harm:-Vokabular (scripts/21_eqf_harm_migration.py) ---",
    "# harm:derivedFrom als IRI (harm:kqr_eqf), harm:sourceIdentifier, rdf:type",
    "# harm:LevelConcept fuer alle 32 Konzepte (analog dqr_levelProposal.ttl).",
    "# Deutsche Labels/Definitionen: Europass, amtliche EQR-Deskriptoren Anhang II",
    "# der Empfehlung 2017/C 189/03 (https://europass.europa.eu/de/description-eight-eqf-levels).",
    "# skos:exactMatch-Ziele auf dqr:L{n} korrigiert (zuvor dqr:Level{n}, tote Kante).",
]

# --- Amtliche deutsche EQR-Deskriptoren (Europass / Anhang II 2017/C 189/03) ---

KNOWLEDGE = {
    1: "grundlegendes Allgemeinwissen",
    2: "grundlegendes Faktenwissen in einem Arbeits- oder Lernbereich",
    3: "Kenntnisse von Fakten, Grundsätzen, Verfahren und allgemeinen Begriffen in einem Arbeits- oder Lernbereich",
    4: "breites Spektrum an Fakten- und Theoriewissen in einem Arbeits- oder Lernbereich",
    5: "umfassendes, spezialisiertes Fakten- und Theoriewissen in einem Arbeits- oder Lernbereich sowie Bewusstsein für die Grenzen dieser Kenntnisse",
    6: "fortgeschrittene Kenntnisse in einem Arbeits- oder Lernbereich unter Einsatz eines kritischen Verständnisses von Theorien und Grundsätzen",
    7: "hoch spezialisierte Kenntnisse, die zum Teil an neueste Erkenntnisse in einem Arbeits- oder Lernbereich anknüpfen, als Grundlage für innovative Denkansätze und/oder Forschung; kritisches Bewusstsein für Wissensfragen in einem Bereich und an der Schnittstelle zwischen verschiedenen Bereichen",
    8: "Spitzenkenntnisse in einem Arbeits- oder Lernbereich und an der Schnittstelle zwischen verschiedenen Bereichen",
}

SKILLS = {
    1: "grundlegende Fertigkeiten, die zur Erledigung einfacher Aufgaben erforderlich sind",
    2: "grundlegende kognitive und praktische Fertigkeiten, die zur Nutzung einschlägiger Informationen erforderlich sind, um Aufgaben zu erledigen und Routineprobleme unter Verwendung einfacher Regeln und Werkzeuge zu lösen",
    3: "eine Reihe kognitiver und praktischer Fertigkeiten zur Erledigung von Aufgaben und zur Lösung von Problemen, wobei grundlegende Methoden, Werkzeuge, Materialien und Informationen ausgewählt und angewandt werden",
    4: "eine Reihe kognitiver und praktischer Fertigkeiten, die erforderlich sind, um Lösungen für spezielle Probleme in einem Arbeits- oder Lernbereich zu finden",
    5: "umfassende kognitive und praktische Fertigkeiten, die erforderlich sind, um kreative Lösungen für abstrakte Probleme zu erarbeiten",
    6: "fortgeschrittene Fertigkeiten, die die Beherrschung des Faches sowie Innovationsfähigkeit erkennen lassen und zur Lösung komplexer und unvorhersehbarer Probleme in einem spezialisierten Arbeits- oder Lernbereich nötig sind",
    7: "spezialisierte Problemlösungsfertigkeiten im Bereich Forschung und/oder Innovation, um neue Kenntnisse zu gewinnen und neue Verfahren zu entwickeln sowie um Wissen aus verschiedenen Bereichen zu integrieren",
    8: "im höchsten Maße fortgeschrittene und spezialisierte Fertigkeiten und Methoden, einschließlich Synthese und Evaluierung, zur Lösung zentraler Problemstellungen in den Bereichen Forschung und/oder Innovation und zur Erweiterung oder Neudefinition vorhandener Kenntnisse oder beruflicher Praxis",
}

RESPONSIBILITY = {
    1: "Arbeiten oder Lernen unter direkter Anleitung in einem strukturierten Kontext",
    2: "Arbeiten oder Lernen unter Anleitung mit einem gewissen Maß an Selbstständigkeit",
    3: "Verantwortung für die Erledigung von Arbeits- oder Lernaufgaben übernehmen; bei der Lösung von Problemen das eigene Verhalten an die jeweiligen Umstände anpassen",
    4: "selbstständiges Tätigwerden innerhalb der Handlungsparameter von Arbeits- oder Lernkontexten, die in der Regel bekannt sind, sich jedoch ändern können; Beaufsichtigung der Routinearbeit anderer Personen, wobei ein gewisses Maß an Verantwortung für die Bewertung und Verbesserung der Arbeits- oder Lernaktivitäten übernommen wird",
    5: "Leiten und Beaufsichtigen in Arbeits- oder Lernkontexten, in denen unvorhersehbare Änderungen auftreten; Überprüfung und Entwicklung der eigenen Leistung und der Leistung anderer Personen",
    6: "Leitung komplexer fachlicher oder beruflicher Tätigkeiten oder Projekte und Übernahme von Entscheidungsverantwortung in unvorhersehbaren Arbeits- oder Lernkontexten; Übernahme von Verantwortung für die berufliche Entwicklung von Einzelpersonen und Gruppen",
    7: "Leitung und Gestaltung komplexer, unvorhersehbarer Arbeits- oder Lernkontexte, die neue strategische Ansätze erfordern; Übernahme von Verantwortung für Beiträge zum Fachwissen und zur Berufspraxis und/oder für die Überprüfung der strategischen Leistung von Teams",
    8: "fachliche Autorität, Innovationsfähigkeit, Selbstständigkeit, wissenschaftliche und berufliche Integrität und nachhaltiges Engagement bei der Entwicklung neuer Ideen oder Verfahren in führenden Arbeits- oder Lernkontexten, einschließlich der Forschung",
}

DIMENSION_DE = {
    "Knowledge": "Kenntnisse",
    "Skills": "Fertigkeiten",
    "ResponsibilityAutonomy": "Verantwortung und Selbstständigkeit",
}

# lokaler Name -> (deutsches prefLabel, deutsche definition)
DE: dict[str, tuple[str, str]] = {}
for _n in range(1, 9):
    DE[f"Level{_n}"] = (
        f"EQR-Niveau {_n}",
        f"Kenntnisse: {KNOWLEDGE[_n]}. "
        f"Fertigkeiten: {SKILLS[_n]}. "
        f"Verantwortung und Selbstständigkeit: {RESPONSIBILITY[_n]}.",
    )
    DE[f"L{_n}_Knowledge"] = (f"Kenntnisse – EQR-Niveau {_n}", KNOWLEDGE[_n])
    DE[f"L{_n}_Skills"] = (f"Fertigkeiten – EQR-Niveau {_n}", SKILLS[_n])
    DE[f"L{_n}_ResponsibilityAutonomy"] = (
        f"Verantwortung und Selbstständigkeit – EQR-Niveau {_n}",
        RESPONSIBILITY[_n],
    )

_SUBJECT_RE = re.compile(
    r"^eqf:(Level[1-8]|L[1-8]_(?:Knowledge|Skills|ResponsibilityAutonomy))\s*$"
)


def _normalise(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _ensure_harm_prefix_and_note(lines: list[str]) -> list[str]:
    if any(ln.startswith("@prefix harm:") for ln in lines):
        return lines
    last_prefix = max(
        (i for i, ln in enumerate(lines) if ln.startswith("@prefix ")), default=-1
    )
    if last_prefix == -1:
        return [HARM_PREFIX_LINE, *HEADER_NOTE, "", *lines]
    insert_at = last_prefix + 1
    return lines[:insert_at] + [HARM_PREFIX_LINE, *HEADER_NOTE] + lines[insert_at:]


def _harm_block(local_name: str) -> list[str]:
    de_label, de_def = DE[local_name]
    return [
        "  harm:derivedFrom harm:kqr_eqf ;",
        f'  harm:sourceIdentifier "{local_name}" ;',
        "  a harm:LevelConcept ;",
        f'  skos:prefLabel "{de_label}"@de ;',
        f'  skos:definition "{de_def}"@de .',
    ]


def migrate(text: str) -> str:
    text = _normalise(text)
    if "a harm:LevelConcept" in text:
        print("eqf_2017.ttl: harm:LevelConcept bereits vorhanden -- uebersprungen.")
        return text

    # Tote Kante dqr:Level{n} -> dqr:L{n} (nur der dqr:-Namensraum, eqf:Level bleibt).
    text = re.sub(r"\bdqr:Level([1-8])\b", r"dqr:L\1", text)

    lines = _ensure_harm_prefix_and_note(text.split("\n"))

    out: list[str] = []
    current: str | None = None
    for line in lines:
        m = _SUBJECT_RE.match(line)
        if m:
            current = m.group(1)
            out.append(line)
            continue
        if current is not None:
            stripped = line.rstrip()
            if stripped.endswith(".") and not stripped.endswith(";"):
                # Blockabschluss: "." -> ";" und harm:-Block anhaengen.
                out.append(stripped[:-1].rstrip() + " ;")
                out.extend(_harm_block(current))
                current = None
                continue
        out.append(line)

    return "\n".join(out)


def verify(path: Path) -> None:
    from rdflib import Graph, Namespace, RDF, URIRef
    from rdflib.namespace import SKOS

    HARM = Namespace("http://hr-qde.org/harmonised/")
    DQR = Namespace("http://data.bmbf.de/dqr/")
    EQF = Namespace("http://data.europa.eu/snb/eqf/")

    g = Graph()
    g.parse(data=_normalise(path.read_text(encoding="utf-8")), format="turtle")

    concepts = list(g.subjects(RDF.type, SKOS.Concept))
    print(f"  skos:Concept                     : {len(concepts)}")

    role_ok = sum(
        1 for c in concepts if (c, RDF.type, HARM.LevelConcept) in g
    )
    print(f"  rdf:type harm:LevelConcept: {role_ok}/{len(concepts)}")

    derived_ok = sum(
        1
        for c in concepts
        if any(
            isinstance(o, URIRef) and o == HARM.kqr_eqf
            for o in g.objects(c, HARM.derivedFrom)
        )
    )
    print(f"  harm:derivedFrom harm:kqr_eqf(IRI): {derived_ok}/{len(concepts)}")

    bilingual = sum(
        1
        for c in concepts
        if {getattr(l, "language", None) for l in g.objects(c, SKOS.prefLabel)}
        >= {"de", "en"}
    )
    print(f"  skos:prefLabel @de UND @en       : {bilingual}/{len(concepts)}")

    dqr_level_dangling = len(list(g.triples((None, SKOS.exactMatch, None))))
    dqr_l = sum(
        1
        for _, _, o in g.triples((None, SKOS.exactMatch, None))
        if str(o).startswith(str(DQR)) and re.search(r"/L[1-8]$", str(o))
    )
    print(f"  skos:exactMatch dqr:L{{n}}          : {dqr_l} (von {dqr_level_dangling} exactMatch gesamt)")

    for n in (1, 5, 8):
        assert (EQF[f"Level{n}"], SKOS.exactMatch, DQR[f"L{n}"]) in g, n
    print("  Stichprobe eqf:Level{1,5,8} skos:exactMatch dqr:L{1,5,8}: ok")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Standard: identisch zum Input (in-place).",
    )
    args = parser.parse_args()

    in_path: Path = args.input
    out_path: Path = args.output or args.input

    original = in_path.read_text(encoding="utf-8")
    migrated = migrate(original)
    out_path.write_text(
        migrated if migrated.endswith("\n") else migrated + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"geschrieben: {out_path}")
    print("Verifikation (rdflib):")
    verify(out_path)


if __name__ == "__main__":
    main()
