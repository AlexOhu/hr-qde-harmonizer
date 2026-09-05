"""
Test für die Mehrheitsentscheid-Logik (app/pipeline/step3_classification/classify.py).

Dient als Startpunkt/Beispiel dafür, wie die übrigen Stubs getestet werden
sollten, sobald sie implementiert sind — insbesondere der Tie-Break-Fall
(kein eindeutiger Mehrheitsentscheid -> final_relation=None), der leicht
übersehen wird.
"""

from app.models.schemas import CandidatePair, ClassificationRun, RelationType
from app.pipeline.step3_classification.classify import majority_vote


def _run(relation: RelationType) -> ClassificationRun:
    return ClassificationRun(
        relation=relation,
        reasoning="Testlauf",
        model="claude-haiku-4-5-20251001",
        temperature=0.0,
    )


def test_majority_vote_clear_majority():
    runs = [_run(RelationType.EQUIVALENT), _run(RelationType.EQUIVALENT), _run(RelationType.RELATED)]
    relation, confidence = majority_vote(runs)
    assert relation == RelationType.EQUIVALENT
    assert confidence == 2 / 3


def test_majority_vote_no_majority_returns_none():
    runs = [
        _run(RelationType.EQUIVALENT),
        _run(RelationType.RELATED),
        _run(RelationType.A_SUBSUMES_B),
    ]
    relation, _ = majority_vote(runs)
    assert relation is None


def test_majority_vote_requires_at_least_one_run():
    try:
        majority_vote([])
        assert False, "sollte ValueError werfen"
    except ValueError:
        pass
