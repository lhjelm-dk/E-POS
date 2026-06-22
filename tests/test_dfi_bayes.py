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


def test_attribute_esl_optionB_r_interval_update():
    from logic.dfi_bayes import attribute_esl_optionB_r, ESLMasses

    def _masses():
        return {p: {"play": ESLMasses(0.55, 0.15), "cond": ESLMasses(0.60, 0.10)}
                for p in ("charge", "trap", "reservoir", "retention")}

    # R = 1 is a no-op (no evidence -> no change).
    out1 = attribute_esl_optionB_r(_masses(), 1.0)
    m = _masses()["charge"]["play"]; o = out1["charge"]["play"]
    assert abs(o.s_for - m.s_for) < 1e-9 and abs(o.s_against - m.s_against) < 1e-9

    # R > 1 raises Bel (S_for up) and Pl (S_against down); R < 1 reverses.
    up = attribute_esl_optionB_r(_masses(), 3.0)["charge"]["play"]
    dn = attribute_esl_optionB_r(_masses(), 0.3)["charge"]["play"]
    assert up.s_for > m.s_for and up.s_against < m.s_against
    assert dn.s_for < m.s_for and dn.s_against > m.s_against

    # Every slot stays a valid flag (S_for + S_against <= 1, both >= 0).
    for r in (0.2, 0.8, 1.0, 2.5, 9.0):
        out = attribute_esl_optionB_r(_masses(), r)
        for scopes in out.values():
            for o in scopes.values():
                assert o.s_for >= 0.0 and o.s_against >= 0.0
                assert o.s_for + o.s_against <= 1.0 + 1e-9


def test_simm_interval_posterior():
    from logic.dfi_simm import simm_interval_posterior, simm_bayes_posterior

    # R = 1 is a no-op: the interval is unchanged.
    b, p, w = simm_interval_posterior(0.30, 0.20, 1.0)
    assert abs(b - 0.30) < 1e-12 and abs(p - 0.80) < 1e-12 and abs(w - 0.50) < 1e-12

    # R > 1 raises both endpoints; R < 1 lowers both.
    bu, pu, _ = simm_interval_posterior(0.30, 0.20, 3.0)
    bd, pd, _ = simm_interval_posterior(0.30, 0.20, 0.3)
    assert bu > 0.30 and pu > 0.80
    assert bd < 0.30 and pd < 0.80

    # Interval stays valid, and the POINT posterior at every stance lies inside it.
    for r in (0.2, 0.8, 1.0, 2.5, 9.0):
        b, p, w = simm_interval_posterior(0.30, 0.20, r)
        assert 0.0 <= b <= p <= 1.0 and abs(w - (p - b)) < 1e-12
        for wt in (0.0, 0.25, 0.5, 0.75, 1.0):
            pt = simm_bayes_posterior(0.30 + wt * 0.50, r)   # S_for + w*White
            assert b - 1e-9 <= pt <= p + 1e-9

    # A zero-white prior (Bel == Pl) stays a point after the update.
    b, p, w = simm_interval_posterior(0.40, 0.60, 5.0)       # White = 0
    assert abs(b - p) < 1e-12 and abs(w) < 1e-12


def test_dhi_volume_weight_equals_r_over_r_plus_1():
    # The DHI Volume Weight V is, by definition, R/(R+1) = dhi_score_from_r(R) -
    # the 0-1 DHI strength. The Custom R tool sweep reuses dhi_score_from_r(R),
    # so the two methods report the same V for the same R. Lock the identity.
    from logic.dfi_simm import dhi_score_from_r
    for dhi in (-15.0, 0.0, 8.0, 19.0, 40.0):
        post = compute_dfi_posterior(_pillars(), dhi, _calib())
        r = post.r_dfi
        if r == float("inf"):
            continue
        assert post.dhi_volume_weight == pytest.approx(r / (r + 1.0), abs=1e-9)
        assert post.dhi_volume_weight == pytest.approx(dhi_score_from_r(r), abs=1e-9)
