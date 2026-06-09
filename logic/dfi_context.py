"""Shared DFI prior/calibration primitives.

These were previously private (``_underscore``) helpers living inside the
``components.tabs.tab_dfi`` UI module, yet four *other* modules
(``tab_dashboard``, ``tab_analysis``, ``prospect_hub``, ``methods.classic_pos``)
reached in and imported them.  UI importing another UI tab's internals is a
fragile abstraction-boundary error, so the shared computation now lives here in
``logic/`` where every consumer can import it cleanly.

The functions read Streamlit ``session_state`` for stance/mode getters and
calibration overrides, so this module imports Streamlit.  ``ctx`` is any object
exposing ``play``, ``conditional`` / ``conditional_results`` and
``uncertainty_weight`` (the real analysis ctx, or a light ``SimpleNamespace``
shim).
"""
from __future__ import annotations

import streamlit as st

from logic.session_keys import SK

# ── DFI pillar coupling ──────────────────────────────────────────────────────
# The DFI Bayesian core (logic.dfi_bayes.PriorPillars + the 8-outcome
# decomposition) is hardcoded to exactly these four pillars.  The prior builders
# below iterate this tuple and pull each pillar out of ``ctx.play`` /
# ``ctx.conditional`` by name; any pillar a model is *missing* silently defaults
# to 0.5/0.1, and any *extra* pillar is silently dropped from the product.  Both
# corrupt the posterior without any visible error, so the DFI tab must guard on
# this and warn the analyst.
DFI_REQUIRED_PILLARS: tuple[str, ...] = ("Charge", "Closure", "Reservoir", "Retention")


def dfi_pillar_check(pillar_ids) -> dict:
    """Compare a model's pillar IDs against the four pillars the DFI core requires.

    Args:
        pillar_ids: iterable of the active model's pillar IDs (e.g. ``ctx.play``).

    Returns:
        ``{"matched": bool, "missing": list[str], "extra": list[str]}`` where
        ``missing`` are required pillars absent from the model (their chance
        silently defaults to 0.5/0.1) and ``extra`` are model pillars the DFI
        product ignores entirely.  ``matched`` is True only when both are empty.
    """
    ids = list(pillar_ids)
    present = set(ids)
    required = set(DFI_REQUIRED_PILLARS)
    missing = [p for p in DFI_REQUIRED_PILLARS if p not in present]
    extra = [p for p in ids if p not in required]
    return {"matched": not missing and not extra, "missing": missing, "extra": extra}


def esl_prior_pillars_from_ctx(ctx):
    """Build ``PriorPillars`` from ctx using ESL per-pillar Pgs at current stance."""
    from logic.pos_policy import policy_pos
    from logic.dfi_bayes import PriorPillars
    w = ctx.uncertainty_weight
    pp: dict[str, float] = {}
    for pid in ("Charge", "Closure", "Reservoir", "Retention"):
        play_el = ctx.play.get(pid, {})
        cond_r = ctx.conditional_results.get(pid, {"for": 0.5, "against": 0.1})
        pp[f"{pid.lower()}_play"] = policy_pos(
            float(play_el.get("support_for", 0.5)),
            float(play_el.get("support_against", 0.1)), w,
        )
        pp[f"{pid.lower()}_cond"] = policy_pos(
            float(cond_r["for"]), float(cond_r["against"]), w,
        )
    return PriorPillars(
        charge_play=pp["charge_play"],   trap_play=pp["closure_play"],
        reservoir_play=pp["reservoir_play"], retention_play=pp["retention_play"],
        charge_cond=pp["charge_cond"],   trap_cond=pp["closure_cond"],
        reservoir_cond=pp["reservoir_cond"], retention_cond=pp["retention_cond"],
    )


def esl_prior_pillars_from_ctx_at_w(ctx, w: float):
    """ESL per-pillar Pgs at an arbitrary stance w (for trajectory sweeps)."""
    from logic.pos_policy import policy_pos
    from logic.dfi_bayes import PriorPillars
    pp: dict[str, float] = {}
    for pid in ("Charge", "Closure", "Reservoir", "Retention"):
        play_el = ctx.play.get(pid, {})
        cond_r = ctx.conditional_results.get(pid, {"for": 0.5, "against": 0.1})
        pp[f"{pid.lower()}_play"] = policy_pos(
            float(play_el.get("support_for", 0.5)),
            float(play_el.get("support_against", 0.1)), w,
        )
        pp[f"{pid.lower()}_cond"] = policy_pos(
            float(cond_r["for"]), float(cond_r["against"]), w,
        )
    return PriorPillars(
        charge_play=pp["charge_play"],     trap_play=pp["closure_play"],
        reservoir_play=pp["reservoir_play"], retention_play=pp["retention_play"],
        charge_cond=pp["charge_cond"],     trap_cond=pp["closure_cond"],
        reservoir_cond=pp["reservoir_cond"], retention_cond=pp["retention_cond"],
    )


def esl_rollup_prior_at_w(ctx, w: float) -> float:
    """Headline **P(G, ESL)** = stance-weighted ESL *mass-rollup* at stance ``w``.

    This is the number reported everywhere else in the app (Dashboard / Analysis /
    Summary) — masses are combined up the play×conditional tree and the stance is
    applied **once** at the top. It is *not* the ∏-pillars "Init Pg" used by the
    8-outcome decomposition (which applies the stance per pillar then multiplies, and
    sits systematically lower). The DFI update is anchored to this rollup so the
    posterior is the update of the geological number the analyst actually books.

    Uses ``ctx.total_for`` / ``ctx.total_against`` when present; otherwise recomputes
    the ESL mass tree from ``ctx.play`` / ``ctx.conditional`` via the shared pipeline.
    """
    from logic.pos_policy import policy_pos
    tf = getattr(ctx, "total_for", None)
    ta = getattr(ctx, "total_against", None)
    if tf is None or ta is None:
        from logic.esl_pipeline import (
            compute_esl_rollup, make_session_mode_dep_getters,
        )
        gm, gd = make_session_mode_dep_getters(st.session_state)
        roll = compute_esl_rollup(getattr(ctx, "play", {}),
                                  getattr(ctx, "conditional", {}), gm, gd)
        tf, ta = roll.total_for, roll.total_against
    return policy_pos(tf, ta, w)


