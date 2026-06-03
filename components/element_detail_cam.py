"""
Element Detail Assessment — full Chance Adequacy Matrix (CAM) panel.

Integrates the standalone GeoProb/CAM app's full assessment depth into each
E-POS risk element. Uses a staging pattern: edits live in the panel but are
only committed back to the model on explicit "Apply".

UI pattern (drawer):
  - Compact row per element in overview grid → "Assess ▶" button
  - Panel renders at fixed location in the section (not nested in row)
  - Apply writes staging → element dict + rerun
  - Cancel clears staging, closes panel

Session-state keys used:
  active_cam_scope       : "cond" | "play"
  active_cam_category    : "Charge" | "Closure" | "Reservoir" | "Retention"
  active_cam_idx         : int (conditional) | None (play)
  active_cam_key_prefix  : str  (e.g. "esl_cond_Charge_0")
  cam_stage_{kp}_{field} : staging values
"""

from __future__ import annotations

import numpy as np
import streamlit as st
import streamlit.components.v1 as _stc

try:
    from geoprob_matrix_html import make_geoprob_matrix_html
    _HAS_MATRIX = True
except ImportError:
    _HAS_MATRIX = False

# ─── Constants ────────────────────────────────────────────────────────────────

CONFLICT_PENALTY_LAMBDA = 2.5
Y_MODE_ECI    = "eci"
Y_MODE_C      = "commitment"
Y_MODE_MANUAL = "manual"
HALO_MODE_U   = "u_proportional"
HALO_MODE_W   = "w_based"
HALO_MODE_MAN = "manual"
DEFAULT_HALO_K       = 0.36
DEFAULT_HALO_B_SCALE = 0.15
DEFAULT_HALO_CLIP_HI = 0.20

ITALY_GREEN = "#008C45"
ITALY_RED   = "#CD212A"
_POS_IGNORANCE = 0.5

_PRMS_SCALE = [
    (0.90, "Highly Likely",  "#15803d"),
    (0.70, "Likely",         "#2563eb"),
    (0.50, "Uncertain",      "#d97706"),
    (0.30, "Unlikely",       "#dc2626"),
    (0.10, "Remote",         "#7c3aed"),
    (0.00, "Highly Remote",  "#9ca3af"),
]

_THEORY_REFS = """\
**Key references**

- Dempster (1967), Shafer (1976) — belief functions, Bel/Pl interval
- Smets (1990, 2005) — Transferable Belief Model, pignistic transformation for *w*
- Hall, Blockley & Davis (1998) — Italian flag / three-value logic
- Walley (1991) — imprecise probabilities, sensitivity intervals
- Otis & Schneidermann (1997) — ROSE adequacy matrix
- Rose (2001) *AAPG Methods 12* — risk analysis, analogue calibration
- SPE PRMS (2018) — verbal probability scale
"""

_ESL_ROSE_TENSION = """\
**ESL commitment vs ROSE adequacy — the fundamental tension**

**ESL Commitment C = S_for + S_against** asks: *How much evidence has been assessed?*
A high C means you have carefully examined the evidence. A 50/50 split at high C means
genuine geological conflict was found — ESL treats this as informative.

**ROSE adequacy / ECI = |S_for − S_against|** asks: *Does evidence produce a clear directional signal?*
A low ECI means the evidence does not clearly favour success or failure.
ROSE practice treats this as a problem to resolve — either via more data or by
re-framing the geological question.

**When they diverge (low ECI + high C):** Ask first — "Have I asked the right
geological question?" If yes and evidence is genuinely conflicting, report as contested
(ESL view). If the conflict could be resolved with targeted data, acquire it (ROSE view).
"""


# ─── Math helpers ─────────────────────────────────────────────────────────────

def _spe_prms_verbal(pos: float) -> tuple[str, str]:
    for thr, lbl, col in _PRMS_SCALE:
        if pos >= thr:
            return lbl, col
    return "Highly Remote", "#9ca3af"


def _bel_pl(s_n: float, s_neg: float) -> tuple[float, float]:
    bel = float(np.clip(s_n, 0.0, 1.0))
    pl  = float(np.clip(1.0 - s_neg, 0.0, 1.0))
    if pl < bel - 1e-12:
        m = 0.5 * (bel + pl)
        return m, m
    return bel, pl


def _eci(s_n: float, s_neg: float) -> float:
    return float(np.clip(abs(float(s_n) - float(s_neg)), 0.0, 1.0))


def _cam_pos(w: float, s_n: float, ev_sum: float) -> float:
    """POS = S_for + w × (1 − ev_sum).  Same formula handles both non-conflict and overcommit."""
    if ev_sum <= 1e-15:
        return _POS_IGNORANCE
    return float(np.clip(s_n + w * (1.0 - ev_sum), 0.0, 1.0))


def _r_g_from_evidence(s_n: float, s_neg: float, ev_sum: float) -> tuple[float, float]:
    """Evidence-derived r (negative boundary) and g (positive boundary) on POS axis."""
    if ev_sum <= 1e-12:
        return 0.25, 0.75
    if ev_sum <= 1.0 + 1e-9:
        r, g = float(s_neg), float(1.0 - s_n)
    else:
        r = float(s_neg / ev_sum)
        g = float(1.0 - s_n / ev_sum)
    r = float(np.clip(r, 0.0, 1.0))
    g = float(np.clip(g, 0.0, 1.0))
    if r > g + 1e-9:
        m = 0.5 * (r + g)
        r, g = m, m
    return r, g


def _halo_b(w: float, u: float, mode: str, manual_b: float = 0.0,
            b_scale: float = DEFAULT_HALO_B_SCALE, k: float = DEFAULT_HALO_K,
            b_add: float = 0.0, clip_lo: float = 0.0,
            clip_hi: float = DEFAULT_HALO_CLIP_HI) -> float:
    w = float(np.clip(w, 0.0, 1.0))
    u = float(np.clip(u, 0.0, 1.0))
    lo, hi = min(clip_lo, clip_hi), max(clip_lo, clip_hi)
    if mode == HALO_MODE_MAN:
        v = float(manual_b)
    elif mode == HALO_MODE_W:
        v = float(k) * abs(w - 0.5) + float(b_add)
    else:
        v = float(b_scale) * u
    return float(np.clip(v, lo, hi))


