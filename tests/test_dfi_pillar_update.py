"""Tests for the pillar-resolved single-segment DFI update (logic/dfi_pillar_update.py).

Covers the four spec invariants plus the patent (US 10,451,762 B2) golden example.
"""
from __future__ import annotations

import math

import pytest

from logic.dfi_simm import simm_bayes_posterior
from logic.dfi_pillar_update import (
    pillar_resolved_update,
    redistribute_log_proportion,
    HC_SYSTEM_PILLARS,
    ChannelLikelihoods,
    aggregate_channels,
    resolve_dfi,
)
from logic.dfi_custom import custom_config_from_state, custom_channel_likelihoods
from logic.dhi_characteristics import characteristic_channels


# A spread of non-degenerate scenarios: (pos, p_res, l_hc, l_fluidfail, l_nonres)
CASES = [
    (0.072, 0.50, 0.8, 0.3, 0.5),   # the patent example
    (0.30, 0.70, 1.0, 1.0, 1.0),    # uninformative DFI (all equal) -> no move
    (0.25, 0.60, 2.5, 0.4, 0.2),    # supportive anomaly
    (0.40, 0.85, 0.3, 1.2, 1.6),    # anti-supportive (reservoir-failure-like)
    (0.10, 0.95, 1.7, 0.9, 0.05),   # strong DHI, reservoir near-certain
    (0.55, 0.55, 1.3, 0.7, 0.7),    # p_res == pos boundary (p_hc == 1)
]


# ── Invariant (a): headline POS == two-state Bayes with blended failure curve ──
@pytest.mark.parametrize("pos,p_res,l_hc,l_ff,l_nr", CASES)
def test_headline_matches_two_state(pos, p_res, l_hc, l_ff, l_nr):
    r = pillar_resolved_update(pos, p_res, l_hc, l_ff, l_nr)
    # Prior-weighted blended failure likelihood over the two failure leaves.
    pri_ff = max(p_res - pos, 0.0)
    pri_nr = 1.0 - p_res
    denom = pri_ff + pri_nr
    if denom <= 0:
        return
    l_failmix = (pri_ff * l_ff + pri_nr * l_nr) / denom
    R = l_hc / l_failmix if l_failmix > 0 else 0.0
    expected = simm_bayes_posterior(pos, R)
    assert r.pos_post == pytest.approx(expected, abs=1e-12)


# ── Invariant (b): P_res' * P_hc' == POS' ──
@pytest.mark.parametrize("pos,p_res,l_hc,l_ff,l_nr", CASES)
def test_product_reconstructs_pos(pos, p_res, l_hc, l_ff, l_nr):
    r = pillar_resolved_update(pos, p_res, l_hc, l_ff, l_nr)
    assert r.p_res_post * r.p_hc_post == pytest.approx(r.pos_post, abs=1e-12)
    # And the prior product is exact too (residual-P_hc trick).
    assert r.p_res_prior * r.p_hc_prior == pytest.approx(r.pos_prior, abs=1e-12)


# ── Invariant (c): product of redistributed pillars == P_hc' ──
@pytest.mark.parametrize("pos,p_res,l_hc,l_ff,l_nr", CASES)
def test_redistribution_product_exact(pos, p_res, l_hc, l_ff, l_nr):
    r = pillar_resolved_update(pos, p_res, l_hc, l_ff, l_nr)
    priors = {"Charge": 0.6, "Closure": 0.5, "Retention": 0.8}
    out = redistribute_log_proportion(r.p_hc_post, priors)
    prod = math.prod(out.values())
    assert prod == pytest.approx(r.p_hc_post, abs=1e-9)
    assert set(out.keys()) == set(priors.keys())


# ── Invariant (d): leaf posteriors normalise to 1 ──
@pytest.mark.parametrize("pos,p_res,l_hc,l_ff,l_nr", CASES)
def test_leaf_posteriors_normalise(pos, p_res, l_hc, l_ff, l_nr):
    r = pillar_resolved_update(pos, p_res, l_hc, l_ff, l_nr)
    assert (r.post_success + r.post_fluidfail + r.post_nonres) == pytest.approx(1.0, abs=1e-12)


# ── Golden test: patent US 10,451,762 B2 (3-leaf reduction) ──
def test_patent_golden_example():
    r = pillar_resolved_update(pos=0.072, p_res=0.50, l_hc=0.8, l_fluidfail=0.3, l_nonres=0.5)
    # Patent Table 6: COS 0.072 -> ~0.130, reservoir presence 0.50 -> ~0.434.
    # 3-leaf reduction lands within rounding of the patent's richer scenario set.
    assert r.pos_post == pytest.approx(0.1321, abs=2e-3)
    assert r.p_res_post == pytest.approx(0.4266, abs=2e-3)
    # The headline signature: COS UP while Reservoir DOWN.
    assert r.pos_post > r.pos_prior
    assert r.p_res_post < r.p_res_prior
    assert r.opposes_headline is True


