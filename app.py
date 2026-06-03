from __future__ import annotations

import csv
import datetime
import io
import json
import numpy as np
import streamlit as st
import plotly.graph_objects as go

from logic.esl_logic import apply_and_logic, apply_product_logic, calculate_uncertainty
from logic.esl_pipeline import (
    DEFAULT_ESL_MODE,
    DEFAULT_CLASSIC_POS_MODE,
    ESL_MODE_OPTIONS,
    combine_with_mode,
    combine_classic_pos,
    compute_esl_rollup,
    group_by_label,
    make_session_mode_dep_getters,
    make_session_classic_mode_getter,
)
from components.overview_table import render_overview_table
from components.element_detail_cam import (
    render_element_cam_panel,
    render_compact_element_row,
    close_active_cam,
    open_element_cam,
)
from data.prospect_schema import (
    ProspectData,
    load_prospect,
    save_prospect,
    list_prospects,
    PROSPECTS_DIR,
)


def _prospect_to_csv_string(data: ProspectData) -> str:
    """Serialize ProspectData to CSV string for download."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["# E-POS Prospect", data.title, data.analyst, data.basin, data.date, data.version])
    w.writerow(["# ESL play", json.dumps(data.play, default=str)])
    w.writerow(["# ESL conditional", json.dumps(data.conditional, default=str)])
    w.writerow(["# Classic POS", data.classic_charge, data.classic_closure, data.classic_reservoir, data.classic_retention])
    w.writerow(["model", "pillar", "sub_element", "success_criteria", "p_success", "support_against", "evidence_for", "evidence_against", "uncertainty_note"])
    for pillar, el in (data.play or {}).items():
        if isinstance(el, dict) and "support_for" in el:
            w.writerow(["esl", pillar, "", el.get("success_criteria", ""), el.get("support_for", 0.5), el.get("support_against", 0.1), el.get("evidence_for", ""), el.get("evidence_against", ""), el.get("uncertainty_note", "")])
    for pillar, elements in (data.conditional or {}).items():
        for elem in elements if isinstance(elements, list) else []:
            if isinstance(elem, dict):
                w.writerow(["esl", pillar, elem.get("label", ""), elem.get("success_criteria", ""), elem.get("support_for", 0.5), elem.get("support_against", 0.1), elem.get("evidence_for", ""), elem.get("evidence_against", ""), elem.get("uncertainty_note", "")])
    return buf.getvalue()


st.set_page_config(page_title="E-POS — Evidence supported probability of success", layout="wide", initial_sidebar_state="collapsed")

# Category color theme: Play level (darker) and Cond level (lighter, same tone)
from components.colors import (
    PILLAR_COLORS as CAT_COLORS,
    PILLAR_COLORS_COND as CAT_COLORS_COND,
    bar_color_for_label,
    lighten_hex,
    COMPANY_DEFAULT_WEIGHT,  # single source — defined in logic/pos_policy.py
)

# ── Imports from extracted helper modules ────────────────────────────────────
from components.render_helpers import (
    calculate_flag,
    policy_pos,
    render_flag,
    _calibration_tier,
    render_flag_stats,
    small_flag_html,
    interval_text,
    render_hierarchy_path,
    _operator_badge_class,
    render_summary,
    _rose_to_esl_guidance,
    ratio_xy,
    point_in_poly,
    classify_esl_region_by_curves,
    _assign_label_positions,
    _compute_total_pos_from_pillars,
    _compute_cond_results_with_override,
)
from components.esl_analysis import (
    render_sensitivity_analysis,
    _render_esl_ratio_plot_and_validation,
    _render_cam_scatter_plot,
)
from components.prospect_hub import (
    _compute_esl_for_hub as _compute_esl_for_hub_impl,
    _compute_classic_pos_for_hub,
    _get_esl_overview_data,
    build_logic_table,
    build_prospect_risk_data,
    _build_full_export_csv,
    _parse_csv_sections,
)
from components.tabs.tab_dashboard import _render_dashboard_tab
from components.tabs.tab_play import _render_play_tab
from components.tabs.tab_conditional import _render_conditional_tab
from components.tabs.tab_analysis import _render_analysis_tab
from components.tabs.tab_dfi import _render_dfi_tab, _render_final_pos_tab
from components.tabs.tab_theory import _render_theory_tab
from components.tabs.tab_reference import _render_reference_tab

st.markdown(
    """
    <style>
    /* Hide sidebar - content moved to main */
    [data-testid="stSidebar"] { display: none; }
    [data-testid="stSidebar"] + div { margin-left: 0 !important; }
    .flag-container {
        display: flex;
        height: 22px;
        width: 100%;
        border: 1px solid #444;
        border-radius: 4px;
        overflow: hidden;
        position: relative;
    }
    .flag-green { background-color: #2e9d5b; height: 100%; }
    .flag-white { background-color: #f5f5f5; height: 100%; }
    .flag-red { background-color: #d64545; height: 100%; }
    .flag-yellow { background-color: #f6c343; height: 100%; }
    .flag-marker {
        position: absolute;
        top: -2px;
        bottom: -2px;
        width: 2px;
        background: #1f2937;
        opacity: 0.85;
    }
    .conflict-warning {
        color: #ffffff;
        background: #b45309;
        font-weight: 700;
        font-size: 0.85em;
        margin-top: 6px;
        padding: 4px 8px;
        border-radius: 4px;
        border-left: 4px solid #7c2d12;
    }
    .title-level-0 {
        font-size: 1.5rem;
        font-weight: 700;
        background: #1f2937;
        color: white;
        padding: 0.5rem 0.75rem;
        border-radius: 4px;
        margin: 0.5rem 0;
    }
    .title-Charge { background: #F69292 !important; color: #1f2937 !important; padding: 0.5rem 0.75rem !important; border-radius: 4px !important; }
    .title-Closure { background: #8CB7FC !important; color: #1f2937 !important; padding: 0.5rem 0.75rem !important; border-radius: 4px !important; }
    .title-Reservoir { background: #FFD44B !important; color: #1f2937 !important; padding: 0.5rem 0.75rem !important; border-radius: 4px !important; }
    .title-Retention { background: #B5E6A2 !important; color: #1f2937 !important; padding: 0.5rem 0.75rem !important; border-radius: 4px !important; }
    .title-Charge-cond { background: #facbcb !important; color: #1f2937 !important; padding: 0.5rem 0.75rem !important; border-radius: 4px !important; }
    .title-Closure-cond { background: #bfd7fd !important; color: #1f2937 !important; padding: 0.5rem 0.75rem !important; border-radius: 4px !important; }
    .title-Reservoir-cond { background: #ffe79c !important; color: #1f2937 !important; padding: 0.5rem 0.75rem !important; border-radius: 4px !important; }
    .title-Retention-cond { background: #d6f1cc !important; color: #1f2937 !important; padding: 0.5rem 0.75rem !important; border-radius: 4px !important; }
    .title-level-1 {
        font-size: 1.1rem;
        font-weight: 600;
        border-left: 4px solid #2563eb;
        padding-left: 0.75rem;
        margin: 0.4rem 0;
    }
    .title-level-2 {
        font-size: 0.9rem;
        font-variant: small-caps;
        color: #6b7280;
        margin-left: 1rem;
        margin: 0.3rem 0;
    }
    .hierarchy-path {
        font-size: 0.85rem;
        color: #6b7280;
        margin-bottom: 0.5rem;
    }
    .hierarchy-path span { color: #9ca3af; }
    .badge-any { background: #22c55e; color: white; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.75rem; }
    .badge-all { background: #2563eb; color: white; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.75rem; }
    .badge-ipt { background: #f97316; color: white; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.75rem; }
    .badge-pi { background: #7c3aed; color: white; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.75rem; }
    .badge-and { background: #2563eb; color: white; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.75rem; }
    .pillar-header { font-size: 1.25rem; font-weight: 700; background: #1f2937; color: white; padding: 10px 12px; border-radius: 5px; margin: 0.5rem 0; }
    .sub-element-row { border-left: 4px solid #2e9d5b; padding-left: 15px; margin-bottom: 10px; }

    /* ── Prominent tab bar ───────────────────────────────────────────────── */
    [data-testid="stTabs"] [role="tablist"] {
        gap: 4px;
        border-bottom: 2px solid #d1d5db;
        padding-bottom: 2px;
    }
    [data-testid="stTabs"] button[role="tab"] {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        padding: 8px 18px !important;
        border-radius: 6px 6px 0 0 !important;
        border: 1.5px solid #d1d5db !important;
        border-bottom: none !important;
        background: #f3f4f6 !important;
        color: #374151 !important;
    }
    [data-testid="stTabs"] button[role="tab"]:hover {
        background: #e5e7eb !important;
        color: #111827 !important;
    }
    [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        background: #1e3a5f !important;
        color: #ffffff !important;
        border-color: #1e3a5f !important;
        box-shadow: 0 -2px 6px rgba(30,58,95,0.20);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# render_flag, calculate_flag, policy_pos, and all other helpers are imported
# from components.render_helpers, components.esl_analysis, and components.prospect_hub
# at the top of this file.  The original definitions have been moved there.


def build_models() -> dict:
    def node(
        label: str,
        success_criteria: str,
        support_for: float = 0.5,
        support_against: float = 0.1,
        suff_for: float = 1.0,
        suff_against: float = 1.0,
    ) -> dict:
        return {
            "label": label,
            "success_criteria": success_criteria,
            "support_for": support_for,
            "support_against": support_against,
            "uncertainty": max(0.0, 1.0 - support_for - support_against),
            "suff_for": suff_for,
            "suff_against": suff_against,
            "evidence_for": "",
            "evidence_against": "",
            "uncertainty_note": "",
        }

    play = {
        "Charge": {
            "label": "Charge",
            "description": _PLAY_GUIDANCE["Charge"]["description"],
            "considerations": _PLAY_GUIDANCE["Charge"]["considerations"],
            "support_for": 0.9,   # updated default
            "support_against": 0.1,
            "success_criteria": "",
            "evidence_for": "",
            "evidence_against": "",
            "uncertainty_note": "",
            "suff_for": 1.0,
            "suff_against": 1.0,
        },
        "Closure": {
            "label": "Closure",
            "description": _PLAY_GUIDANCE["Closure"]["description"],
            "considerations": _PLAY_GUIDANCE["Closure"]["considerations"],
            "support_for": 1.0,   # updated default
            "support_against": 0.0,
            "success_criteria": "",
            "evidence_for": "",
            "evidence_against": "",
            "uncertainty_note": "",
            "suff_for": 1.0,
            "suff_against": 1.0,
        },
        "Reservoir": {
            "label": "Reservoir",
            "description": _PLAY_GUIDANCE["Reservoir"]["description"],
            "considerations": _PLAY_GUIDANCE["Reservoir"]["considerations"],
            "support_for": 0.7,   # updated default
            "support_against": 0.1,
            "success_criteria": "",
            "evidence_for": "",
            "evidence_against": "",
            "uncertainty_note": "",
            "suff_for": 1.0,
            "suff_against": 1.0,
        },
        "Retention": {
            "label": "Retention",
            "description": _PLAY_GUIDANCE["Retention"]["description"],
            "considerations": _PLAY_GUIDANCE["Retention"]["considerations"],
            "support_for": 0.8,   # updated default
            "support_against": 0.1,
            "success_criteria": "",
            "evidence_for": "",
            "evidence_against": "",
            "uncertainty_note": "",
            "suff_for": 1.0,
            "suff_against": 1.0,
        },
    }

    conditional = {
        # ── CHARGE ────────────────────────────────────────────────────────────────
        # Group "Migration pathway": prospect location relative to fairway and carrier geometry
        # Group "Fill adequacy":     source volume sufficient to charge trap to threshold
        # Group "Source / HC phase": source rock maturity and fluid-phase match
        "Charge": [
            node(
                "Migration pathway",
                "Within distance of confirmed / inferred kitchen: "
                "prospect is inside the drainage area and migration fairway",
                0.70, 0.00,
            ),
            node(
                "Migration pathway",
                "Presence of carrier beds: unobstructed sandstone, unconformity, or fault plane "
                "connects fairway to the base of this closure",
                0.60, 0.20,
            ),
            node(
                "Migration pathway",
                "Absence of thief beds: no high-permeability intercalations or fault conduits "
                "that would divert charge away from the trap",
                0.80, 0.00,
            ),
            node(
                "Fill adequacy",
                "Sufficient to fill P99 EUR: source volume and expulsion efficiency sufficient "
                "to fill the closure to at least the P99 recoverable EUR threshold",
                0.90, 0.00,
            ),
            node(
                "Fill adequacy",
                ">P90 within trap: charge sufficient to fill the trap to >P90 gross rock volume "
                "at expected saturation",
                0.80, 0.00,
            ),
            node(
                "Fill adequacy",
                "Sufficient to fill P90 EUR: source volume supports the P90 commercial threshold "
                "given expected expulsion efficiency and migration losses",
                0.90, 0.00,
            ),
            node(
                "Source / HC phase",
                "Supports given HC phase (presence): source rock type and maturity consistent "
                "with expected fluid phase (oil, condensate, or dry gas)",
                0.70, 0.10,
            ),
            node(
                "Source / HC phase",
                "Supports given HC phase (adequacy): predicted GOR and API gravity adequate for "
                "commercial targets; fluid contacts predictable",
                0.80, 0.10,
            ),
            node(
                "Source / HC phase",
                "Maturity level supports the given phase: burial history and present-day Ro "
                "consistent with oil or gas window as appropriate; no over-maturation risk",
                0.80, 0.10,
            ),
        ],
        # ── CLOSURE ──────────────────────────────────────────────────────────────
        # Group "Trap timing":    reservoir / trap geometry in place before migration
        # Group "Closure geometry": valid geometry with adequate volume at migration time
        "Closure": [
            node(
                "Trap timing",
                "Poro/perm >P90 before time of HC-entry: reservoir quality adequate at the "
                "time hydrocarbons entered the trap (pre-diagenesis, pre-cementation risk)",
                1.00, 0.00,
            ),
            node(
                "Trap timing",
                "A Trap containing P99 EUR is formed before migration terminates: "
                "closure geometry and volume were established before or during the main "
                "migration phase; late-stage trap formation would preclude charge",
                1.00, 0.00,
            ),
            node(
                "Closure geometry",
                "Structural confidence in a valid geometry at correct stratigraphic level: "
                "depth-converted 3D seismic or equivalent confirms valid 4-way, 3-way, "
                "or stratigraphic closure at the target level",
                0.70, 0.10,
            ),
            node(
                "Closure geometry",
                "Given presence, the trap can hold >P99 EUR: closure volume and spill-point "
                "geometry sufficient to contain the maximum expected recoverable volume",
                1.00, 0.00,
            ),
        ],
        # ── RESERVOIR ────────────────────────────────────────────────────────────
        # Group "Reservoir rock presence/capacity": thickness and areal extent
        # Group "Reservoir effectiveness":          quality, drive, and deliverability
        "Reservoir": [
            node("Reservoir rock presence/capacity", "Detectable Thickness (>P90): net reservoir thickness exceeds P90 minimum for commercial flow", 0.90, 0.00),
            node("Reservoir rock presence/capacity", "Extent across trap min. area: reservoir facies proven or predicted to cover the full trap area at P90", 1.00, 0.00),
            node("Reservoir effectiveness", "Porosity >P90: effective porosity exceeds P90 threshold; adequate pore volume for commercial EUR", 1.00, 0.00),
            node("Reservoir effectiveness", "Permeability >P90: permeability adequate for commercial flow rates at P90 well spacing", 0.70, 0.10),
            node("Reservoir effectiveness", "N/G - facies: net-to-gross and facies architecture adequate at P90; compartmentalization risk manageable", 0.90, 0.00),
            node("Reservoir effectiveness", "Drive mechanism: primary drive (aquifer, gas cap, solution gas) adequate to deliver P90 EUR recovery factor", 0.80, 0.30),
        ],
        # ── RETENTION ────────────────────────────────────────────────────────────
        # Group "Seal effectiveness":                 capacity, integrity, continuity of all seal elements
        # Group "Preservation from subsequent spillage": post-charge structural stability
        # Group "Preservation from degradation":      thermal, oxidation, bacterial
        "Retention": [
            node("Seal effectiveness", "Top Seal Capacity: lithology (shale / evaporite / tight carbonate) adequate; capillary entry pressure sufficient to hold P90 HC column", 0.90, 0.00),
            node("Seal effectiveness", "Absence of open fractures: no open-fracture network that would bypass seal capillary threshold; fractures healed or mineralized", 1.00, 0.00),
            node("Seal effectiveness", "Continuity: top seal laterally persistent across full closure area; no erosional windows, pinch-outs, or facies changes", 1.00, 0.00),
            node("Seal effectiveness", "Base seal capacity: basal seal adequate where underlying permeable units exist; prevents downward HC migration", 1.00, 0.00),
            node("Seal effectiveness", "Lateral seal Capacity: updip stratigraphic or fault seal adequate; no spill at P90 column height", 0.70, 0.30),
            node("Seal effectiveness", "Cross Fault seal Capacity: across-fault juxtaposition and clay smear adequate; SGR sufficient for expected column", 1.00, 0.00),
            node("Preservation from subsequent spillage", "By tilt and spill: no post-charge tilting (isostatic rebound, inversion) that would move spill point below HC contact", 1.00, 0.00),
            node("Preservation from subsequent spillage", "By seal breaching and fault leakage: no fault reactivation or seal breach since HC charge; current stress regime not critical", 1.00, 0.00),
            node("Preservation from subsequent spillage", "By Flushing / Depletion: no hydrodynamic flushing by meteoric water or pressure depletion pathway", 1.00, 0.00),
            node("Preservation from degradation", "Thermal: no thermal cracking (over-maturation); reservoir temperature history does not exceed cracking window for expected HC phase", 0.80, 0.00),
            node("Preservation from degradation", "Oxidation: no significant oxidative degradation along shallow migration pathways or at outcrop-connected carrier beds", 0.80, 0.00),
            node("Preservation from degradation", "Bacterial: no significant biodegradation risk; reservoir temperature >80°C or meteoric water recharge absent", 0.80, 0.10),
        ],
    }

    return {"play": play, "conditional": conditional}


from data.risk_model import (
    build_runtime_models as _build_rt_models,
    ensure_default_model as _ensure_default_model,
    initialize_operators_from_model as _init_operators,
    initialize_classic_operators_from_model as _init_classic_operators,
    _PLAY_GUIDANCE,
)
from components.model_builder import render_model_section

if "active_risk_model" not in st.session_state:
    try:
        _default_model = _ensure_default_model()
        st.session_state["active_risk_model"] = _default_model
    except FileNotFoundError:
        pass  # Fall through to build_models() below

if "models" not in st.session_state:
    _am = st.session_state.get("active_risk_model")
    if _am is not None:
        st.session_state["models"] = _build_rt_models(_am)
        _init_operators(_am, st.session_state)
        _init_classic_operators(_am, st.session_state)
    else:
        st.session_state["models"] = build_models()

models = st.session_state["models"]


def _migrate_play_to_direct(play: dict) -> None:
    """Migrate old play structure (sub-elements) to new direct structure (4 elements only)."""
    if "considerations" in play.get("Charge", {}):
        return  # Already migrated
    from logic.esl_logic import apply_and_logic
    new_play = build_models()["play"]
    for cat in ["Charge", "Closure", "Reservoir", "Retention"]:
        old = play.get(cat, {})
        if "lateral_migration" in old:
            lat = old["lateral_migration"]
            verts = old.get("vertical_children", [])
            nodes = [{"support_for": lat["support_for"], "support_against": lat["support_against"]}]
            nodes.extend([{"support_for": v["support_for"], "support_against": v["support_against"]} for v in verts])
            f, a = apply_and_logic(nodes) if nodes else (0.5, 0.1)
            new_play[cat]["support_for"], new_play[cat]["support_against"] = f, a
        elif "trap_presence" in old:
            t = old["trap_presence"]
            new_play[cat]["support_for"], new_play[cat]["support_against"] = t["support_for"], t["support_against"]
        elif "children" in old:
            nodes = [{"support_for": c["support_for"], "support_against": c["support_against"]} for c in old["children"]]
            f, a = apply_and_logic(nodes) if nodes else (0.5, 0.1)
            new_play[cat]["support_for"], new_play[cat]["support_against"] = f, a
    play.clear()
    play.update(new_play)


_migrate_play_to_direct(models["play"])


def _render_prospect_hub(models: dict) -> None:
    """Render the top-of-page Prospect Hub: identity, load/save, summary, sign-off."""
    st.markdown(
        "<div style='background:linear-gradient(90deg,#0D2137 0%,#1B3A5C 100%);"
        "padding:14px 20px;border-radius:8px;margin-bottom:12px;'>"
        "<span style='color:#A8C8E8;font-size:0.85rem;font-weight:600;letter-spacing:0.08em;'>"
        "PROSPECT HUB</span></div>",
        unsafe_allow_html=True,
    )
    c_title, c_analyst, c_basin, c_date, c_ver = st.columns([3, 2, 2, 2, 2])
    with c_title:
        st.text_input("Prospect title", value="New Prospect", key="meta_title")
    with c_analyst:
        st.text_input("Analyst", value="", key="meta_analyst")
    with c_basin:
        st.text_input("Basin / Play", value="", key="meta_basin")
    with c_date:
        st.text_input("Date", value=datetime.date.today().strftime("%d. %m. %Y"), key="meta_date")
    with c_ver:
        if "meta_version" not in st.session_state:
            st.session_state["meta_version"] = datetime.datetime.utcnow().strftime("v%Y%m%d-%H%M")
        st.text_input("Version", key="meta_version")

    from data.prospect_schema import list_prospects, load_prospect, save_prospect, PROSPECTS_DIR, ProspectData

    available_files = list_prospects(PROSPECTS_DIR)
    r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns([3, 1, 1, 1, 1])
    with r2c1:
        options = ["(New prospect)"] + available_files
        selected = st.selectbox("Load saved prospect", options, key="hub_prospect_select", label_visibility="collapsed")
    with r2c2:
        if st.button("Load", key="hub_load"):
            if selected != "(New prospect)":
                data = load_prospect(PROSPECTS_DIR / selected)
                if data.play:
                    for k, v in data.play.items():
                        if isinstance(v, dict) and k in models["play"]:
                            models["play"][k].update({x: v[x] for x in ("support_for", "support_against", "evidence_for", "evidence_against", "uncertainty_note", "success_criteria") if x in v})
                if data.conditional:
                    for cat, elems in data.conditional.items():
                        if cat not in models["conditional"]:
                            continue
                        if not isinstance(elems, list):
                            continue
                        if len(elems) != len(models["conditional"][cat]):
                            st.warning(
                                f"Conditional '{cat}': saved file has {len(elems)} element(s) but "
                                f"current model has {len(models['conditional'][cat])}. "
                                "Data for this pillar was not loaded — check that the same risk model "
                                "template is active, or re-enter the values manually."
                            )
                            continue
                        for i, e in enumerate(elems):
                            if i < len(models["conditional"][cat]) and isinstance(e, dict):
                                models["conditional"][cat][i].update({x: e[x] for x in ("support_for", "support_against", "evidence_for", "evidence_against", "uncertainty_note", "success_criteria", "suff_for", "suff_against") if x in e})
                for key, attr in [("meta_title", "title"), ("meta_analyst", "analyst"), ("meta_basin", "basin"), ("meta_date", "date"), ("meta_version", "version")]:
                    if getattr(data, attr):
                        st.session_state[key] = getattr(data, attr)
                st.session_state["classic_charge"] = data.classic_charge
                st.session_state["classic_closure"] = data.classic_closure
                st.session_state["classic_reservoir"] = data.classic_reservoir
                st.session_state["classic_retention"] = data.classic_retention
                st.session_state["current_prospect_file"] = selected
                st.rerun()
    with r2c3:
        if st.button("Save", key="hub_save"):
            pd_obj = ProspectData(
                title=st.session_state.get("meta_title", ""),
                analyst=st.session_state.get("meta_analyst", ""),
                basin=st.session_state.get("meta_basin", ""),
                date=st.session_state.get("meta_date", ""),
                version=st.session_state.get("meta_version", ""),
                play=dict(models["play"]),
                conditional=dict(models["conditional"]),
                classic_charge=st.session_state.get("classic_charge", 0.5),
                classic_closure=st.session_state.get("classic_closure", 0.5),
                classic_reservoir=st.session_state.get("classic_reservoir", 0.5),
                classic_retention=st.session_state.get("classic_retention", 0.5),
            )
            path = save_prospect(pd_obj)
            st.success(f"Saved: {path.name}")
    with r2c4:
        if st.button("New", key="hub_new", help="Reset all values to blank defaults"):
            ts = datetime.datetime.utcnow().strftime("v%Y%m%d-%H%M")
            _am_new = st.session_state.get("active_risk_model")
            if _am_new is not None:
                st.session_state["models"] = _build_rt_models(_am_new)
                _init_operators(_am_new, st.session_state)
                _init_classic_operators(_am_new, st.session_state)
            else:
                st.session_state["models"] = build_models()
            for k in ["meta_title", "meta_analyst", "meta_basin"]:
                st.session_state[k] = ""
            st.session_state["meta_title"] = "New Prospect"
            st.session_state["meta_date"] = datetime.date.today().strftime("%d. %m. %Y")
            st.session_state["meta_version"] = ts
            for meth in ["Classic POS", "ESL"]:
                st.session_state.pop(f"locked_{meth}", None)
            st.session_state.pop("current_prospect_file", None)
            st.rerun()
    with r2c5:
        if st.button("Stamp", key="hub_stamp", help="Set version to current UTC timestamp"):
            st.session_state["meta_version"] = datetime.datetime.utcnow().strftime("v%Y%m%d-%H%M")
            st.rerun()

    _render_tabs(models)


import dataclasses as _dc


@_dc.dataclass
class _TabContext:
    """Shared rendering context threaded through the six tab-render functions.

    All fields are computed once in ``_render_tabs`` and passed down so each tab
    function has explicit, traceable inputs rather than closing over a single
    monolithic outer scope.
    """

    models: dict                      # {"play": …, "conditional": …}
    rollup: "object"                  # ESLRollup
    uncertainty_weight: float
    get_mode: "object"                # Callable[[str], str]
    get_dependency: "object"          # Callable[[str], float]
    prospect_title: str
    active_model: "object"            # RiskModel | None
    pillar_colors: "dict[str, str]"
    pillar_display: "dict[str, str]"
    esl_options: "list[str]"

    @property
    def play(self) -> dict:
        return self.models.get("play", {})

    @property
    def conditional(self) -> dict:
        return self.models.get("conditional", {})

    @property
    def total_for(self) -> float:
        return self.rollup.total_for

    @property
    def total_against(self) -> float:
        return self.rollup.total_against

    @property
    def play_for(self) -> float:
        return self.rollup.play_for

    @property
    def play_against(self) -> float:
        return self.rollup.play_against

    @property
    def conditional_for(self) -> float:
        return self.rollup.conditional_for

    @property
    def conditional_against(self) -> float:
        return self.rollup.conditional_against

    @property
    def conditional_results(self) -> dict:
        return self.rollup.conditional_results


def _render_tabs(models: dict) -> None:
    """Seven-tab UI orchestrator: builds _TabContext then delegates to tab functions."""
    esl_opts = list(ESL_MODE_OPTIONS)
    get_mode, get_dependency = make_session_mode_dep_getters(st.session_state)
    use_policy = st.session_state.get("use_policy_weight", True)
    uncertainty_weight = (
        COMPANY_DEFAULT_WEIGHT
        if use_policy
        else float(st.session_state.get("uncertainty_weight_slider", 0.5))
    )

    play = models["play"]
    conditional = models["conditional"]
    r = compute_esl_rollup(play, conditional, get_mode, get_dependency)

    # Persist ESL masses so the Dashboard comparison table always has current data.
    st.session_state["comparison_esl_pos"]           = policy_pos(r.total_for, r.total_against, uncertainty_weight)
    st.session_state["comparison_esl_total_for"]     = r.total_for
    st.session_state["comparison_esl_total_against"] = r.total_against

    _active_model_ref = st.session_state.get("active_risk_model")
    if _active_model_ref is not None:
        _pillar_colors  = {p.pillar_id: p.color for p in _active_model_ref.pillars}
        _pillar_display = {p.pillar_id: p.display_name for p in _active_model_ref.pillars}
    else:
        _pillar_colors  = {"Charge": "#F69292", "Closure": "#8CB7FC", "Reservoir": "#FFD44B", "Retention": "#B5E6A2"}
        _pillar_display = {"Charge": "Charge", "Closure": "Closure", "Reservoir": "Reservoir", "Retention": "Retention"}

    ctx = _TabContext(
        models=models,
        rollup=r,
        uncertainty_weight=uncertainty_weight,
        get_mode=get_mode,
        get_dependency=get_dependency,
        prospect_title=st.session_state.get("meta_title", "Prospect"),
        active_model=_active_model_ref,
        pillar_colors=_pillar_colors,
        pillar_display=_pillar_display,
        esl_options=esl_opts,
    )

    (tab_dash, tab_play, tab_cond, tab_analysis, tab_dfi, tab_final,
     tab_methods, tab_ref) = st.tabs([
        "\U0001f4ca Dashboard",
        "\U0001f30d Play",
        "\U0001f50d Conditional",
        "\U0001f4c8 Analysis (P(G))",
        "\U0001f30a Bayesian DFI Update",
        "\U0001f4dd Final Prospect POS",
        "\U0001f4da Theory & Guide",
        "\U0001f4cb Reference Tables",
    ])

    with tab_dash:      _render_dashboard_tab(ctx)
    with tab_play:      _render_play_tab(ctx)
    with tab_cond:      _render_conditional_tab(ctx)
    with tab_analysis:  _render_analysis_tab(ctx)
    with tab_dfi:       _render_dfi_tab(ctx)
    with tab_final:     _render_final_pos_tab(ctx)
    with tab_methods:   _render_theory_tab(ctx)
    with tab_ref:       _render_reference_tab(ctx)

# ── TOP OF PAGE ─────────────────────────────────────────────────────────────────
st.title("E-POS")
st.markdown(
    """
    <div style="margin-top:-12px; margin-bottom:18px; line-height:1.6;">
        <span style="
            display: inline-flex;
            align-items: center;
            height: 14px;
            width: 36px;
            border: 1px solid #6B7280;
            border-radius: 2px;
            overflow: hidden;
            vertical-align: middle;
            margin-right: 7px;
            margin-bottom: 2px;
        ">
            <span style="width:33%;background:#2e9d5b;height:100%;display:inline-block;"></span>
            <span style="width:34%;background:#f5f5f5;height:100%;display:inline-block;"></span>
            <span style="width:33%;background:#d64545;height:100%;display:inline-block;"></span>
        </span>
        <span style="font-size:1.05rem; color:#374151; font-weight:500;">
            Evidence supported probability of success for geological prospects.
        </span>
        <br>
        <span style="font-size:0.72rem; color:#9CA3AF; font-style:italic; margin-left:44px;">
            By Lars Hjelm
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── PROSPECT HUB (metadata, Prospect Risk Data, Comparison, method tabs) ───────────
_render_prospect_hub(models)
