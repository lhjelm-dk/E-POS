"""Tests for the Monigle-2025-derived improvements:
discernibility-aware R cap and the DHI->volumetrics integration helpers."""
from logic.dhi_characteristics import (
    cap_for_bucket, simm_bayes_posterior, DISCERNIBILITY_CAPS, R_FLOOR, R_HARD_CAP,
)
from logic.dfi_volumetrics import (
    column_height_weight, volumetrics_recommendation,
    HIGH_DHI_TRIAL_WEIGHT, POROSITY_FLOOR,
)


# ── Discernibility-aware cap ────────────────────────────────────────────────

def test_cap_widens_with_discernibility():
    lo_h, hi_h = cap_for_bucket("high")
    lo_m, hi_m = cap_for_bucket("moderate")
    lo_l, hi_l = cap_for_bucket("low")
    # higher discernibility -> wider band (lower floor, higher cap)
    assert hi_h > hi_m > hi_l
    assert lo_h < lo_m < lo_l
    # low bucket reduces to the Simm single-DFI bound
    assert (lo_l, hi_l) == (R_FLOOR, R_HARD_CAP)


def test_cap_disabled_is_unbounded():
    assert cap_for_bucket("high", enabled=False) == (0.0, float("inf"))


def test_high_discernibility_reproduces_monigle_prospect_b():
    # GCOS 46% with a strong expected-but-absent DHI at HIGH discernibility (d=1)
    # should be able to reach Monigle's ~8% iCOS, which the flat [1/3,3] cap cannot.
    floor, _ = cap_for_bucket("high")          # 1/10
    r_eff = floor ** 1.0                        # d = 1.0 at high discernibility
    post = simm_bayes_posterior(0.46, r_eff)
    assert 0.05 < post < 0.11                   # ~8%
    # the flat Simm floor cannot get there
    post_simm = simm_bayes_posterior(0.46, R_FLOOR)
    assert post_simm > 0.20


def test_discernibility_caps_keys():
    assert set(DISCERNIBILITY_CAPS) == {"high", "moderate", "low", "absent"}


# ── Column-height weighting (Monigle Fig. 8) ────────────────────────────────

def test_column_height_weight_curve():
    assert column_height_weight(0.7) == HIGH_DHI_TRIAL_WEIGHT      # strong DHI -> 95%
    assert abs(column_height_weight(0.3) - 0.6) < 1e-9             # 2 x score
    assert column_height_weight(0.0) == 0.0
    assert column_height_weight(1.0) == HIGH_DHI_TRIAL_WEIGHT      # clamped at 95%


def test_column_height_weight_clamps_out_of_range():
    assert column_height_weight(-1.0) == 0.0
    assert column_height_weight(5.0) == HIGH_DHI_TRIAL_WEIGHT


def test_volumetrics_recommendation_structure():
    rec = volumetrics_recommendation(0.3, discernibility="moderate",
                                     v_weight=0.55, fcr_present=True)
    assert abs(rec.w_ch - 0.6) < 1e-9
    assert rec.v_weight == 0.55
    assert any("NTG" in n for n in rec.consistency_notes)         # FCR note present
    assert any(f"{POROSITY_FLOOR*100:.0f}%" in n for n in rec.consistency_notes)
    assert "60%" in rec.headline                                  # ~60% of trials


def test_volumetrics_no_fcr_note_when_unknown():
    rec = volumetrics_recommendation(0.8, fcr_present=None)
    assert rec.w_ch == HIGH_DHI_TRIAL_WEIGHT
    # exactly two notes: discernibility gate + porosity (no FCR note)
    assert not any("FCR" in n for n in rec.consistency_notes)