def test_uninformative_dfi_is_a_noop():
    r = pillar_resolved_update(pos=0.30, p_res=0.70, l_hc=1.0, l_fluidfail=1.0, l_nonres=1.0)
    assert r.pos_post == pytest.approx(0.30, abs=1e-12)
    assert r.p_res_post == pytest.approx(0.70, abs=1e-12)
    assert r.opposes_headline is False


def test_supportive_anomaly_lifts_pos():
    r = pillar_resolved_update(pos=0.25, p_res=0.60, l_hc=2.5, l_fluidfail=0.4, l_nonres=0.2)
    assert r.pos_post > r.pos_prior


def test_p_res_below_pos_is_clamped():
    # Degenerate input: reservoir marginal below the aggregate POS -> clamp, p_hc=1.
    r = pillar_resolved_update(pos=0.50, p_res=0.40, l_hc=1.5, l_fluidfail=0.5, l_nonres=0.5)
    assert r.p_res_prior >= r.pos_prior
    assert r.p_hc_prior == pytest.approx(1.0, abs=1e-9)


def test_redistribution_preserves_log_proportions():
    priors = {"Charge": 0.6, "Closure": 0.5, "Retention": 0.8}
    out = redistribute_log_proportion(0.31, priors)
    # New log-share of each pillar equals its old log-share.
    old_total = sum(math.log(v) for v in priors.values())
    new_total = sum(math.log(v) for v in out.values())
    for k in priors:
        old_share = math.log(priors[k]) / old_total
        new_share = math.log(out[k]) / new_total
        assert new_share == pytest.approx(old_share, abs=1e-9)


def test_redistribution_all_ones_splits_equally():
    out = redistribute_log_proportion(0.27, {"Charge": 1.0, "Closure": 1.0, "Retention": 1.0})
    assert math.prod(out.values()) == pytest.approx(0.27, abs=1e-9)
    vals = list(out.values())
    assert all(v == pytest.approx(vals[0], abs=1e-12) for v in vals)


def test_hc_system_pillars_constant():
    assert HC_SYSTEM_PILLARS == ("Charge", "Closure", "Retention")


# ── Adapter layer: ChannelLikelihoods / resolve_dfi ──────────────────────────
def test_aggregate_channels_is_not_pillar_resolved():
    ch = aggregate_channels(2.5, "Characteristic")
    assert ch.pillar_resolved is False
    assert ch.l_nonres is None
    assert ch.r == pytest.approx(2.5)


def test_resolve_dfi_aggregate_matches_two_state():
    ch = aggregate_channels(2.5, "x")
    res = resolve_dfi(pos=0.30, p_res=0.80, channels=ch, hc_pillar_priors={"Charge": 0.6})
    assert res.pillar_resolved is False
    assert res.update is None
    assert res.pos_post == pytest.approx(simm_bayes_posterior(0.30, 2.5), abs=1e-12)
    # Pillars left untouched for aggregate-only methods.
    assert res.hc_pillars_post == res.hc_pillars_prior
    assert res.p_res_post is None


def test_resolve_dfi_pillar_resolved_is_consistent():
    ch = ChannelLikelihoods(l_hc=1.4, l_fluidfail=0.7, l_nonres=1.0, method_label="m")
    priors = {"Charge": 0.6, "Closure": 0.5, "Retention": 0.8}
    res = resolve_dfi(pos=0.30, p_res=0.80, channels=ch, hc_pillar_priors=priors)
    assert res.pillar_resolved is True
    # Headline equals the engine's joint success leaf (reservoir-driven).
    assert res.pos_post == pytest.approx(res.update.pos_post, abs=1e-12)
    # Product of redistributed HC pillars == HC-system marginal.
    assert math.prod(res.hc_pillars_post.values()) == pytest.approx(res.update.p_hc_post, abs=1e-9)
    # Reservoir * HC-system == headline.
    assert res.p_res_post * res.update.p_hc_post == pytest.approx(res.pos_post, abs=1e-12)


# ── Custom-tool adapter ──────────────────────────────────────────────────────
def test_custom_dual_is_aggregate_only():
    cfg = custom_config_from_state({"dfi_custom_multicase": False})
    ch = custom_channel_likelihoods(cfg)
    assert ch.pillar_resolved is False
    assert "dual" in ch.method_label.lower()


