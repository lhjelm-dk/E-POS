"""Pure / semi-pure rendering and calculation helpers.

Extracted from app.py so that tab modules can import them without
creating a circular-import cycle.  app.py re-imports everything from here
so existing call-sites inside app.py continue to work.
"""
from __future__ import annotations

import numpy as np
import streamlit as st

from components.colors import (
    PILLAR_COLORS as CAT_COLORS,
    PILLAR_COLORS_COND as CAT_COLORS_COND,
    bar_color_for_label,
    COMPANY_DEFAULT_WEIGHT,
)
from logic.esl_logic import apply_product_logic
from logic.esl_pipeline import group_by_label, combine_with_mode
# policy_pos is re-exported from its single source of truth (logic.pos_policy) so
# existing `from components.render_helpers import policy_pos` call-sites keep working.
from logic.pos_policy import policy_pos  # noqa: F401 — re-export
from logic.session_keys import SK


# ---------------------------------------------------------------------------
# Core flag calculation
# ---------------------------------------------------------------------------

def calculate_flag(s_for: float, s_against: float) -> tuple[float, float, float, float, bool]:
    green = max(0.0, min(1.0, float(s_for)))
    red = max(0.0, min(1.0, float(s_against)))
    overlap = max(0.0, green + red - 1.0)
    white = max(0.0, 1.0 - green - red + overlap)
    conflict = overlap > 0
    return green, white, red, overlap, conflict


# ---------------------------------------------------------------------------
# Italian-flag rendering
# ---------------------------------------------------------------------------

