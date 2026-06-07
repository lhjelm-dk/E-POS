"""Tests for the characteristic-scoring core (logic.dhi_characteristics).

Locks the central Monigle-2025 pathway: per-attribute LRs, base-rate-relative vs
scale-middle anchoring, the naive-independence product, the discernibility squash,
the discernibility-aware cap, and the DHI score.
"""
import math

import pytest

from logic.dhi_characteristics import (
    load_characteristic_stats, compute_r_char, compute_r_char_inferred,
    inferred_lr_at, inferred_success_rate_at, apply_discernibility,
    simm_bayes_posterior, dhi_score_from_r, cap_for_bucket,
    correlation_discount_exponent,
    score_class_logr_moments, score_class_gaussians, score_class_convolution_raw,
    DISCERNIBILITY_CAPS, CHARACTERISTIC_DEFAULT_SELECTIONS,
    R_FLOOR, R_HARD_CAP,
)

MK = "5_current"


@pytest.fixture(scope="module")
def stats():
    return load_characteristic_stats()


# ── Loading / structure ─────────────────────────────────────────────────────

def test_load_has_five_current_attributes(stats):
    active = stats.attributes_for_mode(MK)
    assert set(active) == {
        "anomaly_strength", "lateral_amplitude_contrast", "fit_to_structure",
        "amplitude_terminations", "fluid_contact_reflection",
    }


def test_discernibility_buckets(stats):
    assert {b: round(v.d, 2) for b, v in stats.buckets.items()} == {
        "high": 1.0, "moderate": 0.6, "low": 0.3, "absent": 0.0,
    }


# ── Per-attribute LR: base-rate vs scale-middle anchoring ───────────────────

def test_fair_fcr_base_rate_relative_is_strong(stats):
    # Documented example: Fair fluid-contact-reflection (82% vs 56% base) → LR ~3.25.
    r = compute_r_char(stats, {"fluid_contact_reflection": "Fair"}, mode_key=MK,
                       hard_cap=float("inf"), floor=0.0,
                       relative_to_middle=False)["r_char"]
    assert abs(r - 3.25) < 0.05


def test_fair_fcr_scale_middle_is_neutral(stats):
    # The legacy anchoring forces the *middle* category (Fair) to LR = 1.
    r = compute_r_char(stats, {"fluid_contact_reflection": "Fair"}, mode_key=MK,
                       hard_cap=float("inf"), floor=0.0,
                       relative_to_middle=True)["r_char"]
    assert abs(r - 1.0) < 1e-9