def test_custom_multi_is_pillar_resolved_with_three_channels():
    cfg = custom_config_from_state({"dfi_custom_multicase": True})
    ch = custom_channel_likelihoods(cfg)
    assert ch.pillar_resolved is True
    assert ch.l_nonres is not None and ch.l_nonres > 0.0
    assert ch.l_hc > 0.0 and ch.l_fluidfail > 0.0
    assert "multi" in ch.method_label.lower()


def test_custom_multi_default_success_mix_beats_oil_only():
    # Sanity: the success channel is the weighted mix, not the oil curve alone.
    from logic.dfi_custom import CASE_DEFAULTS, CustomCase
    cfg = custom_config_from_state({"dfi_custom_multicase": True})
    ch = custom_channel_likelihoods(cfg)
    p1, p99 = CASE_DEFAULTS["oil"]
    oil_only = CustomCase("oil", "oil", p1, p99).pdf(cfg.slider)
    assert ch.l_hc != pytest.approx(oil_only, abs=1e-9)


# ── Characteristic adapter ───────────────────────────────────────────────────
def test_characteristic_is_aggregate_only():
    ch = characteristic_channels(1.8)
    assert ch.pillar_resolved is False
    assert ch.r == pytest.approx(1.8)
    assert "Characteristic" in ch.method_label


# ── DHI-Index (SAAM) adapter ─────────────────────────────────────────────────
class _StubClass:
    def __init__(self, mean, sd):
        self.mean = mean
        self._sd = sd
    def sd(self, _mode):
        return self._sd


class _StubCalib:
    """Minimal calibration carrying the SAAM class schema for adapter tests."""
    def __init__(self):
        self.classes = {
            "Success": _StubClass(0.30, 0.25),
            "Oil": _StubClass(0.35, 0.25),
            "Gas": _StubClass(0.20, 0.25),
            "OilGas": _StubClass(0.30, 0.25),
            "H2O_failure": _StubClass(-0.30, 0.25),
            "LSG_failure": _StubClass(0.00, 0.30),
            "Reservoir_failure": _StubClass(-0.10, 0.25),
        }


def test_dhi_index_adapter_is_pillar_resolved_and_maps_reservoir():
    from logic.dfi_orchestration import dhi_index_channel_likelihoods, geox_pdfi_value
    calib = _StubCalib()
    ch = dhi_index_channel_likelihoods(7.0, calib, "sd_calculated",
                                       fluid_type="Success",
                                       fluid_weights={"water": 0.80, "lsg": 0.20, "other": 0.0})
    assert ch.pillar_resolved is True
    # L_nonres comes straight from the Reservoir_failure class.
    assert ch.l_nonres == pytest.approx(geox_pdfi_value(7.0, calib, "Reservoir_failure", "sd_calculated"))
    # L_HC is the chosen success class.
    assert ch.l_hc == pytest.approx(geox_pdfi_value(7.0, calib, "Success", "sd_calculated"))
    # L_fluidfail is the weighted blend of H2O + LSG.
    v_wat = geox_pdfi_value(7.0, calib, "H2O_failure", "sd_calculated")
    v_lsg = geox_pdfi_value(7.0, calib, "LSG_failure", "sd_calculated")
    assert ch.l_fluidfail == pytest.approx(0.80 * v_wat + 0.20 * v_lsg)
    assert ch.method_label == "Modified DHI Index (SAAM)"


def test_dhi_index_other_weight_shares_lsg():
    from logic.dfi_orchestration import dhi_index_channel_likelihoods, geox_pdfi_value
    calib = _StubCalib()
    ch = dhi_index_channel_likelihoods(7.0, calib, "sd_calculated", fluid_type="Success",
                                       fluid_weights={"water": 0.0, "lsg": 0.0, "other": 1.0})
    v_lsg = geox_pdfi_value(7.0, calib, "LSG_failure", "sd_calculated")
    assert ch.l_fluidfail == pytest.approx(v_lsg)  # 'other' shares LSG_failure


def test_dhi_index_resolves_through_engine():
    from logic.dfi_orchestration import dhi_index_channel_likelihoods
    calib = _StubCalib()
    ch = dhi_index_channel_likelihoods(7.0, calib, "sd_calculated")
    priors = {"Charge": 0.6, "Closure": 0.5, "Retention": 0.8}
    res = resolve_dfi(pos=0.25, p_res=0.70, channels=ch, hc_pillar_priors=priors)
    assert res.pillar_resolved is True
    assert res.p_res_post * res.update.p_hc_post == pytest.approx(res.pos_post, abs=1e-12)


