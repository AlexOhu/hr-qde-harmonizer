"""
Analysiert, welche skos:Concept-Knoten in data/formalized/esco.ttl kein
skos:definition tragen und ob validate_formalization() (Schritt 1,
app/pipeline/step1_formalization/formalize.py) sie deshalb zu Recht als
Pflichtfeld-Verletzung meldet.

Hintergrund: validate_formalization() ist Alles-oder-nichts -- ein
einziges Konzept ohne skos:definition haelt den kompletten KQR bei Status
'roh' fest (register_kqr ruft get_embeddings() erst nach fehlerfreier
Validierung auf, vgl. scripts/06_run_classification.py). Administrative
ESCO-Klassifikationsknoten (z. B. isced-f/*, Konzept-Schemata, Skill-/
Occupation-Gruppen) liefern in der ESCO-Rohquelle typischerweise keine
Definition -- das ist erwartbar und kein Formalisierungsfehler. Fehlt sie
dagegen bei einem echten Skill/Occupation-Konzept, ist das ein echter
Formalisierungsmangel, der vor der Registrierung behoben werden muss.

Die URI-Klassifikation stuetzt sich auf das ESCO-URI-Schema
"http://data.europa.eu/esco/<klasse>/<id>" (vgl. data/formalized/esco.ttl).
_ADMINISTRATIVE_CLASSES ist eine Einschaetzung, keine offizielle ESCO-
Taxonomie -- die vollstaendige Kategorie-Aufschluesselung im Report dient
dazu, das manuell nachzupruefen statt der Heuristik blind zu vertrauen.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from rdflib import RDF, SKOS, Graph

ROOT = Path(__file__).resolve().parents[1]
ESCO_FILE = ROOT / "data" / "formalized" / "esco.ttl"
REPORT_PATH = ROOT / "data" / "analysis" / "esco_filtering_report.txt"

# ESCO-URI-Klassen, die Taxonomie-/Struktur-Knoten statt eigenstaendige
# Skills/Occupations sind (vgl. http://data.europa.eu/esco/<klasse>/...).
_ADMINISTRATIVE_CLASSES = {
    "isced-f",
    "concept-scheme",
    "skill-group",
    "occupation-group",
    "isco-group",
    "transversal-skill-collection",
    "member-state",
}


def _esco_class(uri: str) -> str:
    """Extrahiert das URI-Klassensegment nach /esco/, z.B. 'isced-f' aus
    'http://data.europa.eu/esco/isced-f/0610'. Faellt auf 'unbekannt'
    zurueck, wenn das Schema nicht passt (z.B. fremder Namespace)."""
    parts = [p for p in urlparse(uri).path.split("/") if p]
    if "esco" in parts:
        idx = parts.index("esco")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return "unbekannt"


def main() -> None:
    if not ESCO_FILE.exists():
        raise SystemExit(f"Fehler: {ESCO_FILE} nicht gefunden.")

    print(f"Lade {ESCO_FILE.relative_to(ROOT)} ...")
    graph = Graph()
    graph.parse(str(ESCO_FILE), format="turtle")

    concept_uris = list(graph.subjects(RDF.type, SKOS.Concept))
    total_concepts = len(concept_uris)

    missing = [str(uri) for uri in concept_uris if not list(graph.objects(uri, SKOS.definition))]

    by_class: dict[str, list[str]] = {}
    for uri in missing:
        by_class.setdefault(_esco_class(uri), []).append(uri)

    isced_f = by_class.get("isced-f", [])
    administrative = {cls: uris for cls, uris in by_class.items() if cls in _ADMINISTRATIVE_CLASSES}
    administrative_count = sum(len(uris) for uris in administrative.values())
    real_missing: dict[str, list[str]] = {
        cls: uris for cls, uris in by_class.items() if cls not in _ADMINISTRATIVE_CLASSES
    }
    real_missing_count = sum(len(uris) for uris in real_missing.values())

    summary = (
        f"{len(missing)} Konzepte ohne Definition, "
        f"{administrative_count} sind administrative Klassen (u.a. {len(isced_f)} ISCED-F, ausgeschlossen), "
        f"{real_missing_count} sind echte Skills/Occupations (sollten Definition haben)"
    )
    print(f"\n{summary}")

    lines: list[str] = []
    lines.append("ESCO-Filtering-Analyse: skos:Concept ohne skos:definition")
    lines.append(f"Quelle: {ESCO_FILE.relative_to(ROOT)}")
    lines.append(f"Gesamtzahl skos:Concept: {total_concepts}")
    lines.append("")
    lines.append(summary)
    lines.append("")
    lines.append("Aufschluesselung nach ESCO-URI-Klasse (/esco/<klasse>/...):")
    for cls, uris in sorted(by_class.items(), key=lambda item: -len(item[1])):
        marker = "administrativ" if cls in _ADMINISTRATIVE_CLASSES else "ECHTER SKILL/OCCUPATION-VERDACHT"
        lines.append(f"  {cls}: {len(uris)} ({marker})")
    lines.append("")

    if real_missing_count:
        lines.append("Konzepte, die vor der Registrierung geprueft/ergaenzt werden sollten:")
        for cls, uris in sorted(real_missing.items()):
            lines.append(f"  -- Klasse '{cls}' --")
            for uri in uris:
                lines.append(f"    {uri}")
    else:
        lines.append("Keine echten Skill-/Occupation-Konzepte ohne Definition gefunden.")

    lines.append("")
    lines.append("Vollstaendige Liste aller Konzepte ohne skos:definition:")
    for cls, uris in sorted(by_class.items()):
        for uri in uris:
            lines.append(f"  [{cls}] {uri}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report gespeichert unter {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