def _w_label(w: float) -> str:
    if w < 0.10: return "Stance: unknowns vote against success"
    if w < 0.25: return "Stance: cautious"
    if w < 0.42: return "Stance: mildly cautious"
    if w < 0.58: return "Stance: neutral (recommended)"
    if w < 0.75: return "Stance: mildly optimistic"
    if w < 0.90: return "Stance: optimistic"
    return "Stance: unknowns vote for success"


def _esl_verbal(s_n: float, s_neg: float) -> tuple[str, str, str]:
    C = float(s_n + s_neg)
    if C < 1e-9:
        return "Uninformed", "No evidence committed.", "#888888"
    Pg = float(s_n) / C
    if C < 0.30:
        if Pg >= 0.70:   return "Data gap – slight ⊕ lean",  f"C={C:.0%}, Pg={Pg:.0%}. White-dominated; slight positive signal.", "#a8d4a8"
        elif Pg <= 0.30: return "Data gap – slight ⊖ lean",  f"C={C:.0%}, Pg={Pg:.0%}. White-dominated; slight negative signal.", "#d4a8a8"
        else:            return "Data gap – no direction",    f"C={C:.0%}. Almost entirely white.",                                "#bbbbbb"
    elif C < 0.65:
        if Pg >= 0.75:   return "Supported – moderate evid.",  f"Positive predominates (Pg={Pg:.0%}, C={C:.0%}).",  "#5cb85c"
        elif Pg >= 0.60: return "Tentatively supported",        f"Leans positive (Pg={Pg:.0%}, C={C:.0%}).",          "#a8d4a8"
        elif Pg >= 0.40: return "Indeterminate – balanced",     f"Near-balanced (Pg={Pg:.0%}, C={C:.0%}).",           "#c8b820"
        elif Pg >= 0.25: return "Tentatively negated",          f"Leans negative (Pg={Pg:.0%}, C={C:.0%}).",          "#d4a8a8"
        else:            return "Negated – moderate evid.",     f"Negative predominates (Pg={Pg:.0%}, C={C:.0%}).",   "#d9534f"
    else:
        if Pg >= 0.80:   return "Strongly supported",          f"High commitment (C={C:.0%}), strongly positive (Pg={Pg:.0%}).",   "#1a7a1a"
        elif Pg >= 0.65: return "Supported – strong evid.",    f"Positive, high commitment (Pg={Pg:.0%}, C={C:.0%}).",             "#4caf50"
        elif Pg >= 0.35: return "Contested – high commitment", f"High commitment (C={C:.0%}) but genuinely contested (Pg={Pg:.0%}).", "#c07800"
        elif Pg >= 0.20: return "Negated – strong evid.",      f"Negative, high commitment (Pg={Pg:.0%}, C={C:.0%}).",             "#d9534f"
        else:            return "Strongly negated",            f"High commitment (C={C:.0%}), strongly negative (Pg={Pg:.0%}).",   "#8b0000"


def _eci_verbal(eci: float, c: float, s_n: float, s_neg: float) -> tuple[str, str, str]:
    if eci < 0.05:
        if c > 0.60: return "Indeterminate – contested",      f"ECI={eci:.0%}, C={c:.0%}. High commitment, near-equal evidence.", "#c07800"
        if c > 0.25: return "Balanced – low discrimination",  f"ECI={eci:.0%}, C={c:.0%}. Moderate commitment, near-equal.",      "#a87800"
        return "No signal – data gap",                        f"ECI={eci:.0%}, C={c:.0%}. Very little evidence.",                  "#888888"
    if eci < 0.20:
        if c > 0.50: return "Weak signal – low adequacy",     f"ECI={eci:.0%}, C={c:.0%}. Weak direction.",                       "#d4840a"
        return "Weak early signal",                           f"ECI={eci:.0%}, C={c:.0%}. Early indication.",                     "#c07800"
    if eci < 0.45:
        if s_n > s_neg: return "Moderate ⊕ signal",           f"ECI={eci:.0%}, C={c:.0%}. More positive than negative.",          "#5cb85c"
        return "Moderate ⊖ signal",                           f"ECI={eci:.0%}, C={c:.0%}. More negative than positive.",          "#d9534f"
    if c > 0.55:
        if s_n > s_neg: return "Strong ⊕ – high adequacy",    f"ECI={eci:.0%}, C={c:.0%}. Well-evidenced positive.",              "#1a7a1a"
        return "Strong ⊖ – high adequacy",                    f"ECI={eci:.0%}, C={c:.0%}. Well-evidenced negative.",              "#8b0000"
    if s_n > s_neg: return "Clear ⊕ – thin evidence",         f"ECI={eci:.0%}, C={c:.0%}. Clear direction, modest evidence.",     "#4caf50"
    return "Clear ⊖ – thin evidence",                         f"ECI={eci:.0%}, C={c:.0%}. Clearly negative.",                    "#f44336"


# ─── Staging helpers ──────────────────────────────────────────────────────────

def _sk(key_prefix: str, field: str) -> str:
    return f"cam_stage_{key_prefix}_{field}"


