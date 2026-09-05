"""
E5 – Kompetenzfragen-Evaluation CQ1–CQ4 (qualitativ)

Fuehrt vier SPARQL-Abfragen auf der materialisierten Basisontologie aus und
protokolliert Treffer und Beispiel-Ergebnisse.

Zwei Modi:

  --legacy  (Default): eine kombinierte Turtle-Datei mit direkten
            SKOS-Kanten (alter ``ontology_export.py``-Aufbau).

  --delivery DIR: die drei Lieferartefakte nach ``MASTERAND_OBERHUBER.md``
            v0.2 (``oberhuber-harmonised-ontology-v*.ttl`` +
            ``oberhuber-mappings-v*.ttl``). Mappings liegen dort reifiziert
            als ``harm:HubMapping``/``harm:LevelMapping`` mit
            ``sssom:subject_id``/``sssom:object_id``/``sssom:predicate_id``;
            ESCO-Knoten tragen keine Labels (Lieferspezifikation §4), fuer
            lesbare Beispiele wird optional das ESCO-Skelett geladen.

Verwendung:
    python eval/E5_cq_evaluation.py --legacy --ontology <datei.ttl>
    python eval/E5_cq_evaluation.py --delivery . \
        --output eval/results/E5_cq_evaluation.json
    python eval/E5_cq_evaluation.py --report
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ONTOLOGY_PATH = ROOT / "data" / "ontology" / "harmonised_ontology.ttl"
OUTPUT_DIR = ROOT / "eval" / "results"
ESCO_SKELETON = ROOT / "data" / "formalized" / "esco_skeleton_oberhuber.ttl"

# -----------------------------------------------------------------------
# Legacy-Queries: direkte SKOS-Kanten in einer kombinierten Datei
# -----------------------------------------------------------------------
_QUERIES = {
    "CQ1": {
        "label": "Semantisch äquivalente Konzeptpaare (exactMatch)",
        "sparql": """
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>
SELECT ?subjectLabel ?objectLabel
WHERE {
  ?subject skos:exactMatch ?object .
  ?subject skos:prefLabel  ?subjectLabel .
  ?object  skos:prefLabel  ?objectLabel  .
  FILTER(LANG(?subjectLabel) = "en")
  FILTER(LANG(?objectLabel)  = "en")
}
ORDER BY ?subjectLabel
""",
    },
    "CQ2": {
        "label": "Subsumierte ESCO-Konzepte unter e-CF-Bereichen (narrowMatch)",
        "sparql": """
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>
SELECT ?ecfLabel ?escoLabel
WHERE {
  ?ecfConcept skos:narrowMatch ?escoConcept .
  ?ecfConcept skos:prefLabel   ?ecfLabel   .
  ?escoConcept skos:prefLabel  ?escoLabel  .
  FILTER(STRSTARTS(STR(?ecfConcept), "http://hr-qde.org/harmonised/ecf/"))
  FILTER(LANG(?ecfLabel)  = "en")
  FILTER(LANG(?escoLabel) = "en")
}
ORDER BY ?ecfLabel
""",
    },
    "CQ3": {
        "label": "Disjunkte Konzepte ohne ESCO-Pendant",
        "sparql": """
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>
PREFIX harm:  <http://hr-qde.org/harmonised/>
SELECT ?concept ?label ?strategy
WHERE {
  ?concept a harm:HarmonisedConcept ;
           skos:prefLabel           ?label ;
           harm:integrationStrategy ?strategy .
  FILTER NOT EXISTS {
    { ?concept skos:exactMatch  ?e }
    UNION { ?concept skos:narrowMatch ?e }
    UNION { ?concept skos:broadMatch  ?e }
    FILTER(STRSTARTS(STR(?e), "http://data.europa.eu/esco/"))
  }
  FILTER(LANG(?label) = "en")
}
""",
    },
    "CQ4": {
        "label": "Transitive Hierarchie (rdfs:subClassOf+) für einen Beispiel-Cluster",
        "sparql": """
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?ancestor ?ancestorLabel
WHERE {
  ?leaf rdfs:subClassOf+ ?ancestor .
  ?ancestor rdfs:label   ?ancestorLabel .
  FILTER(STRSTARTS(STR(?leaf), "http://hr-qde.org/harmonised/cluster/"))
  FILTER(LANG(?ancestorLabel) = "en")
}
LIMIT 20
""",
    },
}

# -----------------------------------------------------------------------
# Delivery-Queries: reifizierte harm:HubMapping-Records + Skelett-Labels
# -----------------------------------------------------------------------
_DELIVERY_QUERIES = {
    "CQ1": {
        "label": "Semantisch äquivalente Konzeptpaare (harm:HubMapping, skos:exactMatch)",
        "sparql": """
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>
PREFIX sssom: <https://w3id.org/sssom/>
PREFIX harm:  <http://hr-qde.org/harmonised/>
SELECT ?subject ?object
WHERE {
  ?m a harm:HubMapping ;
     sssom:subject_id   ?subject ;
     sssom:object_id    ?object ;
     sssom:predicate_id skos:exactMatch .
}
""",
    },
    "CQ2": {
        "label": "Subsumierte ESCO-Skills unter e-CF-Konzepten (harm:HubMapping, skos:narrowMatch)",
        "sparql": """
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>
PREFIX sssom: <https://w3id.org/sssom/>
PREFIX harm:  <http://hr-qde.org/harmonised/>
SELECT ?ecfLabel ?escoLabel
WHERE {
  ?m a harm:HubMapping ;
     sssom:subject_id   ?ecfConcept ;
     sssom:object_id    ?escoConcept ;
     sssom:predicate_id skos:narrowMatch .
  FILTER(STRSTARTS(STR(?ecfConcept), "http://hr-qde.org/harmonised/ecf/"))
  ?ecfConcept  skos:prefLabel ?ecfLabel .
  FILTER(LANG(?ecfLabel) = "en")
  OPTIONAL { ?escoConcept skos:prefLabel ?escoLabel . FILTER(LANG(?escoLabel) = "en") }
}
ORDER BY ?ecfLabel
""",
    },
    "CQ3": {
        "label": "Disjunkte Konzepte mit Integrationsstrategie (harm:HarmonisedConcept)",
        "sparql": """
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>
PREFIX harm:  <http://hr-qde.org/harmonised/>
SELECT ?concept ?label ?strategy
WHERE {
  ?concept a harm:HarmonisedConcept ;
           harm:integrationStrategy ?strategy .
  OPTIONAL { ?concept skos:prefLabel ?label . FILTER(LANG(?label) = "en") }
}
ORDER BY ?concept
""",
    },
    "CQ4": {
        "label": "Transitive Hierarchie (rdfs:subClassOf+ / harm:harmonises)",
        "sparql": """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX harm: <http://hr-qde.org/harmonised/>
