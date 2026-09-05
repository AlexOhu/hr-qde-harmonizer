"""
Baut einen kleinen, vollstaendig durchlaufbaren DQR x ESCO Slice fuer den
Cognitive Walkthrough (Kapitel 4.5, Funktionsgruppen 1-5).

Quelle sind KEINE neu erzeugten/mock Daten, sondern die bereits real
klassifizierten Mappings aus data/projects/default/mappings.json fuer die
vier Level-6-Kategorien des DQR (Wissen, Fertigkeiten, Sozialkompetenz,
Selbststaendigkeit), die im bestehenden Projekt schon durchklassifiziert
wurden.

WICHTIG: harmonised_ontology.ttl im Projekt typisiert aktuell ALLE DQR-
Konzepte als hrqde:HarmonisedConcept. Das ist nach der korrigierten Spec
(MASTERAND_OBERHUBER.md v0.2, Abschnitt 3) falsch: HarmonisedConcept ist
der disjunkte Fall. Ein Konzept mit ESCO-Gegenstueck bleibt ein simples
skos:Concept mit harm:derivedFrom. Dieses Skript korrigiert das beim Bau
des Slice, es kopiert die falsche Typisierung nicht.
"""

import json
from datetime import date, timezone, datetime
from pathlib import Path

BASE = Path(r"E:\Fernuni\Master\Masterarbeit\hrqde-harmonizer")
MAPPINGS = BASE / "data/projects/default/mappings.json"
ESCO_SRC = BASE / "data/raw/esco_v1_2_ict_ausschnitt.ttl"
OUT_DIR = BASE / "data/walkthrough_slice"
OUT_DIR.mkdir(exist_ok=True)

# Die vier Level-6-Kategorien, siehe harmonised_ontology.ttl
TARGET_SUBJECTS = {
    "http://data.bmbf.de/dqr/L6_Knowledge": "Wissen - Niveau 6",
    "http://data.bmbf.de/dqr/L6_Skills": "Fertigkeiten - Niveau 6",
    "http://data.bmbf.de/dqr/L6_SocialCompetence": "Sozialkompetenz - Niveau 6",
    "http://data.bmbf.de/dqr/L6_Autonomy": "Selbststaendigkeit - Niveau 6",
}

def load_mappings():
    with open(MAPPINGS, "r", encoding="utf-8") as f:
        records = json.load(f)
    filtered = [r for r in records if r["subject_id"] in TARGET_SUBJECTS]
    print(f"{len(filtered)} Mapping-Records fuer die vier Zielkonzepte gefunden.")
    return filtered


def split_by_review_status(records):
    """Konjunkte Mappings gehen in die Ontologie/SSSOM-Slice, alles andere
    (related/unresolved/disjoint) wird gesondert dokumentiert, analog zur
    Trennung in Abschnitt 6 der Spec (Integrationsstrategien)."""
    conjunct = [r for r in records if r.get("review_status") == "conjunct"]
    other = [r for r in records if r.get("review_status") != "conjunct"]
    print(f"  davon konjunkt: {len(conjunct)}, sonstige: {len(other)}")
    return conjunct, other


def collect_esco_targets(records):
    return sorted({r["object_id"] for r in records})

def extract_esco_context(esco_uris):
    """Laedt aus dem ICT-Ausschnitt die prefLabel und eine Ebene
    skos:broader je referenziertem ESCO-Konzept, damit der Slice im UI
    nicht als Menge isolierter Blattknoten erscheint."""
    from rdflib import Graph, URIRef
    from rdflib.namespace import SKOS

    g = Graph()
    g.parse(ESCO_SRC, format="turtle")

    context = {}
    broader_uris = set()
    for uri in esco_uris:
        node = URIRef(uri)
        labels = list(g.objects(node, SKOS.prefLabel))
        label = str(labels[0]) if labels else "(kein prefLabel im Ausschnitt gefunden)"
        broader = [str(b) for b in g.objects(node, SKOS.broader)]
        context[uri] = {"label": label, "broader": broader}
        broader_uris.update(broader)

    # eine Ebene Kontext ergaenzen
    for uri in broader_uris:
        if uri in context:
            continue
        node = URIRef(uri)
        labels = list(g.objects(node, SKOS.prefLabel))
        context[uri] = {
            "label": str(labels[0]) if labels else "(kein prefLabel)",
            "broader": [],
        }
    return context

