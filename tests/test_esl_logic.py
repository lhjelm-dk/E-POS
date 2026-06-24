"""Tests for the low-level ESL combination primitives (``logic.esl_logic``).

These are pure functions with strong, simple invariants — the cheapest and most
durable tests in the repo.  They lock the weakest-link / any-path / product
algebra that the whole ESL rollup is built on.
"""
from __future__ import annotations

import pytest

from logic.esl_logic import (
    apply_and_logic,
    apply_or_logic,
    apply_product_logic,
    calculate_uncertainty,
)


# ── apply_and_logic: weakest link → min(for), max(against) ───────────────────
def test_and_logic_weakest_link():
    nodes = [
        {"support_for": 0.9, "support_against": 0.05},
        {"support_for": 0.6, "support_against": 0.20},
    ]
    f, a = apply_and_logic(nodes)
    assert f == pytest.approx(0.6)   # min of the "for" masses
    assert a == pytest.approx(0.20)  # max of the "against" masses


def test_and_logic_accepts_tuples():
    f, a = apply_and_logic([(0.7, 0.1), (0.4, 0.3)])
    assert (f, a) == pytest.approx((0.4, 0.3))


# ── apply_or_logic: any path → max(for), min(against) ────────────────────────
def test_or_logic_any_path():
    nodes = [
        {"support_for": 0.9, "support_against": 0.05},
        {"support_for": 0.6, "support_against": 0.20},
    ]
    f, a = apply_or_logic(nodes)
    assert f == pytest.approx(0.9)
    assert a == pytest.approx(0.05)


# ── apply_product_logic: S=∏S_i, R=1−∏(1−R_i) ────────────────────────────────
def test_product_logic_formula():
    nodes = [
        {"support_for": 0.8, "support_against": 0.1},
        {"support_for": 0.5, "support_against": 0.2},
    ]
    f, a = apply_product_logic(nodes)
    assert f == pytest.approx(0.8 * 0.5)
    assert a == pytest.approx(1.0 - (1.0 - 0.1) * (1.0 - 0.2))


def test_product_logic_clamps_out_of_range():
    # Values outside [0,1] are clamped before multiplying.
    f, a = apply_product_logic([{"support_for": 1.5, "support_against": -0.3}])
    assert f == pytest.approx(1.0)
    assert a == pytest.approx(0.0)


# ── empty input is the (0,0) identity for all three ──────────────────────────
@pytest.mark.parametrize("fn", [apply_and_logic, apply_or_logic, apply_product_logic])
def test_empty_returns_zero_zero(fn):
    assert fn([]) == (0.0, 0.0)


def test_invalid_node_raises():
    with pytest.raises(ValueError):
        apply_and_logic([object()])


# ── calculate_uncertainty: white = 1 − for − against, conflict if sum > 1 ─────
def test_uncertainty_normal():
    u, conflict = calculate_uncertainty(0.6, 0.1)
    assert u == pytest.approx(0.3)
    assert conflict is False


def test_uncertainty_conflict():
    u, conflict = calculate_uncertainty(0.7, 0.6)
    assert u == pytest.approx(0.0)   # clamped, never negative
    assert conflict is True


def test_incompleteness_equals_pl_minus_bel():
    # The Incompleteness index shown on the Analysis tab is the headline white
    # band, which is exactly Pl - Bel (Bel = S_for, Pl = 1 - S_against).
    s_for, s_against = 0.55, 0.20
    white, conflict = calculate_uncertainty(s_for, s_against)
    bel, pl = s_for, 1.0 - s_against
    assert conflict is False
    assert white == pytest.approx(pl - bel)   # 0.25


def test_esl_trajectory_above_exact_lower_bound():
    # Property: the ESL stance trajectory (headline x = Policy P of the combined
    # masses, linear in w; UI = two-weakest-pillar adequacy) never drops below the
    # exact lower bound UI = 2x - 1. (The upper "all equal" curve 2*x**(1/N) - 1 is
    # only a balanced reference, NOT a bound: a vetoing pillar can exceed it.)
    import numpy as np
    rng = np.random.default_rng(7)
    N = 4
    for _ in range(50000):
        bel = rng.uniform(0.0, 1.0, N)
        pl = bel + rng.uniform(0.0, 1.0, N) * (1.0 - bel)
        w = rng.uniform(0.0, 1.0)
        pg = bel + w * (pl - bel)
        s = np.sort(pg)
        ui = s[0] + s[1] - 1.0
        x = float(np.prod(bel) + w * (np.prod(pl) - np.prod(bel)))
        assert ui >= 2.0 * x - 1.0 - 1e-9   # exact lower bound
