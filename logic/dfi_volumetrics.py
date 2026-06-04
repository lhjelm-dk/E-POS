"""DHI → volumetrics integration helpers (Monigle et al. 2025).

Risk is only half the story — Monigle 2025 stress that a DHI should also constrain
the *volume* distribution, and that the geophysically-defined volume must be joined
with the geologically/structurally-defined volume in proportion to **how much the
DHI can be trusted**. This module provides the small, citable rules from the paper
so E-POS can *recommend* how to blend the two (it is guidance, not a volumetric
Monte-Carlo engine).

Two complementary "trust" measures are surfaced in the app:

1. **DHI Volume Weight (V)** — E-POS's SAAM byproduct,
   ``V = L_success / (L_success + E[L | failure])``: the probability the observed
   DHI Index arises from a true HC (success) response rather than a failure mode.
   A calibrated 0–1 confidence in the anomaly *as a volume-defining observation*.
   Available only in the DHI-Index (SAAM) pathway.

2. **Column-height weighting (w_ch)** — Monigle 2025, Figure 8: the fraction of
   volumetric trials that should place the HC–water contact (HCWC) at the
   DHI-rated elevation, as a function of the DHI score. Available for every
   pathway (it needs only the 0–1 DHI score).

Both answer the same operational question — *what fraction of the volume
distribution should honour the DFI-defined geometry vs the geological spill
estimate?* — from different inputs, so the app shows them side by side.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Monigle 2025 empirical thresholds (Figures 8, 10; Porosity discussion p. 627).
HIGH_DHI_TRIAL_WEIGHT: float = 0.95   # DHI > 0.50 → HCWC at rated elevation 95% of trials
POROSITY_FLOOR: float = 0.14          # DHIs essentially never observed below ~14% porosity
FCR_NTG_MIN: float = 0.50             # FCR present ⇒ NTG generally > ~50% (range 40–85%)
NO_FCR_NTG_MAX: float = 0.55          # FCR absent ⇒ NTG typically ≤ ~55% (does not preclude moderate)


def column_height_weight(dhi_score: float) -> float:
    """Monigle 2025 (Fig. 8) column-height trial weight from the 0–1 DHI score.

    Returns the fraction of volumetric trials that should place the HCWC at the
    DHI-rated elevation:

        w_ch = min(0.95, 2 · DHI_score)

    i.e. a strong DHI (score > ~0.475) pins the contact at the rated elevation in
    95% of trials; a weaker DHI honours it in proportion to twice its score, the
    remainder following the geological/structural spill estimate. Clamped to [0, 0.95]
    — the paper never assigns 100% trust because the low-DHI database is thin
    (<10 weak-DHI successes drilled).
    """
    s = max(0.0, min(1.0, float(dhi_score)))
    return min(HIGH_DHI_TRIAL_WEIGHT, 2.0 * s)


@dataclass(frozen=True)
class VolumetricsRecommendation:
    """Structured DHI→volumetrics blend recommendation for one prospect."""

    dhi_score: float                      # 0–1 DHI score
    w_ch: float                           # Monigle column-height trial weight (0–0.95)
    v_weight: float | None                # SAAM DHI Volume Weight, if available
    discernibility: str | None            # high / moderate / low / absent
    headline: str                         # one-line recommendation
    consistency_notes: list[str] = field(default_factory=list)


def _discernibility_gate(discernibility: str | None) -> str:
    d = (discernibility or "").lower()
    if d == "high" or d == "moderate":
        return ("**High/moderate discernibility:** the volumetric ranges (area, column "
                "height, NTG) **must** be fully consistent with the DHI observations — "
                "honour the contact and edges the DHI defines.")
    if d == "low":
        return ("**Low discernibility:** only the *most-likely* volumetric parameters need "
                "be permissible within the DHI observations; widen the ranges with geology.")
    if d == "absent":
        return ("**No discernibility:** no geophysical tie required — but the volumes must "
                "not violate the root cause of the no-discernibility call (e.g. carbonate, "
                "imaging).")
    return ("Set discernibility on the DFI Setup tab to gate how strictly the volumes must "
            "follow the geophysics.")


def volumetrics_recommendation(
    dhi_score: float,
    *,
    discernibility: str | None = None,
    v_weight: float | None = None,
    fcr_present: bool | None = None,
) -> VolumetricsRecommendation:
    """Build a DHI→volumetrics blend recommendation (Monigle 2025).

    ``dhi_score`` is the 0–1 DHI score (all pathways). ``v_weight`` is the SAAM DHI
    Volume Weight when available. ``discernibility`` ∈ {high, moderate, low, absent}.
    ``fcr_present`` toggles the fluid-contact-reflection → NTG note.
    """
    s = max(0.0, min(1.0, float(dhi_score)))
    w = column_height_weight(s)
    headline = (
        f"Place the HC–water contact at the DFI-rated elevation in ~{w*100:.0f}% of "
        f"volumetric trials; let the remaining ~{(1-w)*100:.0f}% follow the geological/"
        f"structural spill estimate (deeper contact, larger column)."
    )
    notes: list[str] = [_discernibility_gate(discernibility)]
    if fcr_present is True:
        notes.append(
            f"**FCR present** → reservoir NTG generally **> {FCR_NTG_MIN*100:.0f}%** "
            "(observed 40–85%); a fluid-contact reflection precludes *low* NTG.")
    elif fcr_present is False:
        notes.append(
            f"**No FCR** → does not preclude moderate NTG (≲ {NO_FCR_NTG_MAX*100:.0f}%), "
            "but argues against the high-NTG end.")
    notes.append(
        f"**Porosity floor:** a DHI implies porosity above ~{POROSITY_FLOOR*100:.0f}% "
        "(DHIs are essentially never observed below this) — keep the porosity range "
        "consistent.")
    return VolumetricsRecommendation(
        dhi_score=s, w_ch=w, v_weight=v_weight,
        discernibility=discernibility, headline=headline, consistency_notes=notes,
    )