def write_ontology_ttl(conjunct, esco_context):
    """Die vier DQR-Konzepte als schlichte skos:Concept mit harm:derivedFrom,
    NICHT als harm:HarmonisedConcept (das ist per Spec der disjunkte Fall,
    diese vier haben ESCO-Entsprechungen)."""
    lines = [
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "@prefix harm: <http://hr-qde.org/harmonised/> .",
        "@prefix dqr: <http://data.bmbf.de/dqr/> .",
        "",
        "<http://hr-qde.org/harmonised/walkthrough-slice>",
        "    a owl:Ontology ;",
        '    dcterms:source "mappings.json, gefiltert auf L6_Knowledge/Skills/SocialCompetence/Autonomy" ;',
        f'    dcterms:created "{date.today().isoformat()}"^^xsd:date ;',
        '    owl:versionInfo "0.1-walkthrough" .',
        "",
        "# Abschnitt 3: harm:KQR ist der Wertebereich von harm:derivedFrom,",
        "# die Quellrahmen-Entitaet selbst muss typisiert werden.",
        "# Quelle ist dqr_2 (196 Konzepte, granularer Reformalisierungs-",
        "# versuch), NICHT dqr_2013 (32 Konzepte, registriert, aber ohne",
        "# die hier verwendeten L6-Kategorie-Mappings). dqr_2 ist WEDER in",
        "# kqr_registry.json NOCH in project.json referenziert -- das ist",
        "# ein offener Punkt in der Projektkonfiguration, keine Annahme",
        "# dieses Skripts.",
        "<http://hr-qde.org/harmonised/kqr/dqr_2> a harm:KQR ;",
        '    skos:prefLabel "DQR (Reformalisierung dqr_2, unregistriert)"@de .',
        "",
    ]
    for subj_uri, subj_label in TARGET_SUBJECTS.items():
        lines.append(f"<{subj_uri}> a skos:Concept ;")
        lines.append(f'    skos:prefLabel "{subj_label}"@de ;')
        lines.append("    harm:derivedFrom <http://hr-qde.org/harmonised/kqr/dqr_2> .")
        lines.append("")

    out = OUT_DIR / "walkthrough-dqr-esco-ontology.ttl"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"geschrieben: {out}")

def write_sssom_ttl(conjunct):
    """Reifizierte SSSOM-Records gemaess Abschnitt 5 der Spec: predicate_id
    als IRI, nicht als String; ein sssom:MappingSet als Container."""
    lines = [
        "@prefix sssom: <https://w3id.org/sssom/> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix semapv: <https://w3id.org/semapv/vocab/> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "@prefix harm: <http://hr-qde.org/harmonised/> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "",
        "<http://hr-qde.org/harmonised/walkthrough-slice/mappingset>",
        "    a sssom:MappingSet ;",
        "    sssom:mappings",
    ]
    # Abschnitt 4 (Coverage-Tabelle): ESCO-Skill-Ziele -> harm:HubMapping
    # (zaehlt zur Coverage), ESCO-Beruf-Ziele -> harm:OccupationMapping
    # (zaehlt NICHT, Begruendung erforderlich). Nicht pauschal annehmen,
    # dass alle Ziele Skills sind -- pruefen.
    mapping_blocks = []
    n_hub, n_occ = 0, 0
    for i, r in enumerate(conjunct):
        pred = r["predicate_id"].replace("skos:", "")
        just = r["mapping_justification"].replace("semapv:", "")
        if "/esco/occupation/" in r["object_id"]:
            coverage_type = "harm:OccupationMapping"
            n_occ += 1
            begruendung = (
                f'          rdfs:comment "Begruendung (Coverage-Ausnahme, Abschnitt 4): '
                f'{(r.get("justification") or "").replace(chr(34), chr(39))}"@de ;\n'
            )
        else:
            coverage_type = "harm:HubMapping"
            n_hub += 1
            begruendung = ""
        block = (
            f"        [ a sssom:Mapping, {coverage_type} ;\n"
            f'          sssom:subject_id <{r["subject_id"]}> ;\n'
            f'          sssom:object_id <{r["object_id"]}> ;\n'
            f"          sssom:predicate_id skos:{pred} ;\n"
            f'          sssom:mapping_confidence "{r["mapping_confidence"]}"^^xsd:decimal ;\n'
            f"          sssom:mapping_justification semapv:{just} ;\n"
            f"{begruendung}"
            f'          sssom:mapping_tool "{r["mapping_tool"]}" ]'
        )
        mapping_blocks.append(block)
    print(f"  Coverage-Typisierung: {n_hub}x HubMapping, {n_occ}x OccupationMapping")
    lines.append(",\n".join(mapping_blocks) + " .")

    out = OUT_DIR / "walkthrough-dqr-esco-mappings.ttl"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"geschrieben: {out}")

def write_strategy_doc(other_records):
    lines = [
        "# Integrationsstrategie - Walkthrough-Slice DQR Level 6",
        "",
        "Slice aus den vier DQR-Level-6-Kategorien (Wissen, Fertigkeiten, ",
        "Sozialkompetenz, Selbststaendigkeit) gegen den ESCO-IKT-Ausschnitt.",
        "Quelle: bereits durchklassifizierte Mappings aus dem Hauptprojekt, ",
        "gefiltert auf review_status=conjunct fuer die Ontologie/SSSOM-Slice.",
        "",
        "## Nicht-konjunkte Records (nicht in der Ontologie-Slice enthalten)",
        "",
        "| Subjekt | Objekt | review_status | Anmerkung |",
        "|---|---|---|---|",
    ]
    if not other_records:
        lines.append("| - | - | - | keine, alle Records waren konjunkt |")
    else:
        for r in other_records:
            lines.append(
                f'| {r["subject_id"].rsplit("/",1)[-1]} | '
                f'{r.get("object_label","?")} | {r.get("review_status","?")} | '
                f'{(r.get("justification") or "")[:80]} |'
            )

    out = OUT_DIR / "walkthrough-integration-strategy.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"geschrieben: {out}")


if __name__ == "__main__":
    records = load_mappings()
    conjunct, other = split_by_review_status(records)
    esco_uris = collect_esco_targets(conjunct)
    context = extract_esco_context(esco_uris)
    write_ontology_ttl(conjunct, context)
    write_sssom_ttl(conjunct)
    write_strategy_doc(other)
    print(f"\nFertig. {len(esco_uris)} eindeutige ESCO-Konzepte im Slice.")
