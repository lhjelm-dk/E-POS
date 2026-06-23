"""DFI Update (Bayesian) tab — three sub-pages.

  • DFI Setup            — DHI index, fluid-failure weights, calibration view & edit
  • DFI Results          — DFI-modified per-pillar values + posterior trajectory
  • Final Prospect POS   — one-page summary suitable for reporting / sign-off

The tab is gated by a Dashboard toggle ``st.session_state['dfi_enabled']``.
When OFF, each sub-page shows an info placeholder so users see the capability
exists but can't accidentally use stale/empty inputs.

Session-state keys read/written by this tab:

  dfi_enabled            : bool   — master toggle (set on Dashboard)
  dfi_index              : float  — DHI index (-23..+50), default 8
  dfi_fluid_water        : float  — P(fluid=water | failure),    default 0.50
  dfi_fluid_lsg          : float  — P(fluid=LSG   | failure),    default 0.20
  dfi_fluid_other        : float  — P(fluid=other | failure),    default 0.30
  dfi_fluid_type         : str    — Success | Oil | OilGas | Gas, default Success
  dfi_sd_mode            : str    — upper | calculated,          default upper
  dfi_esl_attribution    : str    — A | B,                       default B
  dfi_calibration_override : dict — in-UI edits to calibration, defaults to none
"""
from __future__ import annotations

import streamlit as st


# ─────────────────────────────────────────────────────────────────────────────
# Default values applied when the DFI toggle flips ON for the first time
# ─────────────────────────────────────────────────────────────────────────────

# Defaults live once in logic.dfi_inputs (single source of truth for the DFI
# session contract); aliased here for the widget initialisation below.
from logic.dfi_inputs import (
    DEFAULT_DHI         as _DEFAULT_DHI_INDEX,
    DEFAULT_FLUID_WATER as _DEFAULT_FLUID_WATER,
    DEFAULT_FLUID_LSG   as _DEFAULT_FLUID_LSG,
    DEFAULT_FLUID_OTHER as _DEFAULT_FLUID_OTHER,
    DEFAULT_FLUID_TYPE  as _DEFAULT_FLUID_TYPE,
    DEFAULT_SD_MODE     as _DEFAULT_SD_MODE,
    DEFAULT_ESL_ATTR    as _DEFAULT_ESL_ATTRIBUTION,
)


