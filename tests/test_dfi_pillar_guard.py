"""Tests for the DFI pillar guard (``logic.dfi_context.dfi_pillar_check``).

The DFI Bayesian core is hardcoded to exactly four pillars
(Charge/Closure/Reservoir/Retention).  The prior builders silently default a
*missing* pillar to 0.5/0.1 and silently drop any *extra* pillar from the
product — both corrupt the posterior with no visible error.  This guard is what
lets the DFI tab warn instead of failing silently, so its contract is pinned
here.
"""
from __future__ import annotations

from logic.dfi_context import DFI_REQUIRED_PILLARS, dfi_pillar_check


def test_exact_four_pillars_match():
    res = dfi_pillar_check(["Charge", "Closure", "Reservoir", "Retention"])
    assert res == {"matched": True, "missing": [], "extra": []}


def test_order_independent():
    res = dfi_pillar_check(["Retention", "Charge", "Reservoir", "Closure"])
    assert res["matched"] is True


def test_missing_pillar_flagged():
    res = dfi_pillar_check(["Charge", "Reservoir", "Retention"])
    assert res["matched"] is False
    assert res["missing"] == ["Closure"]
    assert res["extra"] == []


def test_extra_pillar_flagged():
    res = dfi_pillar_check(
        ["Charge", "Closure", "Reservoir", "Retention", "Biogenic"]
    )
    assert res["matched"] is False
    assert res["missing"] == []
    assert res["extra"] == ["Biogenic"]


def test_renamed_pillar_is_both_missing_and_extra():
    # A model that renamed "Closure" → "Trap" trips BOTH lists.
    res = dfi_pillar_check(["Charge", "Trap", "Reservoir", "Retention"])
    assert res["matched"] is False
    assert res["missing"] == ["Closure"]
    assert res["extra"] == ["Trap"]


def test_empty_model_lists_all_required_missing():
    res = dfi_pillar_check([])
    assert res["matched"] is False
    assert res["missing"] == list(DFI_REQUIRED_PILLARS)
    assert res["extra"] == []