def _init_stage(element: dict, key_prefix: str, global_w: float) -> None:
    """Initialize staging from element values (runs once per open)."""
    if st.session_state.get(_sk(key_prefix, "_init")):
        return
    st.session_state[_sk(key_prefix, "for")]      = float(element.get("support_for", 0.5))
    st.session_state[_sk(key_prefix, "against")]  = float(element.get("support_against", 0.1))
    st.session_state[_sk(key_prefix, "ev_for")]   = str(element.get("evidence_for", ""))
    st.session_state[_sk(key_prefix, "ev_ag")]    = str(element.get("evidence_against", ""))
    st.session_state[_sk(key_prefix, "unc")]      = str(element.get("uncertainty_note", ""))
    st.session_state[_sk(key_prefix, "sc")]       = str(element.get("success_criteria", ""))
    # w override
    w_ov = bool(st.session_state.get(f"{key_prefix}_w_override", False))
    w_val = float(st.session_state.get(f"{key_prefix}_w_slider",
                  element.get("_cam_w", global_w)))
    st.session_state[_sk(key_prefix, "w_ov")]    = w_ov
    st.session_state[_sk(key_prefix, "w_val")]   = w_val
    st.session_state[_sk(key_prefix, "w_just")]  = str(st.session_state.get(f"{key_prefix}_w_just", ""))
    # CAM display settings
    st.session_state[_sk(key_prefix, "y_mode")]      = Y_MODE_ECI
    st.session_state[_sk(key_prefix, "b_scale")]     = DEFAULT_HALO_B_SCALE
    st.session_state[_sk(key_prefix, "clip_hi")]     = DEFAULT_HALO_CLIP_HI
    st.session_state[_sk(key_prefix, "show_sens")]   = True
    st.session_state[_sk(key_prefix, "halo_mode")]   = HALO_MODE_U
    st.session_state[_sk(key_prefix, "_init")]       = True


def _apply_stage(element: dict, key_prefix: str) -> None:
    """Write staging values back to element dict and the global w-override keys."""
    element["support_for"]      = float(st.session_state.get(_sk(key_prefix, "for"),     0.5))
    element["support_against"]  = float(st.session_state.get(_sk(key_prefix, "against"), 0.1))
    element["evidence_for"]     = str(st.session_state.get(_sk(key_prefix, "ev_for"), ""))
    element["evidence_against"] = str(st.session_state.get(_sk(key_prefix, "ev_ag"),  ""))
    element["uncertainty_note"] = str(st.session_state.get(_sk(key_prefix, "unc"),    ""))
    element["success_criteria"] = str(st.session_state.get(_sk(key_prefix, "sc"),
                                       element.get("success_criteria", "")))
    element["_cam_w"]           = float(st.session_state.get(_sk(key_prefix, "w_val"), 0.5))
    # Keep the global E-POS w-override keys in sync so render_flag_stats uses the right w
    st.session_state[f"{key_prefix}_w_override"] = bool(
        st.session_state.get(_sk(key_prefix, "w_ov"), False))
    st.session_state[f"{key_prefix}_w_slider"]   = float(
        st.session_state.get(_sk(key_prefix, "w_val"), 0.5))
    st.session_state[f"{key_prefix}_w_just"]     = str(
        st.session_state.get(_sk(key_prefix, "w_just"), ""))


def _clear_stage(key_prefix: str) -> None:
    fields = ["for", "against", "ev_for", "ev_ag", "unc", "sc",
              "w_ov", "w_val", "w_just",
              "y_mode", "b_scale", "clip_hi", "show_sens", "halo_mode", "_init"]
    for f in fields:
        st.session_state.pop(_sk(key_prefix, f), None)


def close_active_cam() -> None:
    """Close the active CAM panel without applying (cancel)."""
    kp = st.session_state.get("active_cam_key_prefix", "")
    if kp:
        _clear_stage(kp)
    for k in ["active_cam_scope", "active_cam_category", "active_cam_idx",
              "active_cam_key_prefix"]:
        st.session_state.pop(k, None)


def open_element_cam(scope: str, category: str, idx: int | None, key_prefix: str) -> None:
    """Open the CAM panel for a specific element."""
    # If switching to a different element, discard previous staging without applying
    prev = st.session_state.get("active_cam_key_prefix", "")
    if prev and prev != key_prefix:
        _clear_stage(prev)
    st.session_state["active_cam_scope"]      = scope
    st.session_state["active_cam_category"]   = category
    st.session_state["active_cam_idx"]        = idx
    st.session_state["active_cam_key_prefix"] = key_prefix


# ─── Compact element row ───────────────────────────────────────────────────────

