"""Tests for the DFI Bayesian core (``logic.dfi_bayes``).

This is the mathematically load-bearing module: the 8-outcome decomposition, the
posterior update, the ``prior_pg_override`` re-anchoring, and the per-pillar
attribution all carry invariants that were previously only verified by hand.
These tests encode them as regressions.

A *synthetic* Calibration is built in-test so the suite never depends on the
local override ``data/dhi_calibration.json`` and stays deterministic.
"""
from __future__ import annotations

import pytest

from logic.dfi_calibration import Calibration, ClassStats, ALL_CLASSES
from logic.dfi_bayes import (
    PriorPillars,
    FluidWeights,
    decompose_prior,
    compute_dfi_posterior,
    attribute_classic,
    rescale_outcomes_to_success,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────
def _calib() -> Calibration:
    """A plausible synthetic calibration covering every required class."""
    means = {
        "Success": 0.25, "Oil": 0.25, "OilGas": 0.22, "Gas": 0.20,
        "H2O_failure": -0.05, "LSG_failure": 0.0, "Reservoir_failure": -0.10,
    }
    classes = {
        name: ClassStats(mean=means[name], sd_calculated=0.12, sd_upper=0.15, n=30)
        for name in ALL_CLASSES
    }
    return Calibration(version="test", source="synthetic", description="",
                       classes=classes, is_placeholder=True)


def _pillars() -> PriorPillars:
    # No pillar at exactly 1.0 → attribution product invariant should hold.
    return PriorPillars(
        charge_play=0.9, trap_play=0.85, reservoir_play=0.8, retention_play=0.9,
        charge_cond=0.95, trap_cond=0.9, reservoir_cond=0.85, retention_cond=0.95,
    )


# ── FluidWeights.normalised ──────────────────────────────────────────────────
def test_fluid_weights_normalise_sums_to_one():
    n = FluidWeights(water=0.8, lsg=0.8, other=0.0).normalised()
    assert n.water + n.lsg + n.other == pytest.approx(1.0)
    assert n.water == pytest.approx(0.5)


def test_fluid_weights_normalise_degenerate():
    n = FluidWeights(0.0, 0.0, 0.0).normalised()
    assert (n.water, n.lsg, n.other) == (1.0, 0.0, 0.0)


# ── decompose_prior: the 8 outcomes sum to 1 ─────────────────────────────────
def test_decompose_prior_sums_to_one():
    outcomes = decompose_prior(_pillars(), FluidWeights(0.8, 0.2, 0.0))
    assert outcomes.total() == pytest.approx(1.0)
    assert outcomes.oil_eval_success == pytest.approx(_pillars().prior_pg)


# ── compute_dfi_posterior: basic well-formedness ─────────────────────────────
def test_posterior_in_unit_interval_and_outcomes_sum_to_one():
    post = compute_dfi_posterior(_pillars(), dhi_index=19.0, calib=_calib())
    assert 0.0 <= post.posterior_pg <= 1.0
    assert sum(post.posterior_outcomes.values()) == pytest.approx(1.0)


# ── prior_pg_override re-anchoring ───────────────────────────────────────────
def test_override_moves_prior_but_not_likelihood_ratios():
    """R_DFI and DHI Volume Weight are likelihood ratios → invariant to the
    prior anchor.  Only the prior→posterior anchor should move."""
    base = compute_dfi_posterior(_pillars(), 19.0, _calib())
    over = compute_dfi_posterior(_pillars(), 19.0, _calib(), prior_pg_override=0.42)

    assert over.r_dfi == pytest.approx(base.r_dfi, rel=1e-9)
    assert over.dhi_volume_weight == pytest.approx(base.dhi_volume_weight, rel=1e-9)
    # The override anchors the success prior to 0.42 exactly.
    assert over.prior_outcomes.oil_eval_success == pytest.approx(0.42)
    # init_pg_unscaled records the native ∏-pillars prior for audit.
    assert over.init_pg_unscaled == pytest.approx(_pillars().prior_pg)


def test_override_outcomes_still_sum_to_one():
    over = compute_dfi_posterior(_pillars(), 19.0, _calib(), prior_pg_override=0.42)
    assert over.prior_outcomes.total() == pytest.approx(1.0)
    assert sum(over.posterior_outcomes.values()) == pytest.approx(1.0)


# ── rescale_outcomes_to_success: preserves failure-mode ratios ───────────────
def test_rescale_preserves_failure_ratios_and_sums_to_one():
    prior = decompose_prior(_pillars(), FluidWeights(0.7, 0.2, 0.1)).as_dict()
    target = 0.30
    out = rescale_outcomes_to_success(prior, target)

    assert out["oil_eval_success"] == pytest.approx(target)
    assert sum(out.values()) == pytest.approx(1.0)
    # Relative proportions among the seven failure outcomes are unchanged.
    fk = [k for k in prior if k != "oil_eval_success"]
    ref = out[fk[0]] / prior[fk[0]]
    for k in fk:
        if prior[k] > 0:
            assert out[k] / prior[k] == pytest.approx(ref)


# ── attribute_classic: ∏(8 pillars) == posterior_pg ──────────────────────────
def test_attribute_classic_product_invariant():
    post = compute_dfi_posterior(_pillars(), 19.0, _calib())
    attr = attribute_classic(_pillars(), post)
    product = (
        attr.charge_play * attr.trap_play * attr.reservoir_play * attr.retention_play
        * attr.charge_cond * attr.trap_cond * attr.reservoir_cond * attr.retention_cond
    )
    assert product == pytest.approx(post.posterior_pg, rel=1e-6)