SELECT ?child ?ancestor
WHERE {
  { ?child rdfs:subClassOf+ ?ancestor }
  UNION
  { ?cluster a harm:HarmonisedCluster ; harm:harmonises ?child . BIND(?cluster AS ?ancestor) }
}
LIMIT 20
""",
    },
}


def run_query(g, sparql: str) -> list[dict]:
    rows = []
    for row in g.query(sparql):
        rows.append({str(k): str(v) for k, v in zip(row.labels, row) if v is not None})
    return rows


def run_experiment(ontology_paths: list[Path], queries: dict, label_paths: list[Path] | None = None) -> list[dict]:
    from rdflib import Graph

    g = Graph()
    for p in ontology_paths:
        print(f"Lade: {p}")
        g.parse(str(p), format="turtle")
    for p in label_paths or []:
        if p.exists():
            print(f"Lade Labels: {p}")
            g.parse(str(p), format="turtle")
    print(f"Tripel gesamt: {len(g)}\n")

    results = []
    for cq_id, cq in queries.items():
        print(f"{cq_id}: {cq['label']} ...", end=" ", flush=True)
        rows = run_query(g, cq["sparql"].strip())
        fulfilled = len(rows) > 0
        print(f"{len(rows)} Treffer  -> {'erfuellt' if fulfilled else 'NICHT erfuellt'}")
        results.append({
            "cq": cq_id,
            "label": cq["label"],
            "n_results": len(rows),
            "fulfilled": fulfilled,
            "examples": rows[:3],
        })
    return results


def report(results: list[dict]) -> None:
    print("\n--- E5: Kompetenzfragen-Evaluation ---")
    print(f"{'CQ':>4} {'Treffer':>8} {'Erfuellt':>9}  Bezeichnung")
    print("-" * 60)
    for r in results:
        status = "JA" if r["fulfilled"] else "NEIN"
        print(f"{r['cq']:>4} {r['n_results']:>8} {status:>9}  {r['label']}")
    print()
    for r in results:
        if r["examples"]:
            print(f"{r['cq']} - Beispiele:")
            for ex in r["examples"]:
                print(f"  {ex}")
        else:
            print(f"{r['cq']}: keine Treffer")
        print()


def _delivery_artifacts(base: Path) -> list[Path]:
    onto = sorted(glob.glob(str(base / "oberhuber-harmonised-ontology-v*.ttl")))
    maps = sorted(glob.glob(str(base / "oberhuber-mappings-v*.ttl")))
    onto = [p for p in onto if not p.endswith(".bak")]
    if not onto or not maps:
        raise SystemExit(f"Lieferartefakte nicht gefunden in {base}")
    return [Path(onto[-1]), Path(maps[-1])]


def main() -> None:
    parser = argparse.ArgumentParser(description="E5: Kompetenzfragen-Evaluation")
    parser.add_argument("--ontology", type=Path, default=ONTOLOGY_PATH,
                        help="Legacy-Modus: kombinierte Turtle-Datei")
    parser.add_argument("--delivery", type=Path, default=None,
                        help="Verzeichnis mit den drei Lieferartefakten (v0.2)")
    parser.add_argument("--legacy", action="store_true",
                        help="Legacy-Modus erzwingen (Default, wenn --delivery fehlt)")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / "E5_cq_evaluation.json")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    if args.report:
        data = json.loads(args.output.read_text(encoding="utf-8"))
        report(data["results"])
        return

    if args.delivery is not None:
        paths = _delivery_artifacts(args.delivery)
        results = run_experiment(paths, _DELIVERY_QUERIES, label_paths=[ESCO_SKELETON])
        mode = "delivery"
    else:
        if not args.ontology.exists():
            raise SystemExit(f"Ontologie nicht gefunden: {args.ontology}")
        results = run_experiment([args.ontology], _QUERIES)
        mode = "legacy"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"mode": mode, "results": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nErgebnis gespeichert: {args.output}")
    report(results)


if __name__ == "__main__":
    main()
