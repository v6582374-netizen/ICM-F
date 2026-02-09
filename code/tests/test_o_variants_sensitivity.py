import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from o_variants_sensitivity import (
    weighted_quantile,
    compute_label_stability,
    compute_transform_jaccard,
    compute_rank_stability,
    kendall_tau,
)


def test_weighted_quantile_basic():
    values = [0.0, 1.0, 2.0, 3.0]
    weights = [1.0, 1.0, 1.0, 1.0]
    assert weighted_quantile(values, weights, 0.25) == 0.0
    assert weighted_quantile(values, weights, 0.50) == 1.0
    assert weighted_quantile(values, weights, 0.75) == 2.0


def test_label_stability_and_jaccard():
    v1 = {"C1": "KEEP", "C2": "TRANSFORM", "C3": "KEEP"}
    v2 = {"C1": "KEEP", "C2": "TRANSFORM", "C3": "PRUNE"}
    v3 = {"C1": "KEEP", "C2": "KEEP", "C3": "PRUNE"}
    stability = compute_label_stability([v1, v2, v3])
    assert stability["C1"]["mode_label"] == "KEEP"
    assert stability["C1"]["stability"] == 1.0
    jaccard_mat = compute_transform_jaccard({"v1": v1, "v2": v2, "v3": v3})
    assert jaccard_mat["v1__v2"] == 1.0
    assert jaccard_mat["v1__v3"] == 0.0


def test_kendall_tau_and_rank_stability():
    assert kendall_tau([1, 2, 3], [1, 2, 3]) == 1.0
    assert kendall_tau([1, 2, 3], [3, 2, 1]) == -1.0
    per_variant = {
        "v1": {"C1": 1.0, "C2": 2.0, "C3": 3.0},
        "v2": {"C1": 1.0, "C2": 2.0, "C3": 3.0},
    }
    tau_mat = compute_rank_stability(per_variant)
    assert tau_mat["v1__v2"] == 1.0