def render_compact_element_row(
    element: dict,
    key_prefix: str,
    global_w: float,
    category: str,
    scope: str,
    category_color: str = "#6b7280",
) -> None:
    """One-line summary row for an element in the overview grid.

    Shows: Italian flag  |  POS  |  C (commitment)  |  ECI  |  w indicator  |  [Assess ▶]
    """
    is_active = st.session_state.get("active_cam_key_prefix") == key_prefix

    # Read from staging when the CAM panel is open so the mini-flag tracks slider changes live
    sf  = float(st.session_state.get(_sk(key_prefix, "for"), element.get("support_for", 0.5)) if is_active
                else element.get("support_for", 0.5))
    sa  = float(st.session_state.get(_sk(key_prefix, "against"), element.get("support_against", 0.1)) if is_active
                else element.get("support_against", 0.1))

    ev_sum = sf + sa
    conflict = max(0.0, ev_sum - 1.0)
    u   = max(0.0, 1.0 - ev_sum)
    cert = ev_sum if ev_sum <= 1.0 else 1.0 / (1.0 + CONFLICT_PENALTY_LAMBDA * conflict)

    # Effective w for this element (read from staging if panel open, else global override keys)
    w_ov  = bool(st.session_state.get(_sk(key_prefix, "w_ov"), False) if is_active
                 else st.session_state.get(f"{key_prefix}_w_override", False))
    w_eff = float(st.session_state.get(_sk(key_prefix, "w_val"), global_w) if is_active
                  else st.session_state.get(f"{key_prefix}_w_slider", global_w)) if w_ov else global_w
    pos   = _cam_pos(w_eff, sf, ev_sum)
    eci_v = _eci(sf, sa)
    bel, pl = _bel_pl(sf, sa)

    label     = element.get("label", "")
    sc        = element.get("success_criteria", "")

    green_non = max(0.0, sf - max(0.0, sf + sa - 1.0))
    white     = max(0.0, 1.0 - sf - sa + max(0.0, sf + sa - 1.0))
    overlap   = max(0.0, sf + sa - 1.0)
    red_non   = max(0.0, sa - overlap)

    # Mini flag: position:relative wrapper with overflow:hidden, absolute POS marker inside
    _marker_pct = min(max(pos * 100, 0.0), 100.0)
    flag_html = (
        f"<div style='position:relative;display:flex;height:14px;width:100%;min-width:80px;"
        f"border:1px solid #555;border-radius:3px;overflow:hidden;'>"
        f"<div style='width:{green_non*100:.1f}%;background:#2e9d5b;height:100%;'></div>"
        f"<div style='width:{white*100:.1f}%;background:#f3f4f6;height:100%;'></div>"
        f"<div style='width:{overlap*100:.1f}%;background:#f6c343;height:100%;'></div>"
        f"<div style='width:{red_non*100:.1f}%;background:#d64545;height:100%;'></div>"
        f"<div style='position:absolute;left:{_marker_pct:.1f}%;top:0;bottom:0;width:2px;"
        f"background:#1f2937;opacity:0.9;transform:translateX(-50%);'></div>"
        f"</div>"
    )

    prms_lbl, prms_col = _spe_prms_verbal(pos)
    # w display: show override indicator if element stance differs from global
    w_is_override = w_ov and abs(w_eff - global_w) > 0.001
    w_color   = "#d97706" if w_is_override else "#6b7280"
    w_display = f"⚑{w_eff:.2f}" if w_is_override else f"{w_eff:.2f}"
    w_sub     = "local" if w_is_override else "global"

    c_label, c_flag, c_pos, c_eci, c_cert, c_w, c_btn = st.columns([4, 3, 1, 1, 1, 1, 1])

    with c_label:
        _active_style = "color:#2563eb;font-weight:700;" if is_active else ""
        _arrow = "▶ " if is_active else ""
        _sc_display = (sc[:70] + "…") if len(sc) > 70 else sc
        st.markdown(
            f"<div style='font-size:0.82rem;padding:4px 0;{_active_style}'>"
            f"{_arrow}{label}</div>"
            f"<div style='font-size:0.75rem;color:#6b7280;white-space:nowrap;overflow:hidden;"
            f"text-overflow:ellipsis;max-width:100%;'>{_sc_display}</div>",
            unsafe_allow_html=True,
        )
    with c_flag:
        st.markdown(flag_html + f"<div style='font-size:0.68rem;color:#888;margin-top:1px'>"
                    f"G{sf*100:.0f}% W{u*100:.0f}% R{sa*100:.0f}% "
                    f"<b style='color:{prms_col};'>POS{pos*100:.0f}%</b>"
                    f"{' ⚠️OC' if conflict > 0 else ''}</div>", unsafe_allow_html=True)
    with c_pos:
        st.markdown(
            f"<div style='font-size:0.9rem;font-weight:700;color:{prms_col};text-align:center'>"
            f"{pos*100:.0f}%</div>"
            f"<div style='font-size:0.65rem;color:{prms_col};text-align:center'>{prms_lbl}</div>",
            unsafe_allow_html=True,
        )
    with c_eci:
        eci_lbl, _, eci_col = _eci_verbal(eci_v, cert, sf, sa)
        st.markdown(
            f"<div style='font-size:0.85rem;font-weight:600;color:{eci_col};text-align:center'>"
            f"{eci_v*100:.0f}%</div>"
            f"<div style='font-size:0.65rem;color:#888;text-align:center'>ECI</div>",
            unsafe_allow_html=True,
        )
    with c_cert:
        st.markdown(
            f"<div style='font-size:0.85rem;font-weight:600;color:#555;text-align:center'>"
            f"{cert*100:.0f}%</div>"
            f"<div style='font-size:0.65rem;color:#888;text-align:center'>C</div>",
            unsafe_allow_html=True,
        )
    with c_w:
        st.markdown(
            f"<div style='font-size:0.85rem;font-weight:600;color:{w_color};text-align:center'>"
            f"{w_display}</div>"
            f"<div style='font-size:0.65rem;color:{w_color};text-align:center'>{w_sub}</div>",
            unsafe_allow_html=True,
        )
    with c_btn:
        btn_label = "▶ Close" if is_active else "▶ Assess"
        btn_type  = "secondary" if is_active else "primary"

        def _on_assess(
            _is_active=is_active,
            _kp=key_prefix,
            _el=element,
            _gw=global_w,
            _sc=scope,
            _cat=category,
        ):
            if _is_active:
                close_active_cam()
            else:
                _idx = int(_kp.split("_")[-1]) if _sc == "cond" else None
                open_element_cam(_sc, _cat, _idx, _kp)
                _init_stage(_el, _kp, _gw)

        st.button(
            btn_label, key=f"btn_assess_{key_prefix}", type=btn_type,
            use_container_width=True, on_click=_on_assess,
        )


# ─── Full CAM detail panel ────────────────────────────────────────────────────

