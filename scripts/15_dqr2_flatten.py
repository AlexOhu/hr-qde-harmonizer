"""
Bereinigt data/formalized/dqr_2.ttl auf die 32 Niveaumatrix-Kernkonzepte
(8 Niveaus x 4 Deskriptorkategorien: Autonomy, Knowledge, Skills,
SocialCompetence).

dqr_2.ttl enthaelt die volle DQR-Niveaumatrix wie in den Rohdateien
data/raw/dqr/DQR_Niveau_1..8.ttl angelegt: acht Schema-Top-Konzepte
(dqr:Level1..Level8), je zwei Gruppierungsknoten (dqr:L*_PersonalCompetence /
dqr:L*_ProfessionalCompetence, mit nivea-uebergreifender skos:broader-Kette)
und darunter je Niveau die vier Deskriptorkategorien mit ihren nummerierten
Unterkonzepten (z.B. dqr:L1_A1_GuidedWork). Fuer dieses Experiment werden nur
die 32 Deskriptorkategorie-Konzepte benoetigt; alle anderen Ebenen werden
entfernt (inkl. aller Tripel, die auf sie verweisen).

Ausgabe: data/formalized/dqr.ttl (32 Konzepte)
Archiv:  data/formalized/dqr_2_extended_experiment_archive.ttl (Original)
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from rdflib import Graph, URIRef

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "formalized"
SRC = DATA_DIR / "dqr_2.ttl"
ARCHIVE = DATA_DIR / "dqr_2_extended_experiment_archive.ttl"
OUT = DATA_DIR / "dqr.ttl"

DQR_NS = "http://data.bmbf.de/dqr/"

# Nummerierte Unterkonzepte je Deskriptorkategorie, z.B. L1_A1_, L2_SC3_.
SUBCONCEPT_RE = re.compile(r"^L[1-8]_(?:SC|A|K|S)\d+_")
# Gruppierungsknoten "Personale Kompetenz" / "Fachkompetenz" je Niveau.
GROUPING_RE = re.compile(r"^L[1-8]_(?:PersonalCompetence|ProfessionalCompetence)$")
# Schema-Top-Konzepte (acht Niveaus).
LEVEL_TOP_RE = re.compile(r"^Level[1-8]$")
# Die zu erhaltenden 32 Ziel-Konzepte.
TARGET_RE = re.compile(r"^L[1-8]_(?:Autonomy|Knowledge|Skills|SocialCompetence)$")


def _local_name(uri: URIRef) -> str | None:
    s = str(uri)
    if not s.startswith(DQR_NS):
        return None
    return s[len(DQR_NS):]


def is_removable(uri: URIRef) -> bool:
    local = _local_name(uri)
    if local is None:
        return False
    return bool(SUBCONCEPT_RE.match(local) or GROUPING_RE.match(local) or LEVEL_TOP_RE.match(local))


def main() -> None:
    if not SRC.exists():
        print(f"Fehler: Eingabedatei nicht gefunden: {SRC}", file=sys.stderr)
        sys.exit(1)

    try:
        shutil.copy2(SRC, ARCHIVE)
    except OSError as exc:
        print(f"Fehler: Archivierung fehlgeschlagen: {exc}", file=sys.stderr)
        sys.exit(1)

    graph = Graph()
    try:
        # Textmodus statt Pfad-Parsing: die Datei enthaelt \r\r\n-Zeilenenden,
        # die der Turtle-Parser als Byte-Stream sonst nicht normalisiert.
        source_text = SRC.read_text(encoding="utf-8")
        graph.parse(data=source_text, format="turtle")
    except Exception as exc:  # rdflib wirft diverse Parser-Exceptions
        print(f"RDF-Parsing-Fehler: {exc}", file=sys.stderr)
        sys.exit(1)

    total_before = len(graph)
    removable_uris = {
        node
        for node in set(graph.subjects()) | set(graph.objects())
        if isinstance(node, URIRef) and is_removable(node)
    }

    out = Graph()
    for prefix, namespace in graph.namespaces():
        out.bind(prefix, namespace, override=True)

    kept = 0
    removed = 0
    for triple in graph:
        subject, _predicate, obj = triple
        if subject in removable_uris or obj in removable_uris:
            removed += 1
        else:
            out.add(triple)
            kept += 1

    try:
        out.serialize(destination=OUT, format="turtle")
    except OSError as exc:
        print(f"Fehler: Ausgabedatei konnte nicht geschrieben werden: {exc}", file=sys.stderr)
        sys.exit(1)

    # Validierung: erneutes Parsen + Konzeptzahl pruefen.
    check = Graph()
    check.parse(OUT, format="turtle")

    top_concepts = set()
    leftover_removable = set()
    for node in set(check.subjects()) | set(check.objects()):
        if not isinstance(node, URIRef):
            continue
        local = _local_name(node)
        if local is None:
            continue
        if TARGET_RE.match(local):
            top_concepts.add(local)
        if is_removable(node):
            leftover_removable.add(local)

    if leftover_removable:
        print(
            f"Fehler: {len(leftover_removable)} unerwuenschte Konzepte verblieben: "
            f"{sorted(leftover_removable)}",
            file=sys.stderr,
        )
        sys.exit(1)
    if len(top_concepts) != 32:
        print(
            f"Fehler: Erwartet 32 Top-Level-Konzepte, gefunden {len(top_concepts)}: "
            f"{sorted(top_concepts)}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"  Removed {removed} triples, kept {kept} triples (vorher {total_before}), 32 top-level concepts")
    print(f"  ✓ Original archiviert: {ARCHIVE.name}")
    print(f"  ✓ Bereinigt: {OUT.name} (32 Konzepte, {kept} Tripel)")
    print("  ✓ Validierung bestanden")


if __name__ == "__main__":
    main()