def render_flag(
    s_for: float,
    s_against: float,
    marker: float | None = None,
    category: str | None = None,
) -> None:
    green, white, red, overlap, conflict = calculate_flag(s_for, s_against)
    marker_html = ""
    if marker is not None:
        marker = min(max(marker, 0.0), 1.0)
        marker_html = f'<div class="flag-marker" style="left: {marker * 100:.1f}%"></div>'
    green_non = max(0.0, green - overlap)
    red_non = max(0.0, red - overlap)
    html = f"""
    <div class="flag-container">
        <div class="flag-green" style="width: {green_non * 100:.1f}%"></div>
        <div class="flag-white" style="width: {white * 100:.1f}%"></div>
        <div class="flag-yellow" style="width: {overlap * 100:.1f}%"></div>
        <div class="flag-red" style="width: {red_non * 100:.1f}%"></div>
        {marker_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
    if conflict:
        cat_specific = {
            "Charge": "Common cause: seismic amplitude supports reservoir/charge but nearby well shows no pay. Document both and note which evidence is more proximal to this specific closure.",
            "Closure": "Common cause: seismic confirms structure but fault interpretation is ambiguous. Is the conflict about trap existence or seal?",
            "Reservoir": "Common cause: core shows good porosity but log interpretation suggests net-to-gross issues. Which data source is more reliable?",
            "Retention": "Common cause: top seal looks good but fault reactivation history is uncertain. Have you checked for palaeo-oil staining in analogues?",
        }.get(category or "", "Review evidence notes and identify the source of contradiction.")
        st.markdown(
            f'<div class="conflict-warning">⚠️ OVERCOMMITTED — {cat_specific}</div>',
            unsafe_allow_html=True,
        )


def _calibration_tier(pos: float) -> tuple[str, str]:
    """Return (tier_text, color) for Policy P calibration guidance."""
    if pos >= 0.85:
        return "EXCEPTIONAL evidence required to justify this score", "#DC2626"
    if pos >= 0.70:
        return "Strong analogue support needed", "#D97706"
    if pos >= 0.50:
        return "Reasonable evidence basis", "#2563EB"
    if pos >= 0.30:
        return "Speculative — document carefully", "#7C3AED"
    return "Very high risk — show-stopper candidate", "#DC2626"


def render_flag_stats(s_for: float, s_against: float, uncertainty_weight: float = 0.5) -> None:
    green, white, red, overlap, conflict = calculate_flag(s_for, s_against)
    lower = green
    upper = 1 - red
    estimated_pos = green + uncertainty_weight * white
    ratio = max(green, 0.01) / max(red, 0.01)
    text = f"Bel–Pl: {lower * 100:.1f}%–{upper * 100:.1f}% | White: {white * 100:.1f}%"
    text += f" | ESL ratio: {ratio:.2f}"
    if overlap > 0:
        text += f" | Overlap: {overlap * 100:.1f}%"
    text += f" | Policy P: {estimated_pos * 100:.1f}%"
    st.caption(text)
    tier_text, tier_color = _calibration_tier(estimated_pos)
    st.markdown(
        f'<span style="color:{tier_color}; font-size:0.8rem; font-weight:600;">{tier_text}</span>',
        unsafe_allow_html=True,
    )


def small_flag_html(s_for: float, s_against: float) -> str:
    green, white, red, overlap, _ = calculate_flag(s_for, s_against)
    green_non = max(0.0, green - overlap)
    red_non = max(0.0, red - overlap)
    return (
        "<div class='flag-container' style='height: 14px; width: 140px;'>"
        f"<div class='flag-green' style='width: {green_non * 100:.1f}%'></div>"
        f"<div class='flag-white' style='width: {white * 100:.1f}%'></div>"
        f"<div class='flag-yellow' style='width: {overlap * 100:.1f}%'></div>"
        f"<div class='flag-red' style='width: {red_non * 100:.1f}%'></div>"
        "</div>"
    )


def interval_text(s_for: float, s_against: float) -> str:
    lower = s_for * 100
    upper = (1 - s_against) * 100
    return f"{lower:.0f}–{upper:.0f}%"


# ---------------------------------------------------------------------------
# Hierarchy / summary rendering
# ---------------------------------------------------------------------------

def render_hierarchy_path(path: list[str]) -> None:
    """Display breadcrumb-style path (e.g., Total > Play > Charge > Migration Path)."""
    if not path:
        return
    breadcrumb = " > ".join(path)
    st.markdown(f'<div class="hierarchy-path">{breadcrumb}</div>', unsafe_allow_html=True)


def _operator_badge_class(operator: str) -> str:
    if not operator:
        return ""
    if "Product" in operator or "product" in operator:
        return "badge-pi"
    if "ANY" in operator or "max" in operator.lower():
        return "badge-any"
    if "ALL" in operator or "min" in operator.lower():
        return "badge-all"
    if "IPT" in operator or "DEP" in operator:
        return "badge-ipt"
    return "badge-all"


def render_summary(
    title: str,
    s_for: float,
    s_against: float,
    level: int = 0,
    operator: str | None = None,
    dependency: float | None = None,
    uncertainty_weight: float = 0.5,
    path: list[str] | None = None,
    category: str | None = None,
    scope: str = "play",
) -> None:
    if level > 0:
        _, col = st.columns([level, 12])
    else:
        col = st.container()
    with col:
        if path:
            render_hierarchy_path(path)
        badge = f' <span class="{_operator_badge_class(operator or "")}">{operator}</span>' if operator else ""
        css_class = f"title-level-{min(level, 2)}"
        if category and category in CAT_COLORS:
            css_class += f" title-{category}" + ("-cond" if scope == "cond" else "")
        st.markdown(f'<div class="{css_class}">{title}{badge}</div>', unsafe_allow_html=True)
        if operator and dependency is not None and operator.startswith("ESL-IPT"):
            st.caption(f"Dependency: {dependency:.2f}")
        est_pos = policy_pos(s_for, s_against, uncertainty_weight)
        render_flag(s_for, s_against, marker=est_pos, category=category)
        render_flag_stats(s_for, s_against, uncertainty_weight)


# ---------------------------------------------------------------------------
# ESL ratio / geometry helpers
# ---------------------------------------------------------------------------

def ratio_xy(s_for: float, s_against: float) -> tuple[float, float]:
    """Convert (support_for, support_against) to (X, ratio) for the ESL plot."""
    f = float(s_for)
    a = float(s_against)
    u = 1 - f - a
    c = f + a - 1
    x = 100 * u if u >= 0 else -100 * c
    r = max(f, 0.01) / max(a, 0.01)
    r = min(r, 100.0)
    return x, r


def point_in_poly(x: float, y: float, poly_x: list[float], poly_y: list[float]) -> bool:
    """Ray-casting point-in-polygon test."""
    inside = False
    n = len(poly_x)
    j = n - 1
    for i in range(n):
        xi, yi = poly_x[i], poly_y[i]
        xj, yj = poly_x[j], poly_y[j]
        intersect = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def classify_esl_region_by_curves(x: float, y: float) -> int:
    """Classify (X, Y) into one of 8 ESL regions."""
    if y > 1:
        if x < 0:
            x_bound = 50 * (1 - y)
            return 1 if x <= x_bound else 2
        else:
            x_bound = 50 * (1 - 1 / y)
            return 4 if x >= x_bound else 3
    if y < 1:
        if x < 0:
            x_bound = 50 * (1 - 1 / y)
            return 5 if x <= x_bound else 6
        else:
            x_bound = 50 * (1 - y)
            return 8 if x >= x_bound else 7
    return 3 if x >= 0 else 2


def _assign_label_positions(
    all_points: list[tuple[float, float, str]],
    proximity_threshold: float = 0.6,
) -> tuple[list[str], list[float]]:
    """Assign textposition to each point to reduce label overlap."""
    TEXT_POSITIONS = [
        "top center",
        "bottom center",
        "top left",
        "bottom right",
        "top right",
        "bottom left",
        "middle left",
        "middle right",
    ]
    n = len(all_points)
    positions = ["top center"] * n
    crowding = [1.0] * n

    def dist(i, j):
        xi, yi, _ = all_points[i]
        xj, yj, _ = all_points[j]
        dx = (xi - xj) / 100.0
        lyi = np.log10(max(yi, 0.01))
        lyj = np.log10(max(yj, 0.01))
        return np.sqrt(dx * dx + (lyi - lyj) ** 2)

    for i in range(n):
        neighbor_count = 0
        used_by_nearby = set()
        for j in range(n):
            if i != j and dist(i, j) < proximity_threshold:
                neighbor_count += 1
                used_by_nearby.add(positions[j])
        crowding[i] = 1.0 + 0.3 * min(neighbor_count, 6)
        for pos in TEXT_POSITIONS:
            if pos not in used_by_nearby:
                positions[i] = pos
                break
    return positions, crowding


# ---------------------------------------------------------------------------
# POS computation helpers
# ---------------------------------------------------------------------------

def _compute_total_pos_from_pillars(
    play_vals: dict[str, tuple[float, float]],
    cond_vals: dict[str, tuple[float, float]],
    uncertainty_weight: float,
) -> float:
    """Compute total POS from pillar (for, against) dicts using product logic."""
    play_nodes = [{"support_for": f, "support_against": a} for f, a in play_vals.values()]
    cond_nodes = [{"support_for": f, "support_against": a} for f, a in cond_vals.values()]
    pf, pa = apply_product_logic(play_nodes)
    cf, ca = apply_product_logic(cond_nodes)
    tf, ta = apply_product_logic([
        {"support_for": pf, "support_against": pa},
        {"support_for": cf, "support_against": ca},
    ])
    return policy_pos(tf, ta, uncertainty_weight)


def _compute_cond_results_with_override(
    conditional: dict,
    override: dict[tuple[str, int], tuple[float, float]],
    get_mode,
    get_dependency,
    combine_with_mode_fn,
) -> dict[str, dict[str, float]]:
    """Recompute conditional_results with one element overridden."""
    results = {}
    for category, elements in conditional.items():
        grouped = group_by_label(elements)
        group_results = []
        for group_label, group_elements in grouped.items():
            if len(group_elements) == 1:
                e = group_elements[0]
                try:
                    idx = elements.index(e)
                except ValueError:
                    idx = -1
                key = (category, idx)
                f, a = override.get(key, (float(e["support_for"]), float(e["support_against"])))
                group_results.append({"support_for": f, "support_against": a})
            else:
                nodes = []
                for e in group_elements:
                    try:
                        idx = elements.index(e)
                    except ValueError:
                        idx = -1
                    key = (category, idx)
                    f, a = override.get(key, (float(e["support_for"]), float(e["support_against"])))
                    nodes.append({
                        "support_for": f, "support_against": a,
                        "suff_for": e.get("suff_for", 1.0), "suff_against": e.get("suff_against", 1.0),
                    })
                gf, ga = combine_with_mode_fn(
                    nodes,
                    get_mode(SK.esl_group_mode(category, group_label)),
                    get_dependency(SK.esl_group_dependency(category, group_label)),
                )
                group_results.append({"support_for": gf, "support_against": ga})
        cf, ca = combine_with_mode_fn(
            group_results,
            get_mode(SK.esl_mode(category)),
            get_dependency(SK.esl_dependency(category)),
        )
        results[category] = {"for": cf, "against": ca}
    return results


# ---------------------------------------------------------------------------
# Miscellaneous helpers
# ---------------------------------------------------------------------------

def _rose_to_esl_guidance(element_label: str, category: str) -> str:
    """Return markdown text explaining how to convert a single probability to ESL."""
    return (
        "**Converting from a single probability to ESL:**\n\n"
        "1. **Start with your best estimate** of this element succeeding (e.g. from analogues, calibration).\n\n"
        "2. **Split into For and Against:**\n"
        "   - *What fraction of evidence actively supports success?* → S_for\n"
        "   - *What fraction actively points to failure?* → S_against\n"
        "   - The remainder is white space (uncommitted evidence, data gaps).\n\n"
        "3. **Policy P** = S_for + w × White. If you have no counter-evidence, set S_for = your probability, "
        "S_against = 0. If you have counter-evidence, set S_against > 0 — your Policy P will decrease accordingly."
    )
