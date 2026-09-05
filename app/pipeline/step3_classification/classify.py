"""
Schritt 3: LLM-gestützte Klassifikation von Kandidatenpaaren.

Entspricht Abschnitt 3.5.2. Jedes CandidatePair wird DREIFACH klassifiziert
(unabhängige Anfragen, temperature=0), die finale Relation ergibt sich per
Mehrheitsentscheid. Der Anteil übereinstimmender Läufe wird als
mapping_confidence dokumentiert (SSSOM-Feld, Tabelle 3.9).

Nicht-Determinismus ist eine AKZEPTIERTE Randbedingung (vgl. VH1.6/VH1.7),
kein Bug — also niemals nur einen Lauf ausführen und als "Ergebnis"
behandeln, auch nicht während der Entwicklung/zum Testen.

Paare ohne Mehrheitsentscheid erhalten final_relation=None und werden
der manuellen Validierung zugeführt (vgl. Abschnitt 3.7.3, FZ3.2).

Mehrere Provider (LLM_PROVIDERS=anthropic,openai,gemini): Läufe werden
per Round-Robin auf die Provider verteilt. Bei einem Provider verhält sich
die Klassifikation identisch zum ursprünglichen Einzelanbieter-Modus.
"""

from __future__ import annotations

from collections import Counter

from app.models.schemas import (
    CandidatePair,
    ClassificationResult,
    ClassificationRun,
    RelationType,
)
from app.pipeline.step3_classification.llm_provider.base import LLMProvider

PROMPT_TEMPLATE_PATH = "prompts/classification_prompt_template.txt"

# Alle vier RelationType-Werte darf ein einzelner Modell-Lauf erzeugen
# (Block 4 des Prompts). Fehlender Mehrheitsentscheid ist kein Relationswert,
# sondern final_relation=None (majority_vote()).
_LLM_PRODUCIBLE_RELATIONS = set(RelationType)


class ClassificationParseError(RuntimeError):
    """Antwort des Klassifikations-LLM entspricht nicht dem Format 'RELATION | Begründung'."""


def build_prompt(
    concept_a_pref_label: str,
    concept_a_definition: str,
    concept_a_kqr: str,
    concept_b_pref_label: str,
    concept_b_definition: str,
    concept_b_kqr: str,
    few_shot_examples: str,
) -> str:
    """Füllt das Vier-Block-Prompt-Template (prompts/classification_prompt_template.txt)."""
    template = open(PROMPT_TEMPLATE_PATH, encoding="utf-8").read()
    return template.format(
        concept_a_pref_label=concept_a_pref_label,
        concept_a_definition=concept_a_definition,
        concept_a_kqr=concept_a_kqr,
        concept_b_pref_label=concept_b_pref_label,
        concept_b_definition=concept_b_definition,
        concept_b_kqr=concept_b_kqr,
        few_shot_examples=few_shot_examples,
    )


def call_classification_model(prompt: str, provider: LLMProvider) -> ClassificationRun:
    """
    Ein einzelner LLM-Aufruf zur Pair-Klassifikation über einen beliebigen Provider.

    Erwartetes Antwortformat: "RELATION | Begründung" (Block 4 des Prompts).
    Parsing-Fehler degradieren NICHT stillschweigend zu RELATED, sondern
    werfen ClassificationParseError als eigenen Fehlerfall.

    provider.model_id wird in ClassificationRun.model gespeichert (FA4).
    """
    text = provider.complete(prompt)

    if "|" not in text:
        raise ClassificationParseError(f"Unerwartetes Antwortformat (kein '|'): {text!r}")

    relation_str, _, reasoning = text.partition("|")
    relation_str = relation_str.strip()
    reasoning = reasoning.strip()

    try:
        relation = RelationType(relation_str)
    except ValueError as exc:
        raise ClassificationParseError(
            f"Unbekannte Relation '{relation_str}' in Antwort: {text!r}"
        ) from exc

    if relation not in _LLM_PRODUCIBLE_RELATIONS:
        raise ClassificationParseError(
            f"Relation '{relation_str}' darf nicht direkt vom Modell erzeugt werden: {text!r}"
        )

    return ClassificationRun(
        relation=relation,
        reasoning=reasoning,
        model=provider.model_id,
        temperature=0.0,
    )


def majority_vote(runs: list[ClassificationRun]) -> tuple[RelationType | None, float]:
    """
    Bestimmt die finale Relation per Mehrheitsentscheid über N Läufe.

    Rückgabe: (finale Relation, mapping_confidence).
    Kein eindeutiger Mehrheitsentscheid → (None, confidence).
    """
    if not runs:
        raise ValueError("Mindestens ein ClassificationRun erforderlich.")

    counts = Counter(run.relation for run in runs)
    relation, count = counts.most_common(1)[0]
    confidence = count / len(runs)

    # Echter Gleichstand (z.B. 1/1/1 bei drei Läufen) → kein Mehrheitsentscheid.
    tied = [r for r, c in counts.items() if c == count]
    if len(tied) > 1:
        return None, confidence

    return relation, confidence


def classify_pair(
    pair: CandidatePair,
    concept_a_data: dict,
    concept_b_data: dict,
    few_shot_examples: str,
    providers: list[LLMProvider],
    runs_per_pair: int,
) -> ClassificationResult:
    """
    Orchestriert Prompt-Bau, N-fachen Modellaufruf und Mehrheitsentscheid.

    Läufe werden per Round-Robin auf die Provider-Liste verteilt:
      providers=[A]       → A, A, A  (Standardfall, ein Anbieter)
      providers=[A, B, C] → A, B, C  (ein Lauf je Anbieter)
      providers=[A, B]    → A, B, A  (bei runs_per_pair=3)

    Diese Verteilung ermöglicht eine anbieterübergreifende Mehrheitsentscheidung
    und damit eine zusätzliche Robustheitsprüfung (vgl. Kapitel 4, ADR-7).
    """
    if not providers:
        raise ValueError("Mindestens ein LLMProvider erforderlich.")

    prompt = build_prompt(
        concept_a_pref_label=concept_a_data["pref_label"],
        concept_a_definition=concept_a_data.get("definition", ""),
        concept_a_kqr=concept_a_data["kqr_id"],
        concept_b_pref_label=concept_b_data["pref_label"],
        concept_b_definition=concept_b_data.get("definition", ""),
        concept_b_kqr=concept_b_data["kqr_id"],
        few_shot_examples=few_shot_examples,
    )

    runs = [
        call_classification_model(prompt, provider=providers[i % len(providers)])
        for i in range(runs_per_pair)
    ]
    final_relation, confidence = majority_vote(runs)

    return ClassificationResult(
        pair=pair,
        runs=runs,
        final_relation=final_relation,
        mapping_confidence=confidence,
    )