def initialise_dfi_session_defaults() -> None:
    """First-time toggle-on: populate the DFI session keys with defaults.

    Idempotent — subsequent calls are no-ops.  Called from the Dashboard when
    the user flips ``dfi_enabled`` ON.
    """
    defaults = {
        # Seed the evidence-source so post-DFI views (CAM overlay, attribution
        # panels) work immediately on toggle-on, before DFI Setup is visited.
        # "custom" matches the Setup radio's first/default option.
        "dfi_source":              "custom",
        "dfi_index":               _DEFAULT_DHI_INDEX,
        "dfi_fluid_water":         _DEFAULT_FLUID_WATER,
        "dfi_fluid_lsg":           _DEFAULT_FLUID_LSG,
        "dfi_fluid_other":         _DEFAULT_FLUID_OTHER,
        "dfi_fluid_type":          _DEFAULT_FLUID_TYPE,
        "dfi_sd_mode":             _DEFAULT_SD_MODE,
        "dfi_esl_attribution":     _DEFAULT_ESL_ATTRIBUTION,
        "dfi_calibration_override": None,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


# ─────────────────────────────────────────────────────────────────────────────
# Top-level tab render — delegates to one of three sub-page renderers
# ─────────────────────────────────────────────────────────────────────────────

def _render_dfi_tab(ctx) -> None:
    """Render the DFI Update (Bayesian) top-level tab."""
    st.markdown(
        "<div style='background:linear-gradient(135deg,#1e3a8a,#312e81);color:#fff;"
        "padding:14px 18px;border-radius:8px;margin-bottom:10px;'>"
        "<b style='font-size:1.1rem;'>Bayesian DFI Update</b><br>"
        "<span style='font-size:0.85rem;opacity:0.9;'>"
        "Update the geological prior probability with a quantitative seismic "
        "observation (Conceptual DHI Index), the update can raise <b>or</b> lower the prior. "
        "Posterior values: <b>P(G | DFI, ESL)</b> and <b>P(G | DFI, Classic)</b>."
        "</span></div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Single-segment prospect only (*segment* is a GeoX term). E-POS does not model "
        "multi-segment prospects or inter-segment DFI correlation — the single-segment "
        "Bayes used here is standard prior art; no patent claim is practised. "
        "▸ details: **Theory & Guide → The maths → Pillar-resolved DFI**."
    )

    _policy_warn = st.session_state.get("_dfi_policy_warning")
    if _policy_warn:
        st.warning("⚠️ " + _policy_warn)

    dfi_on = bool(st.session_state.get("dfi_enabled", False))

    if dfi_on:
        _render_dfi_pillar_warning(ctx)

    sub_setup, sub_results = st.tabs([
        "DFI Setup",
        "DFI Results",
    ])

    with sub_setup:
        if not dfi_on:
            _render_disabled_placeholder("DFI Setup")
        else:
            _render_dfi_setup(ctx)
    with sub_results:
        if not dfi_on:
            _render_disabled_placeholder("DFI Results")
        else:
            _render_dfi_results(ctx)

    if dfi_on:
        st.caption(
            "➡️ The reportable **Final Prospect POS** is now its own top-level tab "
            "(it shows the geological POS with the DFI update layered in)."
        )


def _render_disabled_placeholder(sub_page_name: str) -> None:
    """Friendly placeholder shown when the DFI toggle is OFF."""
    st.info(
        f"**{sub_page_name}** is currently disabled.  \n\n"
        "Enable the **DFI-capable prospect?** toggle on the **Dashboard** (next to the "
        "Stance slider) to activate the DFI Bayesian update for this prospect.  \n\n"
        "When enabled, default values will be applied:  \n"
        "• Conceptual DHI Index = **8**  \n"
        "• Fluid failure probabilities: water **50%**, LSG **20%**, other **30%**  \n"
        "• HC fluid type = **Success** (aggregate)  \n"
        "• ESL per-pillar attribution = **B (Bel/Pl-preserving)**  \n"
        "• Likelihood SD: a single conceptual sigma per class"
    )


def _render_dfi_pillar_warning(ctx) -> None:
    """Warn when the active model's pillars don't match the four the DFI core needs.

    The DFI Bayesian update is hardcoded to Charge / Closure / Reservoir /
    Retention.  If a model renames, drops, or adds a pillar, the prior builders
    silently substitute defaults (missing) or drop the pillar (extra), so the
    posterior is computed on the wrong geological tree without any error.  This
    surfaces that mismatch instead of letting it pass unnoticed.
    """
    check = _dfi_pillar_check(getattr(ctx, "play", {}) or {})
    if check["matched"]:
        return
    lines = [
        "⚠️ **DFI pillar mismatch** — the Bayesian update is hardcoded to the four "
        f"pillars **{', '.join(_DFI_REQUIRED_PILLARS)}**, but the active risk model "
        "does not match them. Results below may be computed on the wrong pillars."
    ]
    if check["missing"]:
        lines.append(
            f"- **Missing** (chance silently defaults to 0.5/0.1): "
            f"{', '.join(check['missing'])}"
        )
    if check["extra"]:
        lines.append(
            f"- **Extra** (ignored by the DFI product, so its risk is omitted): "
            f"{', '.join(check['extra'])}"
        )
    lines.append(
        "Use a model with the four standard pillars for a valid DFI update, or treat "
        "the posterior as indicative only."
    )
    st.warning("  \n".join(lines))


# Shared DFI prior/calibration primitives live in ``logic.dfi_context``; the
# three sub-page renderers now live in sibling ``tab_dfi_*`` modules.  This
# module keeps only the tab entry point, session defaults, and the two shared
# placeholders/guards above.
from logic.dfi_context import (
    dfi_pillar_check     as _dfi_pillar_check,
    DFI_REQUIRED_PILLARS as _DFI_REQUIRED_PILLARS,
)
from components.tabs.tab_dfi_setup import _render_dfi_setup
from components.tabs.tab_dfi_results import _render_dfi_results
from components.tabs.tab_dfi_summary import (
    _render_dfi_summary, _render_geological_pos_summary,
)


def _render_final_pos_tab(ctx) -> None:
    """Top-level **Final Prospect POS** — the reportable sign-off page.

    DFI-aware: when the DFI Bayesian update is enabled it shows the full
    prior→posterior summary (branching by evidence source); when DFI is off it
    shows the geological POS as the final number, so the tab is always meaningful.
    """
    st.markdown(
        "<div style='background:linear-gradient(135deg,#0f172a,#334155);color:#fff;"
        "padding:14px 18px;border-radius:8px;margin-bottom:10px;'>"
        "<b style='font-size:1.1rem;'>Final Prospect POS</b><br>"
        "<span style='font-size:0.85rem;opacity:0.9;'>"
        "The reportable probability of success for this prospect — geological POS, "
        "with the Bayesian DFI update layered in when enabled."
        "</span></div>",
        unsafe_allow_html=True,
    )
    if bool(st.session_state.get("dfi_enabled", False)):
        _render_dfi_summary(ctx)
    else:
        _render_geological_pos_summary(ctx)
