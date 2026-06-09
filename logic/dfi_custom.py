"""Custom DFI-strength tool — derive R from two user-defined Gaussians.

This is the third DFI evidence source (alongside the DHI Index/SAAM pathway and
the Monigle-2025 characteristic scoring). It is a deliberately simple, stand-alone
way to turn a single "DHI strength" reading into a likelihood ratio R, when neither
a SAAM calibration nor a full characteristic score sheet is available.

The user defines two probability-density curves over a common DHI-strength axis
(default −100 … +100):

    P(DFI | HC)     — how a *hydrocarbon-bearing* prospect tends to look on the DHI
    P(DFI | No-HC)  — how a *non-hydrocarbon* (brine / fizz / no-reservoir) prospect
                      tends to look on the DHI

Each curve is a normal distribution specified by its **1st and 99th percentiles**
(P1, P99) — i.e. the user gives a plausible min and max, and the mean/SD follow:

    mean = (P1 + P99) / 2
    sd   = (P99 − P1) / (2·Φ⁻¹(0.99)) = (P99 − P1) / 4.65269…

For an observed DHI-strength reading ``s`` the likelihood ratio is

    R(s) = pdf_HC(s) / pdf_NoHC(s)

R is scale-invariant in the strength axis, so the −100…100 units are arbitrary —
only the *relative* heights of the two curves at ``s`` matter. R then feeds the
Simm two-state Bayesian update exactly like the characteristic-scoring pathway::

    posterior = R·prior / (R·prior + (1 − prior))

so this tool plugs into the existing characteristic results/summary plumbing.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

# 2 · Φ⁻¹(0.99).  Φ⁻¹(0.99) = 2.3263478740408408  →  z = 4.6526957480816815.
# (P99 − P1) spans this many standard deviations.
_P1_P99_Z: float = 2.0 * 2.3263478740408408

# Hard guards mirroring the characteristic pathway so a degenerate ratio can never
# blow up the Bayesian update.
R_FLOOR: float = 1.0 / 50.0
R_HARD_CAP: float = 50.0


def gaussian_from_p1_p99(p1: float, p99: float) -> tuple[float, float]:
    """Return ``(mean, sd)`` of the normal whose 1st/99th percentiles are ``p1``/``p99``.

    Worked example (user's): p1=−50, p99=100 → mean=25, sd=32.239… .
    ``sd`` is clamped to a tiny positive floor so a zero-width spec stays finite.
    """
    mean = (p1 + p99) / 2.0
    sd = abs(p99 - p1) / _P1_P99_Z
    return mean, max(sd, 1e-9)


def normal_pdf(x: float, mean: float, sd: float) -> float:
    """Standard normal probability density. Returns 0 for non-positive ``sd``."""
    if sd <= 0:
        return 0.0
    z = (x - mean) / sd
    return math.exp(-0.5 * z * z) / (sd * math.sqrt(2.0 * math.pi))


@dataclass(frozen=True)
class CustomCase:
    """One user-defined Gaussian over the DHI-strength axis.

    Defined by percentiles ``p1``/``p99``; ``mean``/``sd``/``pdf`` derive from them.
    ``geo_link`` is a free-text note tying the case to a geological risk parameter
    (e.g. "Charge + reservoir present → P(G)"), shown in the UI for interpretability.
    """

    key: str
    label: str
    p1: float
    p99: float
    geo_link: str = ""

    @property
    def mean(self) -> float:
        return gaussian_from_p1_p99(self.p1, self.p99)[0]

    @property
    def sd(self) -> float:
        return gaussian_from_p1_p99(self.p1, self.p99)[1]

    def pdf(self, x: float) -> float:
        return normal_pdf(x, self.mean, self.sd)


def custom_r(slider: float, hc: CustomCase, nohc: CustomCase) -> float:
    """Likelihood ratio R = pdf_HC(slider) / pdf_NoHC(slider), floored/capped.

    If the No-HC density underflows to ~0 (slider far in the HC tail) R is capped
    at ``R_HARD_CAP``; symmetrically floored at ``R_FLOOR``.
    """
    num = hc.pdf(slider)
    den = nohc.pdf(slider)
    if den <= 0.0:
        return R_HARD_CAP if num > 0.0 else 1.0
    r = num / den
    return float(min(max(r, R_FLOOR), R_HARD_CAP))


# Simm two-state primitives — canonical home is ``logic.dfi_simm`` (shared by all
# three DFI pathways). Re-exported so ``from logic.dfi_custom import …`` keeps
# working. NOTE: ``dhi_score_from_r`` returns a score in **[0, 1]** (UI scales ×100).
from logic.dfi_simm import (  # noqa: E402
    dhi_score_from_r,
    simm_rule_of_thumb,
    SIMM_R_BANDS,
)


# Default two-state spec — seeds the UI on first activation.
DEFAULT_HC = CustomCase(
    key="hc", label="P(DFI | HC)", p1=-50.0, p99=100.0,
    geo_link="Hydrocarbons in an evaluable reservoir → drives P(G) up (success case).",
)
DEFAULT_NOHC = CustomCase(
    key="nohc", label="P(DFI | No-HC)", p1=-100.0, p99=50.0,
    geo_link="Brine / fizz / no-reservoir → the pooled failure case.",
)

# ── Multi-case extension ────────────────────────────────────────────────────
# Six named outcomes, split into a SUCCESS group (hydrocarbons present) and a
# FAILURE group (no producible HC). By default every success case shares one
# curve and every failure case shares one curve — so multi-case reduces exactly
# to the simple HC vs No-HC two-state until the user unlinks a case.
SUCCESS_KEYS: tuple[str, ...] = ("oil", "gas", "oil_gas")
# Failure side mirrors the DHI-Index decomposition: three *fluid* failure modes
# (evaluable reservoir, wrong fluid) weighted by P(fluid | failure) — Water / LSG /
# Other — plus a separate Non-reservoir (reservoir-failure) case.
FLUID_FAILURE_KEYS: tuple[str, ...] = ("water", "lsg", "other")
FAILURE_KEYS: tuple[str, ...] = ("water", "lsg", "other", "non_reservoir")

CASE_LABELS: dict[str, str] = {
    "oil":           "Oil",
    "gas":           "Gas",
    "oil_gas":       "Oil + Gas",
    "water":         "Water (brine)",
    "lsg":           "Low-sat gas (fizz)",
    "other":         "Other fluid",
    "non_reservoir": "Non-reservoir",
}

CASE_GEO_LINK: dict[str, str] = {
    "oil":           "Oil leg in an evaluable reservoir → success (drives P(G) up).",
    "gas":           "Gas leg in an evaluable reservoir → success (drives P(G) up).",
    "oil_gas":       "Oil + gas column → success (drives P(G) up).",
    "water":         "Brine-filled evaluable reservoir → fluid failure.",
    "lsg":           "Low-saturation / residual (fizz) gas → fluid failure.",
    "other":         "Other non-producible fluid (e.g. CO₂) in an evaluable reservoir → fluid failure.",
    "non_reservoir": "No effective / non-evaluable reservoir → reservoir-presence failure (geology, not fluid).",
}


def grouped_r(
    slider: float,
    cases: dict[str, CustomCase],
    weights: dict[str, float] | None = None,
    success_keys: tuple[str, ...] = SUCCESS_KEYS,
    failure_keys: tuple[str, ...] = FAILURE_KEYS,
) -> float:
    """Multi-case likelihood ratio.

        R = (Σ_s w_s · pdf_s(slider)) / (Σ_f w_f · pdf_f(slider))

    Weights are normalised *within* each group, so they encode the relative
    prior mix of fluids/failure modes, not absolute scale. With every success
    case sharing one curve and every failure case sharing one curve (and equal
    weights) this collapses to the simple ``custom_r`` two-state ratio.
    Floored/capped to [R_FLOOR, R_HARD_CAP].
    """
    w = weights or {}

    def _grp(keys: tuple[str, ...]) -> float:
        present = [k for k in keys if k in cases]
        if not present:
            return 0.0
        ws = [max(float(w.get(k, 1.0)), 0.0) for k in present]
        tot = sum(ws)
        if tot <= 0.0:
            ws = [1.0] * len(present)
            tot = float(len(present))
        return sum((wi / tot) * cases[k].pdf(slider) for wi, k in zip(ws, present))

    num = _grp(success_keys)
    den = _grp(failure_keys)
    if den <= 0.0:
        return R_HARD_CAP if num > 0.0 else 1.0
    return float(min(max(num / den, R_FLOOR), R_HARD_CAP))


# Per-case default (P1, P99) and prior weight for multi-case mode.
CASE_DEFAULTS: dict[str, tuple[float, float]] = {
    "oil":           (-50.0, 100.0),
    "gas":           (-40.0,  80.0),
    "oil_gas":       (-40.0,  90.0),
    "water":         (-100.0, 50.0),
    "lsg":           (-80.0,  80.0),
    "other":         (-80.0,  80.0),   # shares the LSG-type curve (as DHI shares LSG class)
    "non_reservoir": (-70.0,  50.0),
}

CASE_WEIGHT_DEFAULTS: dict[str, float] = {
    # Success mix: equal 1/3 across oil / gas / oil+gas (normalised → 33% each).
    "oil":           0.33,
    "gas":           0.33,
    "oil_gas":       0.33,
    # Fluid-failure mix P(fluid | failure) — Water 80% · LSG 20% · Other 0%
    # (sums to 1), matching the DHI-Index default fluid-failure weights.
    "water":         0.80,
    "lsg":           0.20,
    "other":         0.00,
    # Reservoir failure is geology's job (already in the prior), so it sits at 0
    # by default — a separate, available-but-off case, exactly like DHI.
    "non_reservoir": 0.00,
}

# Default DHI-strength slider reading (seeds the UI on first activation).
DEFAULT_SLIDER: float = 7.0


@dataclass(frozen=True)
class CustomRConfig:
    """A fully-specified custom-tool R model: the case curves, their weights, and
    the current DHI-strength reading. ``cases``/``weights`` are keyed by the same
    SUCCESS/FAILURE keys in both modes (in linked mode every success key shares the
    HC curve and every failure key the No-HC curve), so :func:`grouped_r` evaluates
    R identically for both — and reduces to :func:`custom_r` in the linked case."""

    multicase: bool
    slider: float
    cases: dict[str, CustomCase]
    weights: dict[str, float]

    def r_at(self, x: float) -> float:
        """Likelihood ratio R at DHI strength ``x``."""
        return grouped_r(x, self.cases, self.weights)

    @property
    def r(self) -> float:
        """R at the current slider reading."""
        return self.r_at(self.slider)


def custom_config_from_state(state) -> CustomRConfig:
    """Reconstruct a :class:`CustomRConfig` from persisted setup widget values.

    ``state`` is any mapping with a ``.get(key, default)`` method (e.g. Streamlit's
    ``st.session_state``). This is the single source of truth for turning the
    persisted custom-tool inputs into an R model, shared by the DFI Setup and DFI
    Results pages so both build R from one place. Missing keys fall back to the
    same defaults the Setup widgets seed.
    """
    g = state.get
    multicase = bool(g("dfi_custom_multicase", False))
    slider = float(g("dfi_custom_slider", DEFAULT_SLIDER))
    cases: dict[str, CustomCase] = {}
    weights: dict[str, float] = {}
    if multicase:
        for k in SUCCESS_KEYS + FAILURE_KEYS:
            d_p1, d_p99 = CASE_DEFAULTS[k]
            cases[k] = CustomCase(
                k, CASE_LABELS[k],
                float(g(f"dfi_custom_{k}_p1",  d_p1)),
                float(g(f"dfi_custom_{k}_p99", d_p99)),
            )
            weights[k] = float(g(f"dfi_custom_{k}_w", CASE_WEIGHT_DEFAULTS[k]))
    else:
        hc = CustomCase("hc",   "P(DFI | HC)",
                        float(g("dfi_custom_hc_p1",  DEFAULT_HC.p1)),
                        float(g("dfi_custom_hc_p99", DEFAULT_HC.p99)))
        no = CustomCase("nohc", "P(DFI | No-HC)",
                        float(g("dfi_custom_no_p1",  DEFAULT_NOHC.p1)),
                        float(g("dfi_custom_no_p99", DEFAULT_NOHC.p99)))
        for k in SUCCESS_KEYS:
            cases[k] = hc;  weights[k] = 1.0
        for k in FAILURE_KEYS:
            cases[k] = no;  weights[k] = 1.0
    return CustomRConfig(multicase=multicase, slider=slider, cases=cases, weights=weights)

def _weighted_mix_pdf(cfg: "CustomRConfig", keys: tuple[str, ...]) -> float:
    """Weight-blended P(DFI|case) density over ``keys`` at the current slider.
    Falls back to a plain mean if all weights are zero (matches the GeoX hand-off)."""
    x = cfg.slider
    w = {k: max(cfg.weights.get(k, 0.0), 0.0) for k in keys}
    pdfs = {k: cfg.cases[k].pdf(x) for k in keys}
    tot = sum(w.values())
    if tot > 0:
        return sum(w[k] * pdfs[k] for k in keys) / tot
    return sum(pdfs.values()) / len(keys) if keys else 0.0


def custom_channel_likelihoods(cfg: "CustomRConfig"):
    """Express a Custom-tool config in the shared channel language.

    Multi-case → 3 channels (pillar-resolved): success-mix, fluid-failure-mix, and
    the dedicated ``non_reservoir`` curve as the reservoir-failure channel.
    Dual-case → aggregate-only (one HC vs one No-HC curve cannot separate reservoir).
    """
    from logic.dfi_pillar_update import ChannelLikelihoods, aggregate_channels
    if not cfg.multicase:
        return aggregate_channels(cfg.r, "Custom R tool — dual-case")
    return ChannelLikelihoods(
        l_hc=_weighted_mix_pdf(cfg, SUCCESS_KEYS),
        l_fluidfail=_weighted_mix_pdf(cfg, FLUID_FAILURE_KEYS),
        l_nonres=cfg.cases["non_reservoir"].pdf(cfg.slider),
        method_label="Custom R tool — multi-case",
    )


# ``simm_rule_of_thumb`` and ``SIMM_R_BANDS`` are imported from ``logic.dfi_simm``
# above (canonical home, shared with the characteristic pathway).
