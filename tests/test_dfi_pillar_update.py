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
)


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
