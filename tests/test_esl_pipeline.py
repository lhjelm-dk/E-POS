"""Tests for ``logic.esl_pipeline`` — the operator dispatch and full rollup.

The single most valuable guard here is :func:`test_combine_with_mode_*`: a silent
regression in one operator branch (e.g. ESL-ALL accidentally behaving like ANY)
would corrupt every POS in the app while still "looking" plausible.  These tests
pin each branch to its defining formula.
"""
from __future__ import annotations

import pytest

from logic.esl_pipeline import (
    combine_with_mode,
    combine_classic_pos,
    combine_ipt,
    group_by_label,
    compute_esl_rollup,
)


def _nodes():
    return [
        {"support_for": 0.9, "support_against": 0.05},
        {"support_for": 0.6, "support_against": 0.20},
    ]


# ── combine_with_mode: one assertion per operator branch ─────────────────────
def test_combine_esl_all_min_min():
    f, a = combine_with_mode(_nodes(), "ESL-ALL (min/min)")
    assert (f, a) == pytest.approx((0.6, 0.05))


def test_combine_esl_any_max_max():
    f, a = combine_with_mode(_nodes(), "ESL-ANY (max/max)")
    assert (f, a) == pytest.approx((0.9, 0.20))


def test_combine_product():
    f, a = combine_with_mode(_nodes(), "Product (Π)")
    assert f == pytest.approx(0.9 * 0.6)
    assert a == pytest.approx(1.0 - (1.0 - 0.05) * (1.0 - 0.20))


def test_combine_mean():
    f, a = combine_with_mode(_nodes(), "Mean")
    assert f == pytest.approx((0.9 + 0.6) / 2)
    assert a == pytest.approx((0.05 + 0.20) / 2)


def test_combine_empty_is_zero():
    assert combine_with_mode([], "ESL-ALL (min/min)") == (0.0, 0.0)


# ── IPT dependency knob: ρ=0 → independent OR, ρ=1 → max ─────────────────────
def test_combine_ipt_dependency_extremes():
    nodes = [
        {"support_for": 0.5, "support_against": 0.0, "suff_for": 1.0, "suff_against": 1.0},
        {"support_for": 0.5, "support_against": 0.0, "suff_for": 1.0, "suff_against": 1.0},
    ]
    f_ind, _ = combine_ipt(nodes, dependency=0.0)
    f_dep, _ = combine_ipt(nodes, dependency=1.0)
    assert f_ind == pytest.approx(1.0 - 0.5 * 0.5)  # 0.75 (noisy-OR)
    assert f_dep == pytest.approx(0.5)              # fully correlated → max


# ── group_by_label ───────────────────────────────────────────────────────────
def test_group_by_label():
    elems = [
        {"label": "A", "support_for": 0.1},
        {"label": "B", "support_for": 0.2},
        {"label": "A", "support_for": 0.3},
    ]
    grouped = group_by_label(elems)
    assert set(grouped) == {"A", "B"}
    assert len(grouped["A"]) == 2 and len(grouped["B"]) == 1


# ── combine_classic_pos: probability-space operators ─────────────────────────
@pytest.mark.parametrize(
    "mode,expected",
    [
        ("Min (weakest link)", 0.2),
        ("Max", 0.8),
        ("Mean", 0.5),
        ("Product (Π)", 0.2 * 0.5 * 0.8),
    ],
)
def test_combine_classic_pos(mode, expected):
    assert combine_classic_pos([0.2, 0.5, 0.8], mode) == pytest.approx(expected)


def test_combine_classic_pos_empty():
    assert combine_classic_pos([], "Min (weakest link)") == 0.0


# ── compute_esl_rollup: play × conditional product tree ──────────────────────
def test_compute_esl_rollup_single_pillar():
    play = {"Charge": {"support_for": 0.8, "support_against": 0.1}}
    conditional = {"Charge": [{"label": "g", "support_for": 0.9, "support_against": 0.05}]}
    get_mode = lambda k: "ESL-ALL (min/min)"
    get_dep = lambda k: 0.0

    r = compute_esl_rollup(play, conditional, get_mode, get_dep)

    assert r.pillar_for["Charge"] == pytest.approx(0.8)
    assert r.conditional_results["Charge"]["for"] == pytest.approx(0.9)
    # total_for = play_for × cond_for ; total_against = 1−∏(1−r)
    assert r.total_for == pytest.approx(0.8 * 0.9)
    assert r.total_against == pytest.approx(1.0 - (1.0 - 0.1) * (1.0 - 0.05))
