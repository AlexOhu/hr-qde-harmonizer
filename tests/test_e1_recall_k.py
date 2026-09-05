import numpy as np

import eval.E1_recall_k as e1


def test_recall_at_k_perfect_match_with_k1():
    gold_pairs = [("s1", "o1"), ("s2", "o2")]
    embeddings = {
        "s1": np.array([1.0, 0.0]),
        "o1": np.array([0.9, 0.1]),
        "s2": np.array([0.0, 1.0]),
        "o2": np.array([0.1, 0.9]),
    }

    recall, hits, total_evaluable = e1.recall_at_k(gold_pairs, embeddings, k=1)

    assert total_evaluable == 2
    assert hits == 2
    assert recall == 1.0


def test_recall_at_k_excludes_pairs_without_embeddings():
    gold_pairs = [("s1", "o1"), ("s2", "PLACEHOLDER_missing")]
    embeddings = {
        "s1": np.array([1.0, 0.0]),
        "o1": np.array([0.9, 0.1]),
        "s2": np.array([0.0, 1.0]),
    }

    recall, hits, total_evaluable = e1.recall_at_k(gold_pairs, embeddings, k=1)

    assert total_evaluable == 1
    assert hits == 1
    assert recall == 1.0


def test_recall_at_k_empty_embeddings_returns_zero_without_crash():
    gold_pairs = [("s1", "o1")]
    recall, hits, total_evaluable = e1.recall_at_k(gold_pairs, {}, k=5)

    assert (recall, hits, total_evaluable) == (0.0, 0, 0)
