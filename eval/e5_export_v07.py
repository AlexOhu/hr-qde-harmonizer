"""
E5-Vorbereitung (Re-Run 2026-08-31): frischer Ontologie-Export aus dem
Projekt "IKT Slice V0.7" (neuer Klassifikationsprompt, = Seed von
oberhuber-harmonised-ontology-v0.3.ttl) fuer die CQ1-CQ4-Auswertung.

Schritte:
  1. Clustering (HDBSCAN m*=3) ueber ESCO + e-CF im V0.7-Projekt
     (Raum 1001, analog E4-Entscheidung 2026-08-31: nur harm:CompetenceConcept).
  2. Disjunkte Konzepte automatisiert per suggest_strategy() entscheiden
     (wie im Original-E5 vom 2026-07-29 -- keine manuelle Einzelpruefung,
     als Limitation dokumentiert).
  3. export_ontology() nach eval/results/e5_v07_harmonised.ttl.

Kein LLM-Aufruf. Danach:
  python eval/E5_cq_evaluation.py --ontology eval/results/e5_v07_harmonised.ttl \
      --output eval/results/E5_cq_evaluation.json
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROJECT_ID = "hr_qde_basisontologie_ikt_slice_v0_7_20260830T183521Z"
CLUSTER_KQR_IDS = ["esco_v1_2_ict_ausschnitt", "ecf"]
MIN_CLUSTER_SIZE = 3  # E4 (Kapitel 5)
OUT_TTL = ROOT / "eval" / "results" / "e5_v07_harmonised.ttl"


def main() -> None:
    from app.services import disjoint_service, mapping_service, ontology_service
    from app.pipeline.step4_export.ontology_export import export_ontology

    print(f"Projekt: {PROJECT_ID}")

    print("1) Clustering ...")
    clusters_raw = ontology_service.run_clustering(
        CLUSTER_KQR_IDS, min_cluster_size=MIN_CLUSTER_SIZE, project_id=PROJECT_ID
    )
    harmonised_clusters = ontology_service.get_harmonised_clusters(project_id=PROJECT_ID)
    print(f"   ClusterResults: {len(clusters_raw)}  HarmonisedCluster (ohne Noise): {len(harmonised_clusters)}")

    print("2) Disjunkte Konzepte automatisiert entscheiden ...")
    disj = disjoint_service.list_disjoint_concepts(project_id=PROJECT_ID)
    existing = {d.concept_id for d in disjoint_service.list_decisions(project_id=PROJECT_ID)}
    decided = 0
    for concept in disj:
        if concept.uri in existing:
            continue
        strategy = disjoint_service.suggest_strategy(concept, project_id=PROJECT_ID)
        disjoint_service.decide(
            concept_id=concept.uri,
            strategy=strategy,
            justification="E5-Re-Run 2026-08-31: automatisierte suggest_strategy()-Entscheidung "
            "(keine manuelle Einzelpruefung, vgl. eval/PROTOKOLL.md).",
            author="eval_e5_rerun_20260831",
            project_id=PROJECT_ID,
        )
        decided += 1
    decisions = disjoint_service.list_decisions(project_id=PROJECT_ID)
    print(f"   disjunkte Konzepte: {len(disj)}  neu entschieden: {decided}  Entscheidungen gesamt: {len(decisions)}")

    print("3) Ontologie exportieren ...")
    mappings = mapping_service.list_mappings(project_id=PROJECT_ID)
    OUT_TTL.parent.mkdir(parents=True, exist_ok=True)
    export_ontology(mappings, harmonised_clusters, decisions, "turtle", OUT_TTL)

    from rdflib import Graph

    g = Graph()
    g.parse(str(OUT_TTL), format="turtle")
    print(f"   {OUT_TTL}  ({len(g)} Tripel)")


if __name__ == "__main__":
    main()