def test_all_middle_scale_relative_is_one(stats):
    # An all-middle selection under scale-middle anchoring yields R = 1 by construction.
    mids = {k: a.categories(MK)[len(a.categories(MK)) // 2]
            for k, a in stats.attributes_for_mode(MK).items()}
    r = compute_r_char(stats, mids, mode_key=MK, hard_cap=float("inf"), floor=0.0,
                       relative_to_middle=True)["r_char"]
    assert abs(r - 1.0) < 1e-9


def test_missing_selection_contributes_lr_one(stats):
    # No selections → product over LR=1 → R=1.
    r = compute_r_char(stats, {}, mode_key=MK, hard_cap=float("inf"), floor=0.0)["r_char"]
    assert abs(r - 1.0) < 1e-9


def test_correlation_discount_exponent_limits():
    # rho=0 -> independent (f=1); k=1 -> f=1; rho->1 -> f -> 1/k
    assert correlation_discount_exponent(5, 0.0) == 1.0
    assert correlation_discount_exponent(1, 0.7) == 1.0
    assert abs(correlation_discount_exponent(5, 0.5) - 1.0 / (1 + 4 * 0.5)) < 1e-12
    assert abs(correlation_discount_exponent(4, 0.99) - 1.0 / (1 + 3 * 0.99)) < 1e-12


def test_corr_rho_discounts_evidence_toward_one(stats):
    # A strong all-positive selection: rho>0 must pull R_disc strictly toward 1
    # (below the naive product) but stay on the same side (>1).
    sel = {"fluid_contact_reflection": "Excellent", "anomaly_strength": "Very strong",
           "lateral_amplitude_contrast": "High"}
    base = compute_r_char(stats, sel, mode_key=MK, hard_cap=float("inf"), floor=0.0,
                          corr_rho=0.0)
    disc = compute_r_char(stats, sel, mode_key=MK, hard_cap=float("inf"), floor=0.0,
                          corr_rho=0.5)
    assert disc["corr_rho"] == 0.5
    assert base["raw_r"] > 1.0
    # discounted is raw_r ** f, with f<1 -> closer to 1 but still > 1
    assert 1.0 < disc["r_char"] < base["r_char"]
    k = base["n_attributes_in_r"]
    f = correlation_discount_exponent(k, 0.5)
    assert abs(disc["r_char"] - base["raw_r"] ** f) < 1e-9


def test_corr_rho_default_is_naive_product(stats):
    # Default corr_rho=0 leaves the result identical to the naive product.
    sel = {"anomaly_strength": "Very strong"}
    a = compute_r_char(stats, sel, mode_key=MK, hard_cap=float("inf"), floor=0.0)
    assert abs(a["discounted_r"] - a["raw_r"]) < 1e-12
    assert a["corr_exponent"] == 1.0


def test_score_class_gaussians_success_above_failure(stats):
    # The success population must sit at a higher composite log-LR than failure,
    # with positive spreads — both for raw and inferred LRs.
    for inf in (False, True):
        g = score_class_gaussians(stats, mode_key=MK, inferred=inf)
        mu_s, sd_s = g["succ"]
        mu_f, sd_f = g["fail"]
        assert mu_s > mu_f                 # successes look more success-like
        assert sd_s > 0 and sd_f > 0
        assert g["k"] == 5


def test_score_class_gaussians_corr_shrinks_spread(stats):
    # The independence discount f<1 scales mu and sd toward 0 (R=1 / score 50%).
    g0 = score_class_gaussians(stats, mode_key=MK, corr_rho=0.0)
    g1 = score_class_gaussians(stats, mode_key=MK, corr_rho=0.5)
    f = correlation_discount_exponent(g0["k"], 0.5)
    assert abs(g1["corr_exponent"] - f) < 1e-12
    assert abs(g1["succ"][0] - g0["succ"][0] * f) < 1e-9     # mu scales by f
    assert abs(g1["succ"][1] - g0["succ"][1] * f) < 1e-9     # sd scales by f


def test_score_class_logr_moments_variance_nonneg(stats):
    m = score_class_logr_moments(stats, mode_key=MK)
    assert m["succ"][1] >= 0 and m["fail"][1] >= 0


def test_score_class_convolution_raw(stats):
    c = score_class_convolution_raw(stats, mode_key=MK, nbins=40)
    assert c is not None
    assert c["n_cells"] == 5 ** 5            # 5 attributes × 5 categories
    bw = 1.0 / 40
    # binned densities integrate to ~1 (it's a proper distribution per class)
    assert abs(sum(v * bw for v in c["succ"]) - 1.0) < 1e-6
    assert abs(sum(v * bw for v in c["fail"]) - 1.0) < 1e-6
    # success population's mean score sits above the failure population's
    mean_s = sum(x * v * bw for x, v in zip(c["centers"], c["succ"]))
    mean_f = sum(x * v * bw for x, v in zip(c["centers"], c["fail"]))
    assert mean_s > mean_f


def test_score_class_convolution_guard_returns_none(stats):
    # An impossibly small cell budget forces the combinatorial guard to bail out.
    assert score_class_convolution_raw(stats, mode_key=MK, max_cells=10) is None


def test_product_is_sum_in_logs(stats):
    # R_char is the product of the per-attribute LRs.
    sel = {"fluid_contact_reflection": "Excellent", "anomaly_strength": "Very strong"}
    res = compute_r_char(stats, sel, mode_key=MK, hard_cap=float("inf"), floor=0.0,
                         relative_to_middle=False)
    prod = 1.0
    for k in sel:
        prod *= res["per_attribute_lr"][k]
    assert abs(res["r_char"] - prod) < 1e-6


# ── Discernibility squash ───────────────────────────────────────────────────

def test_apply_discernibility_is_power(stats):
    high = stats.buckets["high"]
    moderate = stats.buckets["moderate"]
    absent = stats.buckets["absent"]
    assert abs(apply_discernibility(4.0, high) - 4.0) < 1e-9          # d=1 unchanged
    assert abs(apply_discernibility(4.0, moderate) - 4.0 ** 0.6) < 1e-9
    assert abs(apply_discernibility(4.0, absent) - 1.0) < 1e-9        # d=0 → 1


# ── Discernibility-aware cap ────────────────────────────────────────────────

def test_cap_widens_with_discernibility():
    assert cap_for_bucket("high") == (1 / 10.0, 10.0)
    assert cap_for_bucket("low") == (R_FLOOR, R_HARD_CAP)
    assert cap_for_bucket("high", enabled=False) == (0.0, float("inf"))
    assert set(DISCERNIBILITY_CAPS) == {"high", "moderate", "low", "absent"}


def test_cap_clamps_r(stats):
    sel = {"fluid_contact_reflection": "Excellent", "anomaly_strength": "Very strong",
           "lateral_amplitude_contrast": "Very high"}
    lo, hi = cap_for_bucket("low")          # Simm [1/3, 3]
    capped = compute_r_char(stats, sel, mode_key=MK, hard_cap=hi, floor=lo,
                            relative_to_middle=False)
    assert capped["r_char"] <= hi + 1e-9
    assert capped["was_capped"] is True


# ── Inferred (isotonic) pathway ─────────────────────────────────────────────

def test_inferred_lr_monotonic_in_position(stats):
    attr = stats.attributes["fit_to_structure"]
    xs = [0.0, 0.25, 0.5, 0.75, 1.0]
    lrs = [inferred_lr_at(attr, MK, x, relative_to_middle=False) for x in xs]
    assert all(b >= a - 1e-9 for a, b in zip(lrs, lrs[1:]))   # non-decreasing


def test_inferred_success_rate_monotonic(stats):
    attr = stats.attributes["fluid_contact_reflection"]
    srs = [inferred_success_rate_at(attr, MK, x) for x in (0.0, 0.5, 1.0)]
    assert srs[0] <= srs[1] <= srs[2]                         # isotonic removes the Fair>Good dip


def test_compute_r_char_inferred_runs(stats):
    positions = {k: 0.8 for k in stats.attributes_for_mode(MK)}
    res = compute_r_char_inferred(stats, positions, mode_key=MK,
                                  hard_cap=float("inf"), floor=0.0,
                                  relative_to_middle=False)
    assert res["r_char"] > 1.0                                # strong positions → uplift


# ── DHI score + posterior plumbing ──────────────────────────────────────────

def test_dhi_score_from_r(stats):
    assert dhi_score_from_r(1.0) == 0.5
    assert abs(dhi_score_from_r(3.0) - 0.75) < 1e-9
    assert dhi_score_from_r(0.0) == 0.0


def test_simm_posterior_matches_bayes(stats):
    assert abs(simm_bayes_posterior(0.30, 3.0) - (3 * 0.3) / (3 * 0.3 + 0.7)) < 1e-9


def test_default_selections_are_valid_categories(stats):
    active = stats.attributes_for_mode(MK)
    for key, cat in CHARACTERISTIC_DEFAULT_SELECTIONS.items():
        assert key in active
        assert cat in active[key].categories(MK)