def resolve_dfi_custom(ctx):
    """Pillar-resolved DFI result for the **Custom R tool** at current stance.

    Returns a ``ResolvedDfi`` (pillar-resolved for multi-case, aggregate-only for
    dual-case) or ``None`` when the active method is not the Custom tool. The
    Reservoir prior is the Reservoir-pillar marginal; the headline prior is the
    ESL mass-rollup ``P(G, ESL)``; the HC-system pillars are Charge / Closure /
    Retention marginals (used for the log-proportion split). DHI-Index keeps its
    own richer 8-outcome attribution and is intentionally not routed here.
    """
    if st.session_state.get("dfi_source") != "custom":
        return None
    from logic.dfi_custom import custom_config_from_state, custom_channel_likelihoods
    from logic.dfi_pillar_update import resolve_dfi
    w = ctx.uncertainty_weight
    pos = esl_rollup_prior_at_w(ctx, w)
    pp = esl_prior_pillars_from_ctx_at_w(ctx, w)
    p_res = pp.reservoir_play * pp.reservoir_cond
    hc_priors = {
        "Charge":    pp.charge_play * pp.charge_cond,
        "Closure":   pp.trap_play * pp.trap_cond,        # PriorPillars uses trap_* for Closure
        "Retention": pp.retention_play * pp.retention_cond,
    }
    cfg = custom_config_from_state(st.session_state)
    ch = custom_channel_likelihoods(cfg)
    return resolve_dfi(pos, p_res, ch, hc_priors)


def classic_prior_pillars_from_ctx(ctx, w: float | None = None):
    """Build ``PriorPillars`` from ctx using Classic per-pillar Pgs at given stance.

    Mirrors the math in methods/classic_pos.py: Policy P per sub-element,
    combine via Classic operator at group then pillar level.
    """
    from logic.pos_policy import policy_pos
    from logic.dfi_bayes import PriorPillars
    from logic.esl_pipeline import (
        group_by_label, combine_classic_pos, make_session_classic_mode_getter,
    )
    if w is None:
        w = ctx.uncertainty_weight
    get_classic_mode = make_session_classic_mode_getter(st.session_state)
    pp: dict[str, float] = {}
    for pid in ("Charge", "Closure", "Reservoir", "Retention"):
        play_el = ctx.play.get(pid, {})
        pp[f"{pid.lower()}_play"] = policy_pos(
            float(play_el.get("support_for", 0.5)),
            float(play_el.get("support_against", 0.1)), w,
        )
        elems = ctx.conditional.get(pid, [])
        if not elems:
            pp[f"{pid.lower()}_cond"] = 1.0
            continue
        elem_p = {
            id(e): policy_pos(
                float(e["support_for"]), float(e["support_against"]), w,
            )
            for e in elems
        }
        grouped = group_by_label(elems)
        grp_pts: list[float] = []
        for grp_label, grp_elems in grouped.items():
            grp_mode = get_classic_mode(SK.classic_group_mode(pid, grp_label))
            grp_pts.append(combine_classic_pos(
                [elem_p[id(e)] for e in grp_elems], grp_mode,
            ))
        pil_mode = get_classic_mode(SK.classic_mode(pid))
        pp[f"{pid.lower()}_cond"] = combine_classic_pos(grp_pts, pil_mode)
    return PriorPillars(
        charge_play=pp["charge_play"],     trap_play=pp["closure_play"],
        reservoir_play=pp["reservoir_play"], retention_play=pp["retention_play"],
        charge_cond=pp["charge_cond"],     trap_cond=pp["closure_cond"],
        reservoir_cond=pp["reservoir_cond"], retention_cond=pp["retention_cond"],
    )


def get_effective_calibration():
    """Load base calibration and apply any in-UI overrides from session state.

    Overrides are stored as ``{class_name: {mean, sd_calculated, sd_upper, n}}``.
    The base is reloaded each call so a file change is picked up; the JSON
    files are small (< 2 KB) so this is cheap.
    """
    from logic.dfi_calibration import load_calibration
    base = load_calibration()
    override = st.session_state.get("dfi_calibration_override") or {}
    for class_name, edits in override.items():
        if class_name in base.classes:
            cls = base.classes[class_name]
            if "mean" in edits:          cls.mean          = float(edits["mean"])
            if "sd_calculated" in edits: cls.sd_calculated = float(edits["sd_calculated"])
            if "sd_upper" in edits:      cls.sd_upper      = float(edits["sd_upper"])
            if "n" in edits:             cls.n             = int(edits["n"])
    return base


def pillar_pairs_from_priorpillars(p):
    """List of (display_name, attribute_key, value) for the 8 pillar slots."""
    return [
        ("Charge / Play",     "charge_play",    p.charge_play),
        ("Charge / Cond",     "charge_cond",    p.charge_cond),
        ("Closure / Play",    "trap_play",      p.trap_play),
        ("Closure / Cond",    "trap_cond",      p.trap_cond),
        ("Reservoir / Play",  "reservoir_play", p.reservoir_play),
        ("Reservoir / Cond",  "reservoir_cond", p.reservoir_cond),
        ("Retention / Play",  "retention_play", p.retention_play),
        ("Retention / Cond",  "retention_cond", p.retention_cond),
    ]
