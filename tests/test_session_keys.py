"""Contract test for the session-key registry (``logic.session_keys.SK``).

``SK`` is the single source of truth for the operator / dependency session-key
namespace.  Many modules now call ``SK.*`` instead of embedding raw f-strings, so
the *exact byte format* of each generated key is a hard contract: if it drifts,
a writer (widget ``key=``) and a reader (getter) would silently address different
keys — the dead-key class of bug.

This test pins every generator to the literal string the app has always used, so
the format can never change by accident.  Update it deliberately (and migrate all
call-sites) if the namespace ever needs to change.
"""
from __future__ import annotations

from logic.session_keys import SK


def test_esl_operator_keys():
    assert SK.esl_mode("Charge") == "mode_cond_Charge"
    assert SK.esl_group_mode("Charge", "Migration pathway") == "mode_group_cond_Charge_Migration pathway"
    assert SK.esl_dependency("Closure") == "dep_cond_Closure"
    assert SK.esl_group_dependency("Closure", "Trap timing") == "dep_group_cond_Closure_Trap timing"


def test_classic_operator_keys():
    assert SK.classic_mode("Reservoir") == "classic_mode_cond_Reservoir"
    assert SK.classic_group_mode("Reservoir", "Effectiveness") == "classic_mode_group_cond_Reservoir_Effectiveness"


def test_group_key_composition_matches_legacy_prefix_form():
    """The legacy call-sites built ``f"mode_group_{group_key}"`` where
    ``group_key = f"cond_{pid}_{group}"``.  SK must reproduce that exact string."""
    pid, group = "Retention", "Seal effectiveness"
    legacy_group_key = f"cond_{pid}_{group}"
    assert SK.esl_group_mode(pid, group) == f"mode_group_{legacy_group_key}"
    assert SK.esl_group_dependency(pid, group) == f"dep_group_{legacy_group_key}"
    assert SK.classic_group_mode(pid, group) == f"classic_mode_group_{legacy_group_key}"


def test_flat_constants_unchanged():
    assert SK.COMPARISON_ESL_POS == "comparison_esl_pos"
    assert SK.COMPARISON_ESL_TOTAL_FOR == "comparison_esl_total_for"
    assert SK.COMPARISON_ESL_TOTAL_AGAINST == "comparison_esl_total_against"
    assert SK.COMPARISON_CLASSIC_POS == "comparison_classic_pos"
    assert SK.USE_POLICY_WEIGHT == "use_policy_weight"
    assert SK.UNCERTAINTY_WEIGHT_SLIDER == "uncertainty_weight_slider"
    assert SK.locked("ESL") == "locked_ESL"