def render_element_cam_panel(
    element: dict,
    key_prefix: str,
    global_w: float,
    category: str | None = None,
    scope: str = "cond",
) -> None:
    """Render the full Chance Adequacy Matrix assessment panel for one element.

    Call this once at the top of the section (before the overview grid) when
    st.session_state["active_cam_key_prefix"] == key_prefix.
    """
    _init_stage(element, key_prefix, global_w)

    display_cat = category or ""
    cat_colors  = {"Charge": "#F69292", "Closure": "#8CB7FC",
                   "Reservoir": "#FFD44B", "Retention": "#B5E6A2"}
    header_bg = cat_colors.get(display_cat, "#e5e7eb")

    # ── Panel header ──────────────────────────────────────────────────────────
    st.markdown(
        f"<div style='background:{header_bg};border-radius:6px;padding:10px 16px;"
        f"margin-bottom:10px;border-left:6px solid #1f2937;'>"
        f"<span style='font-size:0.75rem;font-weight:700;color:#374151;text-transform:uppercase;"
        f"letter-spacing:0.08em;'>DETAIL ASSESSMENT — {display_cat}</span><br>"
        f"<span style='font-size:1.05rem;font-weight:700;color:#111;'>"
        f"{element.get('label','')}</span>"
        + (f"<br><span style='font-size:0.8rem;color:#555;'>"
           f"{element.get('success_criteria','')}</span>"
           if element.get('success_criteria') else "")
        + "</div>",
        unsafe_allow_html=True,
    )

    # ── Apply / Cancel / w controls ──────────────────────────────────────────
    # Use on_click so the callback runs before the natural button-rerun, avoiding
    # an explicit st.rerun() that would reset the active tab position.
    def _on_apply(_el=element, _kp=key_prefix):
        _apply_stage(_el, _kp)
        close_active_cam()

    def _on_cancel(_kp=key_prefix):
        close_active_cam()

    hdr_col_apply, hdr_col_cancel, hdr_col_w = st.columns([1, 1, 4])
    with hdr_col_apply:
        st.button("✔ Apply", key=f"cam_apply_{key_prefix}",
                  type="primary", use_container_width=True,
                  help="Commit these values to the prospect model.",
                  on_click=_on_apply)
    with hdr_col_cancel:
        st.button("✖ Cancel", key=f"cam_cancel_{key_prefix}",
                  use_container_width=True,
                  help="Discard changes and close panel.",
                  on_click=_on_cancel)
    with hdr_col_w:
        w_ov_key  = _sk(key_prefix, "w_ov")
        w_val_key = _sk(key_prefix, "w_val")
        w_just_key = _sk(key_prefix, "w_just")
        w_override = st.checkbox(
            f"Override global stance (currently w = {global_w:.2f} — {_w_label(global_w)})",
            key=w_ov_key,
            help="The global stance (w) is set in the Dashboard. Override here for this element only. An override will be flagged in the overview.",
        )
        if w_override:
            w_curr = float(st.session_state.get(w_val_key, global_w))
            st.slider(
                f"Element stance (w) — {_w_label(w_curr)}",
                0.0, 1.0, w_curr, 0.05,
                key=w_val_key,
                help="0 = unknowns vote against success (pessimistic). 0.5 = neutral (Laplace). 1 = unknowns vote for success (optimistic). POS = S_for + w × U.",
            )
            st.text_input(
                "Justification for stance override (required)",
                key=w_just_key,
                placeholder="Why does this element warrant a different stance than company policy?",
            )
            if not st.session_state.get(w_just_key, "").strip():
                st.warning("Document the reason for this stance override.")
            eff_w = float(st.session_state.get(w_val_key, global_w))
        else:
            st.session_state[w_val_key] = global_w
            eff_w = global_w
            st.caption(f"Using global stance w = {global_w:.2f} — {_w_label(global_w)}")

    st.divider()

    # ── Read staged values ────────────────────────────────────────────────────
    sf_stage  = float(st.session_state.get(_sk(key_prefix, "for"),     0.5))
    sa_stage  = float(st.session_state.get(_sk(key_prefix, "against"), 0.1))
    ev_sum    = sf_stage + sa_stage
    conflict  = max(0.0, ev_sum - 1.0)
    u_live    = max(0.0, 1.0 - ev_sum)
    cert      = ev_sum if ev_sum <= 1.0 else 1.0 / (1.0 + CONFLICT_PENALTY_LAMBDA * conflict)

    pos    = _cam_pos(eff_w, sf_stage, ev_sum)
    bel, pl = _bel_pl(sf_stage, sa_stage)
    eci_v  = _eci(sf_stage, sa_stage)
    r_ev, g_ev = _r_g_from_evidence(sf_stage, sa_stage, ev_sum)

    prms_lbl, prms_col = _spe_prms_verbal(pos)
    esl_lbl, esl_desc, esl_col = _esl_verbal(sf_stage, sa_stage)
    eci_lbl, eci_desc, eci_col = _eci_verbal(eci_v, cert, sf_stage, sa_stage)

    # ── Evidence Inputs ───────────────────────────────────────────────────────
    inp_col_for, inp_col_u, inp_col_ag = st.columns([5, 2, 5])

    with inp_col_for:
        st.markdown(
            f"<div style='font-size:0.8rem;font-weight:700;color:{ITALY_GREEN};"
            f"margin-bottom:3px;'>⊕ Support For — S_for</div>"
            f"<div style='font-size:0.72rem;color:#888;'>Fraction of evidence supporting success</div>",
            unsafe_allow_html=True,
        )
        st.slider(
            "S_for",
            0.0, 1.0,
            float(st.session_state.get(_sk(key_prefix, "for"), 0.5)),
            0.05,
            key=_sk(key_prefix, "for"),
            label_visibility="collapsed",
            help="Green segment. 0 = no positive evidence. 1 = fully committed positive.",
        )
        st.text_area(
            "Evidence for",
            key=_sk(key_prefix, "ev_for"),
            placeholder="List data supporting success. Be specific: well, seismic, analogue.",
            height=90,
            label_visibility="collapsed",
        )

    with inp_col_u:
        # Read updated slider values
        sf_now = float(st.session_state.get(_sk(key_prefix, "for"), sf_stage))
        sa_now = float(st.session_state.get(_sk(key_prefix, "against"), sa_stage))
        u_now  = max(0.0, 1.0 - sf_now - sa_now)
        oc_now = max(0.0, sf_now + sa_now - 1.0)
        if oc_now > 0:
            st.markdown(
                "<div style='font-size:0.8rem;font-weight:700;color:#b45309;margin-bottom:3px;'>"
                "⚠️ Overcommit — U (conflict)</div>"
                "<div style='font-size:0.72rem;color:#aaa;'>= 1 − S_for − S_against</div>",
                unsafe_allow_html=True,
            )
            st.slider(
                "U_display",
                0.0, 1.0, float(u_now if u_now >= 0 else 0.0), 0.01,
                key=f"_u_display_{key_prefix}",
                label_visibility="collapsed",
                disabled=True,
                help=f"Overcommit: S_for + S_against = {(sf_now+sa_now)*100:.0f}% > 100%. Conflict = {oc_now*100:.0f}%.",
            )
            st.markdown(
                f"<div style='background:#fef3c7;border-left:3px solid #d4a017;padding:4px 7px;"
                f"border-radius:0 4px 4px 0;font-size:0.75rem;color:#7a5700;margin-top:2px;'>"
                f"Conflict {oc_now*100:.0f}%</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='font-size:0.8rem;font-weight:700;color:#6b7280;margin-bottom:3px;'>"
                "⬜ Unknowns — U (auto)</div>"
                "<div style='font-size:0.72rem;color:#aaa;'>= 1 − S_for − S_against · not editable</div>",
                unsafe_allow_html=True,
            )
            st.slider(
                "U_display",
                0.0, 1.0, float(u_now), 0.01,
                key=f"_u_display_{key_prefix}",
                label_visibility="collapsed",
                disabled=True,
                help="Unknown mass U = 1 − S_for − S_against (read-only). Adjust the For or Against sliders to change this.",
            )
        st.text_area(
            "Uncertainty note",
            key=_sk(key_prefix, "unc"),
            placeholder="What would resolve this? 3D seismic? Well? Basin model?",
            height=90,
            label_visibility="collapsed",
        )

    with inp_col_ag:
        st.markdown(
            f"<div style='font-size:0.8rem;font-weight:700;color:{ITALY_RED};"
            f"margin-bottom:3px;'>⊖ Support Against — S_against</div>"
            f"<div style='font-size:0.72rem;color:#888;'>Fraction of evidence negating success</div>",
            unsafe_allow_html=True,
        )
        st.slider(
            "S_against",
            0.0, 1.0,
            float(st.session_state.get(_sk(key_prefix, "against"), 0.1)),
            0.05,
            key=_sk(key_prefix, "against"),
            label_visibility="collapsed",
            help="Red segment. 0 = no negative evidence. Leave 0 only if truly no counter-evidence.",
        )
        st.text_area(
            "Evidence against",
            key=_sk(key_prefix, "ev_ag"),
            placeholder="List data against success. Negative analogues, geochemistry, seismic negatives.",
            height=90,
            label_visibility="collapsed",
        )

    st.divider()

    # Re-read after slider updates
    sf_now = float(st.session_state.get(_sk(key_prefix, "for"),     sf_stage))
    sa_now = float(st.session_state.get(_sk(key_prefix, "against"), sa_stage))
    ev_now = sf_now + sa_now
    u_now  = max(0.0, 1.0 - ev_now)
    conf_now = max(0.0, ev_now - 1.0)
    cert_now = ev_now if ev_now <= 1.0 else 1.0 / (1.0 + CONFLICT_PENALTY_LAMBDA * conf_now)
    pos_now  = _cam_pos(eff_w, sf_now, ev_now)
    bel_now, pl_now = _bel_pl(sf_now, sa_now)
    eci_now  = _eci(sf_now, sa_now)
    r_ev_now, g_ev_now = _r_g_from_evidence(sf_now, sa_now, ev_now)
    prms_now, prms_col_now = _spe_prms_verbal(pos_now)
    esl_lbl_now, esl_desc_now, esl_col_now = _esl_verbal(sf_now, sa_now)
    eci_lbl_now, eci_desc_now, eci_col_now = _eci_verbal(eci_now, cert_now, sf_now, sa_now)

    # ── Metrics row ───────────────────────────────────────────────────────────
    m_col_pos, m_col_range, m_col_esl, m_col_eci = st.columns([2, 2, 3, 3])

    with m_col_pos:
        st.markdown(
            f"<div style='font-size:0.72rem;font-weight:600;color:#888;text-transform:uppercase;"
            f"letter-spacing:.06em;'>ESL — Policy P</div>"
            f"<div style='font-size:2.4rem;font-weight:800;line-height:1;color:#1a1a1a;"
            f"letter-spacing:-1px;'>{pos_now*100:.1f}%</div>"
            f"<span style='font-size:0.78rem;font-weight:600;padding:2px 8px;border-radius:4px;"
            f"background:{prms_col_now}1a;color:{prms_col_now};border:1px solid {prms_col_now}55;"
            f"'>{prms_now}</span>"
            f"<div style='font-size:0.72rem;color:#888;margin-top:4px;'>"
            f"S_for + w × U = {sf_now:.2f} + {eff_w:.2f}×{u_now:.2f}</div>",
            unsafe_allow_html=True,
        )

    with m_col_range:
        bel_lbl, bel_col = _spe_prms_verbal(bel_now)
        pl_lbl,  pl_col  = _spe_prms_verbal(pl_now)
        st.markdown(
            f"<div style='font-size:0.72rem;font-weight:600;color:#888;text-transform:uppercase;"
            f"letter-spacing:.06em;'>Bel / Pl Interval</div>"
            f"<div style='font-size:1.3rem;font-weight:700;line-height:1.2;'>"
            f"<span style='color:{bel_col};'>{bel_now*100:.0f}%</span>"
            f" <span style='color:#ccc;'>—</span> "
            f"<span style='color:{pl_col};'>{pl_now*100:.0f}%</span></div>"
            f"<div style='font-size:0.72rem;color:#888;margin-top:3px;'>Bel=S_for at w=0 · Pl=1−S_ag at w=1</div>"
            f"<div style='position:relative;height:8px;background:#eee;border-radius:4px;"
            f"overflow:hidden;margin-top:6px;'>"
            f"<div style='position:absolute;left:{bel_now*100:.1f}%;right:{(1-pl_now)*100:.1f}%;"
            f"top:0;height:100%;background:linear-gradient(to right,{bel_col}55,{pl_col}55);'></div>"
            f"<div style='position:absolute;left:{pos_now*100:.1f}%;top:-1px;width:4px;height:10px;"
            f"background:#1a50c0;border-radius:2px;transform:translateX(-50%);'></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with m_col_esl:
        st.markdown(
            f"<div style='font-size:0.72rem;font-weight:600;color:#888;text-transform:uppercase;"
            f"letter-spacing:.06em;'>ESL Commitment</div>"
            f"<div style='font-size:1.5rem;font-weight:700;color:#222;'>{cert_now*100:.0f}%</div>"
            f"<div style='font-size:0.72rem;color:#aaa;'>C = S_for + S_against</div>"
            f"<div style='border-left:3px solid {esl_col_now};padding:2px 6px;"
            f"background:{esl_col_now}12;border-radius:0 4px 4px 0;margin-top:4px;"
            f"font-size:0.78rem;font-weight:600;color:{esl_col_now};'>{esl_lbl_now}</div>"
            f"<div style='font-size:0.7rem;color:#777;margin-top:3px;'>{esl_desc_now[:80]}</div>",
            unsafe_allow_html=True,
        )

    with m_col_eci:
        st.markdown(
            f"<div style='font-size:0.72rem;font-weight:600;color:#888;text-transform:uppercase;"
            f"letter-spacing:.06em;'>Evidence Clarity (ECI)</div>"
            f"<div style='font-size:1.5rem;font-weight:700;color:#222;'>{eci_now*100:.0f}%</div>"
            f"<div style='font-size:0.72rem;color:#aaa;'>|S_for − S_against|</div>"
            f"<div style='border-left:3px solid {eci_col_now};padding:2px 6px;"
            f"background:{eci_col_now}12;border-radius:0 4px 4px 0;margin-top:4px;"
            f"font-size:0.78rem;font-weight:600;color:{eci_col_now};'>{eci_lbl_now}</div>"
            f"<div style='font-size:0.7rem;color:#777;margin-top:3px;'>{eci_desc_now[:80]}</div>",
            unsafe_allow_html=True,
        )

    # ESL-ROSE tension warning
    if cert_now > 0.55 and eci_now < 0.25:
        st.warning(
            f"**ESL–ROSE tension:** C={cert_now:.0%} (high commitment) but ECI={eci_now:.0%} "
            f"(weak directional clarity). **ESL:** contested geology — well-evidenced conflict. "
            f"**ROSE:** adequacy failure if targeted data could resolve the direction. "
            f"Document which interpretation applies before reporting POS = {pos_now*100:.0f}%."
        )

    # Low evidence warning
    if ev_now < 0.20:
        st.info(
            f"Total evidence committed: **{ev_now:.0%}**. POS is dominated by your stance w = {eff_w:.2f}, "
            "not by evidence. Consider whether more geological data can be quantified."
        )

    st.divider()

    # ── Chance Adequacy Matrix ────────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:0.8rem;font-weight:600;color:#555;margin-bottom:4px;'>"
        "Chance Adequacy Matrix</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "**Reading the chart:** X-axis = POS (reversed, high left). Y-axis = Evidence Clarity Index "
        "(ECI = |S_for−S_against|) by default. The gradient colours every feasible point by its implied Pg "
        "(green = positive, amber = balanced, red = negative); saturation increases with commitment C. "
        "**Blue dot** = your current assessment. **Gray dot** = alternate Y reference (ECI or C)."
    )

    # Y-axis mode selector
    y_mode_key = _sk(key_prefix, "y_mode")
    y_mode = st.radio(
        "Y-axis",
        [Y_MODE_ECI, Y_MODE_C, Y_MODE_MANUAL],
        format_func=lambda x: {Y_MODE_ECI: "ECI (ROSE-style)", Y_MODE_C: "Commitment C (ESL)", Y_MODE_MANUAL: "Manual"}[x],
        horizontal=True,
        key=y_mode_key,
        help="ECI = |S_for−S_against|: zero when 50/50, max when one-sided. C = total committed mass.",
    )
    manual_y = 0.5
    if y_mode == Y_MODE_MANUAL:
        manual_y = st.slider("Manual Y", 0.0, 1.0, 0.5, 0.05,
                             key=_sk(key_prefix, "manual_y"),
                             help="Independent data quality score (0=none, 1=excellent).")

    if y_mode == Y_MODE_ECI:
        y_ax_val   = float(eci_now)
        y_ax_label = "Evidence Clarity Index |S_for − S_against|"
        y_sec      = float(cert_now)
    elif y_mode == Y_MODE_C:
        y_ax_val   = float(cert_now)
        y_ax_label = "ESL Commitment C = S_for + S_against"
        y_sec      = float(eci_now)
    else:
        y_ax_val   = float(st.session_state.get(_sk(key_prefix, "manual_y"), manual_y))
        y_ax_label = f"Data confidence (manual = {y_ax_val:.0%})"
        y_sec      = float(eci_now)

    # Sensitivity zone settings
    show_sens_key = _sk(key_prefix, "show_sens")
    b_scale_key   = _sk(key_prefix, "b_scale")
    clip_hi_key   = _sk(key_prefix, "clip_hi")
    halo_mode_key = _sk(key_prefix, "halo_mode")
    show_sens = bool(st.session_state.get(show_sens_key, True))
    b_scale   = float(st.session_state.get(b_scale_key, DEFAULT_HALO_B_SCALE))
    clip_hi   = float(st.session_state.get(clip_hi_key, DEFAULT_HALO_CLIP_HI))
    halo_mode = str(st.session_state.get(halo_mode_key, HALO_MODE_U))

    x_blur = _halo_b(eff_w, u_now if conf_now < 1e-9 else 0.0,
                     mode=halo_mode, b_scale=b_scale, clip_hi=clip_hi)

    if _HAS_MATRIX:
        elem_name = (element.get("label", "") + " · " + element.get("success_criteria", ""))[:60]
        html_chart = make_geoprob_matrix_html(
            s_n=float(sf_now),
            s_neg_n=float(sa_now),
            w=float(eff_w),
            pos=float(pos_now),
            eci=float(eci_now),
            y_esl_commitment=float(cert_now),
            bel=float(bel_now),
            pl=float(pl_now),
            uncertainty=float(u_now),
            conflict=float(conf_now),
            element_name=elem_name,
            r_ev=float(r_ev_now),
            g_ev=float(g_ev_now),
            sens_b=float(x_blur),
            y_mode=str(y_mode),
            y_axis_value=float(y_ax_val),
            esl_label=str(esl_lbl_now),
            eci_label=str(eci_lbl_now),
            prms_label=str(prms_now),
            y_axis_label=str(y_ax_label),
        )
        # Constrain to ~67 % of page width so the canvas stays proportionally shorter
        # and the bottom controls (checkboxes, legend, explanation) are always visible.
        # Play-scope assessments use a shorter height so the panel stays compact above the element grid.
        _cam_height = 430 if scope == "play" else 510
        _cam_col, _cam_spacer = st.columns([2, 1])
        with _cam_col:
            _stc.html(html_chart, height=_cam_height, scrolling=False)
    else:
        st.warning("geoprob_matrix_html.py not found — matrix plot unavailable.")

    # ── Robustness & Advanced settings ───────────────────────────────────────
    with st.expander("Robustness metrics", expanded=False):
        ws_range = np.linspace(0.1, 0.9, 801)
        pos_range = [_cam_pos(float(wi), sf_now, ev_now) for wi in ws_range]
        pos_min_w = float(np.min(pos_range))
        pos_max_w = float(np.max(pos_range))
        in_green  = sum(1 for p in pos_range if p >= float(g_ev_now))
        robust_pct = 100.0 * in_green / len(ws_range)

        if u_now < 1e-12:
            w_min_green = None
        else:
            w_thr = (float(g_ev_now) - sf_now) / u_now
            w_min_green = float(np.clip(w_thr, 0.0, 1.0))

        r1, r2, r3 = st.columns(3)
        with r1:
            st.metric("POS at w=0.1 (cautious)",  f"{_cam_pos(0.1, sf_now, ev_now)*100:.1f}%")
            st.metric("POS at w=0.5 (neutral)",   f"{_cam_pos(0.5, sf_now, ev_now)*100:.1f}%")
            st.metric("POS at w=0.9 (optimistic)", f"{_cam_pos(0.9, sf_now, ev_now)*100:.1f}%")
        with r2:
            st.metric("POS range w∈[10%,90%]",
                      f"{pos_min_w*100:.1f}% – {pos_max_w*100:.1f}%")
            st.metric("% of w-range → Positive zone",
                      f"{robust_pct:.0f}%",
                      help=f"Fraction of w values [10%,90%] where POS ≥ g={g_ev_now:.0%}")
        with r3:
            if w_min_green is not None:
                st.metric("Min w for Positive zone",
                          f"{w_min_green*100:.0f}%",
                          help=f"Minimum stance w needed to reach POS ≥ g={g_ev_now:.0%}")
            fc_pos = sf_now / ev_now if ev_now > 1e-9 else 0.5
            st.metric("Full-commitment scenario",
                      f"{fc_pos*100:.0f}%",
                      help="POS if all uncommitted mass resolved in same For/Against ratio.")
        st.caption(
            "g (positive boundary) = 1 − S_for. Positive zone: POS ≥ g. "
            "Full-commitment: what POS would be if U=0 at current evidence ratio."
        )

    with st.expander("Sensitivity zone settings", expanded=False):
        st.checkbox("Show sensitivity zones on matrix", key=show_sens_key)
        hm_labels = {HALO_MODE_U: "U-proportional (b = scale × U)", HALO_MODE_W: "w-based (legacy)", HALO_MODE_MAN: "Fixed"}
        st.radio("Zone width formula", [HALO_MODE_U, HALO_MODE_W, HALO_MODE_MAN],
                 format_func=lambda x: hm_labels[x], key=halo_mode_key, horizontal=True)
        st.slider("Scale (b = scale × U)", 0.0, 0.40, DEFAULT_HALO_B_SCALE, 0.01, key=b_scale_key)
        st.slider("Max b (clip_hi)",        0.02, 0.25, DEFAULT_HALO_CLIP_HI, 0.01, key=clip_hi_key)
        st.caption(f"Current halo half-width b = {x_blur:.3f}")

    with st.expander("Theory — ESL, ROSE adequacy, Bel/Pl", expanded=False):
        st.markdown(_ESL_ROSE_TENSION)
        st.divider()
        st.markdown(_THEORY_REFS)

    # ── Classic / calibration bridge ──────────────────────────────────────────
    with st.expander("P(G, Classic) / calibration bridge (read-only)", expanded=False):
        derived_pos = pos_now
        st.markdown(f"**Policy P for this element: {derived_pos*100:.1f}%**")
        st.markdown(
            f"Policy P = S_for + w × White  "
            f"= {sf_now:.2f} + {eff_w:.2f} × {u_now:.2f}  = **{derived_pos:.3f}**"
        )
        st.markdown(
            "This is the per-element point estimate that enters the P(G, Classic) product. "
            "The Italian Flag provides the reasoning; the Policy P is the number that "
            "propagates upward."
        )
        if sa_now > 0.15 and eff_w > 0.4:
            st.warning(
                f"You have {sa_now*100:.0f}% Support Against — active negative evidence. "
                f"Your w = {eff_w:.2f} still counts the white space optimistically. "
                f"Consider reducing w to {max(0.1, eff_w - 0.2):.2f} or lower, "
                "or document why the white space is expected to resolve favourably."
            )
        st.info(
            "**Converting a single probability to ESL:** "
            "Start with your best estimate P. Set S_for ≈ P, S_against ≈ 0 if no counter-evidence, "
            "or S_against > 0 if you have data pointing against. The remainder is white space. "
            "Policy P = S_for + w × White will reproduce your P at w = (P − S_for) / White."
        )

    st.divider()
    # Bottom Apply/Cancel repeat for convenience
    bot_apply, bot_cancel, _ = st.columns([1, 1, 6])
    with bot_apply:
        st.button("✔ Apply", key=f"cam_apply_bot_{key_prefix}", type="primary",
                  on_click=_on_apply)
    with bot_cancel:
        st.button("✖ Cancel", key=f"cam_cancel_bot_{key_prefix}",
                  on_click=_on_cancel)
