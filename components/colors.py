"""Shared color theme for risk elements — used in overview tables and tornado charts."""

# Re-export so callers that used to import COMPANY_DEFAULT_WEIGHT from here still work.
from logic.pos_policy import COMPANY_DEFAULT_WEIGHT as COMPANY_DEFAULT_WEIGHT  # noqa: F401

PILLAR_COLORS = {
    "Charge": "#F69292",
    "Closure": "#8CB7FC",
    "Reservoir": "#FFD44B",
    "Retention": "#B5E6A2",
}


def lighten_hex(hex_color: str, factor: float = 0.5) -> str:
    """Lighten a hex color toward white by *factor* ∈ [0, 1]."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return f"#{hex_color}"
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


# ── Shared Probability (CoS) colour scale ───────────────────────────────────
# Single source of truth for the probability→colour mapping used across the app:
# reference tables, DFI characteristic radar, adequacy matrix, Risking-V
# schematic — anything that calls cos_color()/COS_SCALE adjusts when this changes.
# Intervals are SYMMETRIC about 50% (0–10 / 10–25 / 25–40 / 40–60 / 60–75 /
# 75–90 / 90–100); the 7 colours and verbal labels are retained.
COS_SCALE: list[tuple[float, float, str, str]] = [
    (0.90, 1.00, "#1A7A4A", "Very High (90–100%)"),
    (0.75, 0.90, "#70AD47", "High (75–90%)"),
    (0.60, 0.75, "#A9D18E", "Moderately High (60–75%)"),
    (0.40, 0.60, "#FFD966", "Moderate (40–60%)"),
    (0.25, 0.40, "#F4B942", "Moderately Low (25–40%)"),
    (0.10, 0.25, "#E2603A", "Low (10–25%)"),
    (0.00, 0.10, "#C00000", "Very Low (0–10%)"),
]


def cos_color(value: float) -> str:
    """Return the hex colour for a probability ``value`` ∈ [0, 1] on the shared
    CoS scale. Out-of-range values clamp to the nearest band; non-finite → grey."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "#9CA3AF"
    if v != v:  # NaN
        return "#9CA3AF"
    v = max(0.0, min(1.0, v))
    for lo, hi, col, _ in COS_SCALE:
        if lo <= v <= hi:
            return col
    return "#9CA3AF"


# Keep the private alias so existing internal callers (`PILLAR_COLORS_COND`) still work.
_lighten_hex = lighten_hex


PILLAR_COLORS_COND = {k: _lighten_hex(v, 0.45) for k, v in PILLAR_COLORS.items()}

def bar_color_for_label(label: str) -> str:
    """Return pillar color for a tornado/sensitivity bar label.

    Recognised formats:
      'Charge (Play)'                     → play-level pillar colour (solid)
      'Closure (Cond)'                    → cond-level pillar colour (light)
      'Charge / Migration Path: ...'      → cond element, pillar prefix before ' / '
      'X — Y (Reservoir)'                 → pillar name in parentheses
    """
    if " (Play)" in label:
        base = label.split(" (Play)")[0].strip()
        return PILLAR_COLORS.get(base, "#6b7280")
    if " (Cond)" in label:
        base = label.split(" (Cond)")[0].strip()
        return PILLAR_COLORS_COND.get(base, "#9ca3af")
    # Conditional element labels: "PillarName / GroupLabel: ..." — pillar is before first ' / '
    if " / " in label:
        base = label.split(" / ")[0].strip()
        col = PILLAR_COLORS_COND.get(base)
        if col:
            return col
    # Legacy: pillar name in trailing parentheses
    if " (" in label:
        cat = label.split(" (")[-1].rstrip(")")
        col = PILLAR_COLORS_COND.get(cat)
        if col:
            return col
    return "#6b7280"
