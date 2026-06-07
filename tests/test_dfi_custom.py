"""Tests for the custom DFI-strength tool (logic.dfi_custom)."""
import math

from logic.dfi_custom import (
    gaussian_from_p1_p99, normal_pdf, custom_r, dhi_score_from_r,
    CustomCase, DEFAULT_HC, DEFAULT_NOHC, R_HARD_CAP, R_FLOOR,
    grouped_r, SUCCESS_KEYS, FAILURE_KEYS, CASE_DEFAULTS,
)


def _identical_case_set():
    # All success cases identical, all failure cases identical, equal weights —
    # the "linked" two-state configuration.
    cases = {k: DEFAULT_HC for k in SUCCESS_KEYS}
    cases.update({k: DEFAULT_NOHC for k in FAILURE_KEYS})
    weights = {k: 1.0 for k in cases}
    return cases, weights


def _default_case_set():
    cases = {k: CustomCase(k, k, *CASE_DEFAULTS[k]) for k in SUCCESS_KEYS + FAILURE_KEYS}
    weights = {k: 1.0 for k in cases}
    return cases, weights


def test_grouped_r_reduces_to_two_state_when_linked():
    # All success cases share the HC curve, all failure cases share No-HC, equal
    # weights -> grouped_r must equal the simple custom_r at every point.
    cases, weights = _identical_case_set()
    for x in (-80, -30, 0, 30, 80):
        assert abs(grouped_r(x, cases, weights) - custom_r(x, DEFAULT_HC, DEFAULT_NOHC)) < 1e-9


def test_grouped_r_weights_shift_result():
    cases, weights = _default_case_set()
    # Make one failure case much "stronger-looking" (mirrors a success curve) and
    # weight it heavily -> the failure denominator rises, so R should drop.
    cases["non_reservoir"] = CustomCase("non_reservoir", "nr", -50.0, 100.0)
    weights["non_reservoir"] = 50.0
    base = custom_r(40.0, DEFAULT_HC, DEFAULT_NOHC)
    assert grouped_r(40.0, cases, weights) < base


def test_case_weight_defaults_match_spec():
    from logic.dfi_custom import CASE_DEFAULTS, CASE_WEIGHT_DEFAULTS
    assert CASE_DEFAULTS["oil"] == (-50.0, 100.0)
    assert CASE_DEFAULTS["gas"] == (-40.0, 80.0)
    assert CASE_DEFAULTS["oil_gas"] == (-40.0, 90.0)
    assert CASE_DEFAULTS["water"] == (-100.0, 50.0)
    assert CASE_DEFAULTS["lsg"] == (-80.0, 80.0)
    assert CASE_DEFAULTS["non_reservoir"] == (-70.0, 50.0)
    assert CASE_WEIGHT_DEFAULTS == {
        "oil": 0.33, "gas": 0.33, "oil_gas": 0.33,
        "water": 0.80, "lsg": 0.20, "non_reservoir": 0.00,
    }


def test_simm_rule_of_thumb_bands():
    from logic.dfi_custom import simm_rule_of_thumb
    assert simm_rule_of_thumb(20.0)[0] == "Decisive uplift"
    assert simm_rule_of_thumb(4.0)[0] == "Strong uplift"
    assert simm_rule_of_thumb(2.0)[0] == "Moderate uplift"
    assert simm_rule_of_thumb(1.0)[0] == "Negligible"
    assert simm_rule_of_thumb(0.5)[0] == "Moderate downgrade"
    assert simm_rule_of_thumb(0.2)[0] == "Strong downgrade"
    assert simm_rule_of_thumb(0.02)[0] == "Decisive downgrade"
    # symmetry in log-odds: R and 1/R land in mirror bands
    assert simm_rule_of_thumb(3.0)[0] == "Strong uplift"
    assert simm_rule_of_thumb(1 / 3.0)[0] == "Strong downgrade"
    assert simm_rule_of_thumb(0.34)[0] == "Moderate downgrade"