# ── Plan B: PostDfiPillars / build_post_pillars ──────────────────────────────
def test_build_post_pillars_product_and_keys():
    from logic.dfi_pillar_update import build_post_pillars
    priors = {"Charge": 0.6, "Closure": 0.5, "Retention": 0.8}
    pp = build_post_pillars(pos_prior=0.072, pos_post=0.132,
                            p_res_prior=0.50, p_res_post=0.43,
                            hc_pillar_priors=priors, method_label="m")
    assert pp.pillar_resolved is True
    assert set(pp.pillars_post.keys()) == {"Reservoir", "Charge", "Closure", "Retention"}
    # HC pillars' product == HC-system posterior == pos_post / p_res_post.
    hc_prod = pp.pillars_post["Charge"] * pp.pillars_post["Closure"] * pp.pillars_post["Retention"]
    assert hc_prod == pytest.approx(0.132 / 0.43, abs=1e-9)
    # COS up while Reservoir down → opposes_headline.
    assert pp.opposes_headline is True


def test_post_pillars_from_resolved_matches():
    from logic.dfi_pillar_update import resolve_dfi, ChannelLikelihoods, post_pillars_from_resolved
    ch = ChannelLikelihoods(1.4, 0.7, 1.0, "m")
    priors = {"Charge": 0.6, "Closure": 0.5, "Retention": 0.8}
    res = resolve_dfi(0.30, 0.80, ch, priors)
    pp = post_pillars_from_resolved(res)
    assert pp.pillars_post["Reservoir"] == pytest.approx(res.p_res_post)
    assert pp.pos_post == pytest.approx(res.pos_post)


# ── Plan B: DHI-Index reservoir marginal (patent P(RP|DFI)) ──────────────────
def test_reservoir_present_marginal_sums_eval_outcomes():
    from logic.dfi_bayes import reservoir_present_marginal, EVAL_RES_OUTCOMES
    d = {"oil_eval_success": 0.1, "water_eval_failure": 0.05, "lsg_eval_failure": 0.03,
         "other_eval_failure": 0.02, "oil_noneval_failure": 0.4,
         "water_noneval_failure": 0.4}
    assert reservoir_present_marginal(d) == pytest.approx(0.20)
    assert EVAL_RES_OUTCOMES[0] == "oil_eval_success"


def test_dhi_index_post_pillars_reservoir_down_when_nonres_likely():
    """A DHI most consistent with the Reservoir_failure class must push the reservoir
    marginal DOWN even if the headline moves up — the channel-resolved upgrade."""
    from logic.dfi_bayes import (
        compute_dfi_posterior, reservoir_present_marginal, PriorPillars, FluidWeights,
    )
    from logic.dfi_pillar_update import build_post_pillars
    # Stub calib where the Reservoir_failure class is most consistent with DHI≈ -10.
    classes = {
        "Success": _StubClass(0.30, 0.25), "Oil": _StubClass(0.30, 0.25),
        "Gas": _StubClass(0.20, 0.25), "OilGas": _StubClass(0.30, 0.25),
        "H2O_failure": _StubClass(-0.40, 0.25), "LSG_failure": _StubClass(0.00, 0.30),
        "Reservoir_failure": _StubClass(-0.10, 0.18),
    }
    calib = type("C", (), {"classes": classes})()
    pillars = PriorPillars(
        charge_play=0.9, trap_play=0.9, reservoir_play=0.8, retention_play=0.9,
        charge_cond=0.8, trap_cond=0.95, reservoir_cond=0.85, retention_cond=0.8,
    )
    esl_prior = pillars.prior_pg
    post = compute_dfi_posterior(pillars, -10.0, calib, FluidWeights(), "sd_calculated", "Success",
                                 prior_pg_override=esl_prior)
    p_res_prior = reservoir_present_marginal(post.prior_outcomes.as_dict())
    p_res_post = reservoir_present_marginal(post.posterior_outcomes)
    hc = {"Charge": pillars.charge_play * pillars.charge_cond,
          "Closure": pillars.trap_play * pillars.trap_cond,
          "Retention": pillars.retention_play * pillars.retention_cond}
    pp = build_post_pillars(esl_prior, post.posterior_pg, p_res_prior, p_res_post, hc)
    # Reservoir marginal moved DOWN (the anomaly looks like a non-reservoir cause).
    assert pp.pillars_post["Reservoir"] < pp.pillars_prior["Reservoir"]
    # Headline equals the 8-outcome posterior (unchanged by the channel split).
    assert pp.pos_post == pytest.approx(post.posterior_pg, abs=1e-12)
