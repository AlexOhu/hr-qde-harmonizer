"""
Schritt 4a: Export der Klassifikationsergebnisse als SSSOM-TSV.

Feldschema gemäß Tabelle 3.9:
subject_id, subject_label, object_id, object_label, predicate_id,
mapping_confidence, mapping_tool, mapping_justification.

Mappings mit mapping_confidence < MAPPING_CONFIDENCE_THRESHOLD werden laut
Konzeption NICHT ausgeliefert (vgl. Tabelle 3.9) — hier filtern, nicht in
der UI verstecken. Dasselbe gilt für Mappings mit offenem Review-Status:
sie sind persistiert und über /mappings/ entscheidbar, gehören aber bis zur
Entscheidung nicht in ein Exportartefakt.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.models.schemas import (
    ClassificationResult,
    Mapping,
    MappingJustification,
    RelationType,
    ReviewStatus,
    SSSOMRecord,
)

_SSSOM_HEADER = "\n".join([
    "# mapping_set_version: \"0.15\"",
    "# mapping_tool: HR-QDE-Harmonizer-v0.1",
    "# curie_map:",
    "#   semapv: \"https://w3id.org/semapv/vocab/\"",
    "#   skos: \"http://www.w3.org/2004/02/skos/core#\"",
    # ADR-19: harm: ist das Kürzel der Harmonisierungsschicht, hrqde: bleibt
    # dem HR-QDE-Skelett vorbehalten.
    "#   harm: \"http://hr-qde.org/harmonised/\"",
    "#   hrqde: \"http://hr-qde.org/ontology/\"",
    "",
])

def _is_open(final_relation: RelationType | None) -> bool:
    """RELATED und der fehlende Mehrheitsentscheid (final_relation=None) sind
    nicht Bestandteil der konjunkten Menge K. Sie werden trotzdem als
    Mapping-Objekt mit stabiler mapping_id persistiert (ReviewStatus.OPEN);
    erst PUT /mappings/{id}/review entscheidet, ob daraus ein K-Mapping
    (CONJUNCT) oder ein disjunktes Konzept (DISJUNCT) wird. Vorher bleiben sie
    aus allen Exportartefakten heraus."""
    return final_relation is None or final_relation == RelationType.RELATED


def classification_results_to_mappings(
    results: list[ClassificationResult],
    concept_lookup: dict[str, dict],
) -> list[Mapping]:
    """
    Wandelt ClassificationResult-Objekte in dokumentierte Mapping-Objekte um.

    concept_lookup: Concept.uri -> {"pref_label": ..., "kqr_id": ...}

    Jedes Kandidatenpaar wird materialisiert, auch RELATED-Ergebnisse und
    Paare ohne LLM-Mehrheitsentscheid (predicate_id=None): Diese Fälle
    bekommen ReviewStatus.OPEN und sind damit über /mappings/ erreichbar und
    per PUT /mappings/{id}/review entscheidbar. Vorher waren sie nur flüchtige
    Objekte im Prüfbericht ohne stabile mapping_id.

    mapping_justification ist hier stets semapv:LLMBasedMatching: strukturell
    ableitbare Paare erzeugt find_structural_shortcuts() vorgelagert direkt
    als Mapping (semapv:StructuralMatching) und durchlaufen diese Funktion nie.
    """
    mappings: list[Mapping] = []
    for result in results:
        subject_info = concept_lookup[result.pair.concept_a]
        object_info = concept_lookup[result.pair.concept_b]
        majority_reasoning = next(
            (run.reasoning for run in result.runs if run.relation == result.final_relation),
            "",
        )
        is_open = _is_open(result.final_relation)
        # Fehlender Mehrheitsentscheid: kein Praedikat bis zur Review-
        # Entscheidung. Ein offenes RELATED traegt dagegen skos:relatedMatch.
        # subject = Konzept A, object = Konzept B; to_skos_predicate() folgt
        # der SKOS-Richtung (A_SUBSUMES_B -> skos:narrowMatch).
        predicate_id = (
            None if result.final_relation is None else result.final_relation.to_skos_predicate()
        )

        mappings.append(
            Mapping(
                subject_id=result.pair.concept_a,
                subject_label=subject_info["pref_label"],
                subject_kqr_id=subject_info.get("kqr_id"),
                object_id=result.pair.concept_b,
                object_label=object_info["pref_label"],
                object_kqr_id=object_info.get("kqr_id"),
                predicate_id=predicate_id,
                mapping_confidence=result.mapping_confidence,
                mapping_justification=MappingJustification.LLM_BASED_MATCHING,
                mapping_source="algorithmic",
                review_status=ReviewStatus.OPEN if is_open else ReviewStatus.CONJUNCT,
                justification=majority_reasoning,
            )
        )
    return mappings


def write_sssom_tsv(
    mappings: list[Mapping],
    output_path: Path,
    confidence_threshold: float,
) -> Path:
    """
    Schreibt die Mapping-Liste als SSSOM-konforme TSV-Datei.

    Mappings unterhalb von confidence_threshold werden NICHT geschrieben,
    sondern separat für die manuelle Validierung vorgehalten — siehe
    Abschnitt 3.7.3. Ebenso ausgeschlossen sind Mappings mit
    ReviewStatus.OPEN (noch nicht entschiedene RELATED/UNRESOLVED-Paare) und
    ReviewStatus.DISJUNCT (im Review als "kein Mapping" entschieden; die
    Integrationsstrategie steht stattdessen in disjoint_decisions.json).
    """
    filtered = [
        m
        for m in mappings
        if m.review_status == ReviewStatus.CONJUNCT
        and m.mapping_confidence >= confidence_threshold
    ]
    records = [SSSOMRecord.from_mapping(m) for m in filtered]
    df = pd.DataFrame([r.model_dump() for r in records])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(_SSSOM_HEADER)
        df.to_csv(fh, sep="\t", index=False)
    return output_path