def test_custom_config_from_state_linked_matches_custom_r():
    from logic.dfi_custom import custom_config_from_state, CustomCase
    state = {
        "dfi_custom_multicase": False, "dfi_custom_slider": 30.0,
        "dfi_custom_hc_p1": -40.0, "dfi_custom_hc_p99": 90.0,
        "dfi_custom_no_p1": -110.0, "dfi_custom_no_p99": 40.0,
    }
    cfg = custom_config_from_state(state)
    hc = CustomCase("hc", "HC", -40.0, 90.0)
    no = CustomCase("no", "No", -110.0, 40.0)
    assert cfg.multicase is False and cfg.slider == 30.0
    assert abs(cfg.r - custom_r(30.0, hc, no)) < 1e-9


def test_custom_config_from_state_multicase_matches_grouped_r():
    from logic.dfi_custom import (
        custom_config_from_state, CustomCase, grouped_r,
        SUCCESS_KEYS, FAILURE_KEYS, CASE_DEFAULTS, CASE_WEIGHT_DEFAULTS,
    )
    state = {"dfi_custom_multicase": True, "dfi_custom_slider": 15.0}
    cfg = custom_config_from_state(state)   # all per-case keys fall back to defaults
    cases = {k: CustomCase(k, k, *CASE_DEFAULTS[k]) for k in SUCCESS_KEYS + FAILURE_KEYS}
    weights = {k: CASE_WEIGHT_DEFAULTS[k] for k in SUCCESS_KEYS + FAILURE_KEYS}
    assert cfg.multicase is True
    assert abs(cfg.r_at(15.0) - grouped_r(15.0, cases, weights)) < 1e-9


def test_custom_config_defaults_on_empty_state():
    from logic.dfi_custom import custom_config_from_state, DEFAULT_SLIDER
    cfg = custom_config_from_state({})
    assert cfg.multicase is False and cfg.slider == DEFAULT_SLIDER
    assert R_FLOOR <= cfg.r <= R_HARD_CAP


def test_grouped_r_zero_weights_fall_back_to_equal():
    cases, weights = _default_case_set()
    for k in weights:
        weights[k] = 0.0
    # Degenerate all-zero weights must not crash; equal-weight fallback applies.
    r = grouped_r(0.0, cases, weights)
    assert R_FLOOR <= r <= R_HARD_CAP


def test_gaussian_from_p1_p99_matches_worked_example():
    # User's worked example: P1=-50, P99=100 -> mean 25, sd 32.2393449
    mean, sd = gaussian_from_p1_p99(-50.0, 100.0)
    assert mean == 25.0
    assert abs(sd - 32.2393449) < 1e-4


def test_p1_p99_are_actual_percentiles():
    # The PDF integrated... simpler: the spec says p1/p99 are 1st/99th percentiles,
    # so the normal CDF at p1 ~ 0.01 and at p99 ~ 0.99.
    mean, sd = gaussian_from_p1_p99(-50.0, 100.0)
    cdf = lambda x: 0.5 * (1 + math.erf((x - mean) / (sd * math.sqrt(2))))
    assert abs(cdf(-50.0) - 0.01) < 1e-3
    assert abs(cdf(100.0) - 0.99) < 1e-3


def test_zero_width_spec_is_finite():
    mean, sd = gaussian_from_p1_p99(10.0, 10.0)
    assert mean == 10.0
    assert sd > 0.0  # floored, not zero


def test_custom_r_equal_curves_is_one():
    same = CustomCase("a", "a", -50.0, 50.0)
    assert abs(custom_r(0.0, same, same) - 1.0) < 1e-9


def test_custom_r_capped_and_floored():
    # Far in the HC tail -> R hits the cap; far in the No-HC tail -> floor.
    assert custom_r(100.0, DEFAULT_HC, DEFAULT_NOHC) <= R_HARD_CAP + 1e-9
    assert custom_r(-100.0, DEFAULT_HC, DEFAULT_NOHC) >= R_FLOOR - 1e-9


def test_custom_r_monotonic_increasing_with_strength():
    xs = [-80, -40, 0, 40, 80]
    rs = [custom_r(x, DEFAULT_HC, DEFAULT_NOHC) for x in xs]
    assert all(b >= a for a, b in zip(rs, rs[1:]))


def test_dhi_score_from_r():
    # Canonical score is in [0, 1] (UI scales ×100). Re-exported from logic.dfi_simm.
    assert dhi_score_from_r(1.0) == 0.5
    assert abs(dhi_score_from_r(3.0) - 0.75) < 1e-9


def test_normal_pdf_nonpositive_sd():
    assert normal_pdf(0.0, 0.0, 0.0) == 0.0
