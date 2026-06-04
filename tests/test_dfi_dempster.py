"""Tests for the prototype Dempster-Shafer DFI fusion (option B)."""
import math

from logic.dfi_dempster import (
    BeliefMass, esl_mass, dfi_mass, dempster_combine, fuse_dfi_into_esl,
)


def _sums_to_one(m: BeliefMass) -> bool:
    return abs(m.g + m.r + m.w - 1.0) < 1e-9


def test_esl_mass_basic():
    m = esl_mass(0.30, 0.10)
    assert (m.g, m.r) == (0.30, 0.10)
    assert abs(m.w - 0.60) < 1e-9
    assert _sums_to_one(m)
    assert abs(m.bel - 0.30) < 1e-9
    assert abs(m.pl - 0.90) < 1e-9      # bel + white


def test_dfi_mass_discernibility_is_unknown_mass():
    # d=0 -> fully vacuous; d=1 -> all committed by the score
    assert dfi_mass(0.7, 0.0) == BeliefMass(0.0, 0.0, 1.0)
    m = dfi_mass(0.7, 1.0)
    assert abs(m.g - 0.7) < 1e-9 and abs(m.r - 0.3) < 1e-9 and m.w == 0.0
    # partial discernibility splits the d mass by the score, rest is white
    m2 = dfi_mass(0.5, 0.4)
    assert abs(m2.w - 0.6) < 1e-9 and abs(m2.g - 0.2) < 1e-9 and abs(m2.r - 0.2) < 1e-9


def test_combine_with_vacuous_is_noop():
    esl = esl_mass(0.3, 0.1)
    vac = BeliefMass(0.0, 0.0, 1.0)          # a fully non-discernible DFI
    post, K = dempster_combine(esl, vac)
    assert K == 0.0
    assert abs(post.g - esl.g) < 1e-9 and abs(post.r - esl.r) < 1e-9 and abs(post.w - esl.w) < 1e-9


def test_white_shrinks_with_discernibility():
    # higher discernibility -> less posterior white (combination sharpens belief)
    _, _, p_lo, _ = fuse_dfi_into_esl(0.3, 0.1, 0.7, 0.1)
    _, _, p_hi, _ = fuse_dfi_into_esl(0.3, 0.1, 0.7, 0.9)
    esl = esl_mass(0.3, 0.1)
    assert p_lo.w <= esl.w + 1e-9            # never adds white
    assert p_hi.w < p_lo.w                   # more discernible -> sharper
    assert p_hi.bel > p_lo.bel               # positive DFI lifts belief more when discernible


def test_conflict_K_high_when_sources_disagree():
    # confident ESL-for-success vs confident DFI-for-failure -> high conflict
    _, _, post, K = fuse_dfi_into_esl(0.85, 0.05, 0.05, 0.95)
    assert K > 0.5
    assert _sums_to_one(post)


def test_posterior_always_normalised():
    for tf, ta, s, d in [(0.3, 0.1, 0.7, 0.6), (0.6, 0.2, 0.2, 0.9), (0.1, 0.7, 0.9, 0.5)]:
        _, _, post, _ = fuse_dfi_into_esl(tf, ta, s, d)
        assert _sums_to_one(post)
        assert 0.0 <= post.point(0.5) <= 1.0
