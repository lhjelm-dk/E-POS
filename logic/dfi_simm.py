"""Shared Simm (2016) two-state Bayes primitives for the DFI evidence sources.

All three DFI evidence sources (DHI Index, Characteristic scoring /
Monigle 2025, and the Custom R tool) ultimately express their evidence as a
**likelihood ratio R** and read it through the same Simm two-state machinery.
This module is the single home for that machinery so the three pathways stay
mathematically consistent and present R the same way.

Canonical exports
-----------------
``simm_bayes_posterior(prior_pg, r)``
    Two-state Bayesian update (Simm 2016 p.15).
``dhi_score_from_r(r)``
    Monigle-style DHI score in **[0, 1]** = the posterior at a neutral 50/50
    prior. (UI callsites multiply by 100 for a percentage.)
``simm_rule_of_thumb(r)``
    Verbal interpretation of R → ``(label, comment, color)`` over 7 log-symmetric
    bands. Used for the verdict banner and the shaded R-plot bands.
``SIMM_R_BANDS``
    The R thresholds (and reciprocals) that separate those bands, for plotting.
``SIMM_RULE_OF_THUMB``
    The legacy 3-row narrative reference table from Simm (2016), kept verbatim
    for the characteristic-pathway reference tile.

This module has **no dependencies** on the other DFI logic modules, so both
``dhi_characteristics`` and ``dfi_custom`` can re-export from it without any
import cycle.
"""
from __future__ import annotations

import math


def simm_bayes_posterior(prior_pg: float, r: float) -> float:
    """Two-state Bayesian update per Simm 2016 p.15.

    ``posterior = R * prior / (R * prior + (1 - prior))``
    """
    prior_pg = max(0.0, min(1.0, prior_pg))
    if r <= 0:
        return prior_pg
    num = r * prior_pg
    den = num + (1.0 - prior_pg)
    return num / den if den > 0 else prior_pg


def dhi_score_from_r(r: float) -> float:
    """Monigle-style DHI score in **[0, 1]** = posterior at a neutral prior.

    ``score = R / (R + 1)``  (Bayes with prior_pg = 0.5). UI callsites scale by
    100 to display a percentage.
    """
    if r <= 0:
        return 0.0
    return r / (r + 1.0)


def simm_rule_of_thumb(r: float) -> tuple[str, str, str]:
    """Verbal interpretation of a likelihood ratio ``R``.

    Returns ``(label, comment, color)``. The bands follow Simm (2016) "Sense
    Check" guidance and the standard Bayes-factor convention; they are symmetric
    in log-odds, so an R that raises P(G) and a 1/R that lowers it carry equal
    strength. Simm cautions that for a *single* DFI line of evidence an honest R
    rarely exceeds ~3 either way; treat |R| ≳ 10 as exceptional and audit the inputs.

    Labels use the same ↑ (raises P(G)) / ↓ (lowers P(G)) convention as the
    rule-of-thumb band shading, for consistency across the DFI plots.
    """
    if r >= 10.0:
        return ("Decisive ↑", "Very rarely justified for one DFI — re-check the curves.", "#15803d")
    if r >= 3.0:
        return ("Strong ↑", "About the practical ceiling Simm suggests for a single DFI.", "#16a34a")
    if r >= 1.5:
        return ("Moderate ↑", "Credible supportive DFI evidence.", "#65a30d")
    if r > 1.0 / 1.5:
        return ("Negligible", "R ≈ 1 — the DFI barely shifts the prior.", "#6b7280")
    if r > 1.0 / 3.0:
        return ("Moderate ↓", "Credible evidence the DFI is anomalous against HC.", "#d97706")
    if r > 1.0 / 10.0:
        return ("Strong ↓", "About the practical floor Simm suggests for a single DFI.", "#dc2626")
    return ("Decisive ↓", "Very rarely justified for one DFI — re-check the curves.", "#991b1b")


# R thresholds (and reciprocals) for plotting the Simm rule-of-thumb bands.
SIMM_R_BANDS: tuple[float, ...] = (3.0, 1.5, 1.0, 1.0 / 1.5, 1.0 / 3.0)


# Legacy narrative reference (Simm 2016) — kept verbatim for the characteristic
# reference tile. ``(R ≈, interpretation)``.
SIMM_RULE_OF_THUMB: tuple[tuple[float, str], ...] = (
    (1.0, "Non-hydrocarbon explanations most likely — single anomaly often associated with stratigraphic trap."),
    (2.0, "Two first-order amplitude effects (e.g. anomaly + structural consistency, correlative amplitude change, AVO fluid vector)."),
    (3.0, "Multiple first-order amplitude effects, including potential contact effects. High degree of consistency between different effects."),
)


def geox_pdfi_cases(success: float, water: float, lsg: float,
                    reservoir: float) -> list[tuple[str, float, str]]:
    """Map four per-case DFI likelihoods onto SLB **GeoX**'s six DFI-Assessment
    cases (fluid × reservoir-evaluability), scaled so the strongest = 100 %.

    GeoX combines these conditional likelihoods with its own geological prior and
    only uses their **ratios**, so the absolute scale is free; we normalise to the
    maximum purely so the six numbers are readable on entry. The three
    non-evaluable-reservoir cases all map to the ``reservoir`` (reservoir-failure)
    likelihood, exactly like the DHI-Index hand-off.

    Returns a list of ``(geox_case_label, value_pct, represents)`` rows.
    """
    vals = [v for v in (success, water, lsg, reservoir) if v and v > 0.0]
    mx = max(vals) if vals else 1.0

    def _sc(v: float) -> float:
        return (max(0.0, float(v)) / mx) * 100.0 if mx > 0 else 0.0

    return [
        ("Oil & Eval. Res.",               _sc(success),   "Success"),
        ("Oil & Non. Eval. Res.",          _sc(reservoir), "Reservoir failure"),
        ("Water & Eval. Res.",             _sc(water),     "Water failure"),
        ("Water & Non. Eval. Res.",        _sc(reservoir), "Reservoir failure"),
        ("Low Sat. Gas & Eval. Res.",      _sc(lsg),       "LSG / other failure"),
        ("Low Sat. Gas & Non. Eval. Res.", _sc(reservoir), "Reservoir failure"),
    ]


def apply_discernibility(r: float, d: float) -> float:
    """Squash R toward 1 by a discernibility weight ``d`` ∈ [0, 1] (Monigle 2025).

    ``R_effective = R ** d``.  d=1 → unchanged; d=0 → R=1 (no effect).  Lives here
    (taking a plain float ``d``) so any pathway can apply a data-quality squash;
    the characteristic pathway wraps it with its ``DiscernibilityBucket``.
    """
    if r <= 0:
        return 1.0
    return math.exp(math.log(r) * d)
