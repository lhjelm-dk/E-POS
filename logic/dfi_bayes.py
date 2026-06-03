"""DFI Bayesian update — core math.

Mirrors the methodology in the INEOS workbook ('DHI Prospect inputs' sheet) but
uses **rigorous Gaussian PDFs** as likelihoods (the workbook's `× 20/100`
factor is a frequency-scaling artefact for GeoX compatibility and is dropped
here — the Bayesian denominator normalises consistently regardless).

Public entry points
-------------------

``compute_dfi_posterior(...)``
    Single-prior, single-method Bayes computation.  Returns the posterior
    P(G | DFI), the posterior probability of each of the 7 outcome classes,
    and the diagnostic metrics R_SAAM (DHI-Index strength) and DHI-Volume-Weight.

``attribute_classic(...)``
    Spreadsheet's log-attribution that distributes the posterior across the
    8 per-pillar Pgs (4 pillars × Play/Cond) so the product invariant holds.

``attribute_esl_optionA(...)``
    Equal multiplicative scaling that updates each pillar's (S_for, S_against)
    masses while preserving commitment ``C = S_for + S_against``.

``attribute_esl_optionB(...)``
    Bel/Pl-preserving update.  Recomputes the posterior at w=0 (Bel side) and
    w=1 (Pl side), then redistributes the change across pillars.

All outcome probabilities and pillar Pgs are plain floats in [0, 1].
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from logic.dfi_calibration import Calibration, ClassStats


# ─────────────────────────────────────────────────────────────────────────────
# Gaussian PDF — pure numpy-free implementation to keep this module light
# ─────────────────────────────────────────────────────────────────────────────

_SQRT_2PI = math.sqrt(2.0 * math.pi)


def gaussian_pdf(x: float, mu: float, sigma: float) -> float:
    """Standard univariate Gaussian PDF.  Returns 0 if sigma <= 0."""
    if sigma <= 0:
        return 0.0
    z = (x - mu) / sigma
    return math.exp(-0.5 * z * z) / (sigma * _SQRT_2PI)


def likelihood_for_class(dhi_index: float, stats: ClassStats,
                         sd_mode: str = "upper") -> float:
    """``P(DHI | class)`` evaluated as the Gaussian PDF at ``DHI/100``.

    The PDF is unnormalised in the Bayesian sense (it's a density), but the
    posterior denominator divides through so all classes are on the same
    footing — that's all that matters.
    """
    return gaussian_pdf(dhi_index / 100.0, stats.mean, stats.sd(sd_mode))


# ─────────────────────────────────────────────────────────────────────────────
# 7-outcome decomposition of the prior
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PriorPillars:
    """The 8 per-pillar Pgs from a single method (ESL or Classic).

    Names match the workbook's column letters:  D=Charge_Play, E=Trap_Play,
    F=Reservoir_Play, G=Retention_Play, H=Charge_Cond, I=Trap_Cond,
    J=Reservoir_Cond, K=Retention_Cond.
    """
    charge_play:    float
    trap_play:      float
    reservoir_play: float
    retention_play: float
    charge_cond:    float
    trap_cond:      float
    reservoir_cond: float
    retention_cond: float

    @property
    def prior_pg(self) -> float:
        """``Init Pg`` = product of all 8 (= P(oil & eval-res, success))."""
        return (self.charge_play * self.trap_play * self.reservoir_play *
                self.retention_play * self.charge_cond * self.trap_cond *
                self.reservoir_cond * self.retention_cond)

    @property
    def non_reservoir_product(self) -> float:
        """Product of the 6 non-reservoir pillars (D*E*G*H*I*K in the workbook)."""
        return (self.charge_play * self.trap_play * self.retention_play *
                self.charge_cond * self.trap_cond * self.retention_cond)

    @property
    def reservoir_product(self) -> float:
        """``F × J`` = combined reservoir Pg."""
        return self.reservoir_play * self.reservoir_cond


@dataclass
class FluidWeights:
    """User-specified P(fluid | failure) — must sum to 1."""
    water: float = 0.8
    lsg:   float = 0.2
    other: float = 0.0

    def normalised(self) -> "FluidWeights":
        s = self.water + self.lsg + self.other
        if s <= 0:
            return FluidWeights(1.0, 0.0, 0.0)
        return FluidWeights(self.water / s, self.lsg / s, self.other / s)


@dataclass
class PriorOutcomes:
    """The 8 prior outcome probabilities (sum to 1)."""
    oil_eval_success:        float
    oil_noneval_failure:     float
    water_eval_failure:      float
    water_noneval_failure:   float
    lsg_eval_failure:        float
    lsg_noneval_failure:     float
    other_eval_failure:      float
    other_noneval_failure:   float

    def as_dict(self) -> dict[str, float]:
        return {
            "oil_eval_success":      self.oil_eval_success,
            "oil_noneval_failure":   self.oil_noneval_failure,
            "water_eval_failure":    self.water_eval_failure,
            "water_noneval_failure": self.water_noneval_failure,
            "lsg_eval_failure":      self.lsg_eval_failure,
            "lsg_noneval_failure":   self.lsg_noneval_failure,
            "other_eval_failure":    self.other_eval_failure,
            "other_noneval_failure": self.other_noneval_failure,
        }

    def total(self) -> float:
        return sum(self.as_dict().values())


def decompose_prior(p: PriorPillars, w: FluidWeights) -> PriorOutcomes:
    """Workbook columns 22..29 (V..AC):  8 mutually exclusive outcomes.

    P(oil & eval-res, success)     = Init Pg
    P(oil & non-eval-res, failure) = (non-res product) × (1 − reservoir product)
    P(fluid & eval-res, failure)   = (1 − non-res product) × (reservoir product) × w_fluid
    P(fluid & non-eval-res, fail.) = (1 − non-res product) × (1 − reservoir product) × w_fluid

    The 8 sum to 1.
    """
    w = w.normalised()
    init_pg   = p.prior_pg
    non_res_p = p.non_reservoir_product
    res_p     = p.reservoir_product
    one_minus_non_res = 1.0 - non_res_p
    one_minus_res     = 1.0 - res_p

    return PriorOutcomes(
        oil_eval_success      = init_pg,
        oil_noneval_failure   = non_res_p * one_minus_res,
        water_eval_failure    = one_minus_non_res * res_p     * w.water,
        water_noneval_failure = one_minus_non_res * one_minus_res * w.water,
        lsg_eval_failure      = one_minus_non_res * res_p     * w.lsg,
        lsg_noneval_failure   = one_minus_non_res * one_minus_res * w.lsg,
        other_eval_failure    = one_minus_non_res * res_p     * w.other,
        other_noneval_failure = one_minus_non_res * one_minus_res * w.other,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Likelihood mapping — which SAAM class supplies P(DFI | outcome)
# ─────────────────────────────────────────────────────────────────────────────

def _likelihood_per_outcome(dhi_index: float, calib: Calibration,
                            sd_mode: str = "upper",
                            fluid_type: str = "Success") -> dict[str, float]:
    """Likelihood of the observed DHI for each of the 8 outcomes.

    Outcome → SAAM class mapping (mirrors the workbook):
      oil & eval-res success      → ``fluid_type``  (Success/Oil/OilGas/Gas)
      oil & non-eval-res failure  → Reservoir_failure
      water & eval-res failure    → H2O_failure
      water & non-eval-res fail.  → Reservoir_failure
      LSG/Other & eval-res fail.  → LSG_failure
      LSG/Other & non-eval-res    → Reservoir_failure
    """
    if fluid_type not in calib.classes:
        fluid_type = "Success"
    L_success = likelihood_for_class(dhi_index, calib.classes[fluid_type],     sd_mode)
    L_water   = likelihood_for_class(dhi_index, calib.classes["H2O_failure"],  sd_mode)
    L_lsg     = likelihood_for_class(dhi_index, calib.classes["LSG_failure"],  sd_mode)
    L_resfail = likelihood_for_class(dhi_index, calib.classes["Reservoir_failure"], sd_mode)
    return {
        "oil_eval_success":      L_success,
        "oil_noneval_failure":   L_resfail,
        "water_eval_failure":    L_water,
        "water_noneval_failure": L_resfail,
        "lsg_eval_failure":      L_lsg,
        "lsg_noneval_failure":   L_resfail,
        "other_eval_failure":    L_lsg,
        "other_noneval_failure": L_resfail,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Posterior
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DFIPosterior:
    """Result of one Bayesian update.

    ``posterior_pg`` is the headline number — ``P(G | DFI)``.
    """
    posterior_pg:        float
    posterior_outcomes:  dict[str, float]   # P(outcome | DFI) for all 8
    prior_outcomes:      PriorOutcomes
    likelihoods:         dict[str, float]   # P(DFI | outcome)
    dhi_index:           float
    sd_mode:             str
    fluid_type:          str
    fluid_weights:       FluidWeights
    # Auxiliary diagnostics
    r_saam:              float              # R_SAAM = L_success / E[L|failure] (DHI-Index strength)
    dhi_volume_weight:   float              # = L_success / (L_success + L_failure_with_DFI)
    # Joint marginals (workbook AE/AF/AG/AH)
    joint_success_dfi:   float              # P(DFI ∧ success)
    joint_failure_dfi:   float              # P(DFI ∧ overall failure)
    joint_total_dfi:     float              # P(DFI) = sum of joint over all outcomes
    # The ∏-pillars "Init Pg" the 8-outcome failure split was derived from, BEFORE any
    # prior_pg_override re-anchoring. Kept for audit/diagnostics; None when no override.
    init_pg_unscaled:    float | None = None


def compute_dfi_posterior(pillars: PriorPillars,
                          dhi_index: float,
                          calib: Calibration,
                          fluid_weights: FluidWeights = FluidWeights(),
                          sd_mode: str = "upper",
                          fluid_type: str = "Success",
                          prior_pg_override: float | None = None) -> DFIPosterior:
    """Run the Bayesian update once for one prior + DFI observation.

    ``prior_pg_override`` re-anchors the success prior to a supplied scalar (e.g. the
    ESL *mass-rollup* P(G, ESL)) while preserving the pillar-derived failure-mode mix.
    R_SAAM and DHI Volume Weight are invariant to this re-anchoring (they are likelihood
    ratios); only the prior→posterior anchor moves. When None, the native ∏-pillars
    Init Pg is used, exactly as before.
    """
    init_pg_unscaled = pillars.prior_pg
    prior_outcomes = decompose_prior(pillars, fluid_weights)
    if prior_pg_override is not None:
        prior_outcomes = PriorOutcomes(
            **rescale_outcomes_to_success(prior_outcomes.as_dict(), prior_pg_override)
        )
    likelihoods    = _likelihood_per_outcome(dhi_index, calib, sd_mode, fluid_type)

    # Joint = prior × likelihood per outcome
    joint = {k: prior_outcomes.as_dict()[k] * likelihoods[k] for k in likelihoods}
    total = sum(joint.values())
    if total <= 0:
        # Degenerate case — no valid likelihood; return prior unchanged
        post = {k: prior_outcomes.as_dict()[k] for k in likelihoods}
        post_pg = prior_outcomes.oil_eval_success
    else:
        post = {k: v / total for k, v in joint.items()}
        post_pg = post["oil_eval_success"]

    # Diagnostic metrics (workbook cols 57, 58)
    joint_success    = joint["oil_eval_success"]
    joint_failure    = total - joint_success
    L_success        = likelihoods["oil_eval_success"]
    # The workbook computes an "average likelihood for failure outcomes" by
    # normalising the failure-side joint mass by the prior failure marginal:
    #     E[L | failure]  =  joint_failure  /  P(prior failure)
    # The two metrics are then defined relative to this average.
    prior_failure_marginal = 1.0 - prior_outcomes.oil_eval_success
    avg_L_failure = (joint_failure / prior_failure_marginal) if prior_failure_marginal > 0 else 0.0
    # R_SAAM (DHI-Index strength)  =  L_success / E[L|failure]   (workbook col 57: =N5/AG5)
    r_saam = (L_success / avg_L_failure) if avg_L_failure > 0 else float("inf")
    # DHI Volume Weight =  L_success / (L_success + E[L|failure])  (workbook col 58: =N5/(N5+AG5))
    weight_denom = L_success + avg_L_failure
    dhi_volume = (L_success / weight_denom) if weight_denom > 0 else 0.0

    return DFIPosterior(
        posterior_pg       = post_pg,
        posterior_outcomes = post,
        prior_outcomes     = prior_outcomes,
        likelihoods        = likelihoods,
        dhi_index          = dhi_index,
        sd_mode            = sd_mode,
        fluid_type         = fluid_type,
        fluid_weights      = fluid_weights,
        r_saam             = r_saam,
        dhi_volume_weight  = dhi_volume,
        joint_success_dfi  = joint_success,
        joint_failure_dfi  = joint_failure,
        joint_total_dfi    = total,
        init_pg_unscaled   = init_pg_unscaled,
    )


def posterior_pg_from_outcomes(prior_outcomes: dict[str, float],
                               dhi_index: float,
                               calib: Calibration,
                               sd_mode: str = "upper",
                               fluid_type: str = "Success") -> float:
    """Posterior P(G | DFI) starting from an explicit 8-outcome prior dict.

    Used by the iso-DHI reference plot, where the prior is a synthetic
    distribution (a target Initial Pg with the prospect's failure-mode mix held
    fixed) rather than one derived from pillar masses.
    """
    likelihoods = _likelihood_per_outcome(dhi_index, calib, sd_mode, fluid_type)
    joint = {k: prior_outcomes.get(k, 0.0) * likelihoods[k] for k in likelihoods}
    total = sum(joint.values())
    if total <= 0:
        return prior_outcomes.get("oil_eval_success", 0.0)
    return joint["oil_eval_success"] / total


def rescale_outcomes_to_success(prior_outcomes: dict[str, float],
                                target_success: float) -> dict[str, float]:
    """Rescale an 8-outcome prior so success = ``target_success``.

    The seven failure outcomes are scaled together to fill ``1 - target_success``
    while preserving their relative proportions (so the assumed failure-mode mix —
    water/LSG/other × eval/non-eval — is held constant as the overall prior Pg
    sweeps). This is the defensible "generic Initial Pg" interpretation for the
    iso-DHI adjustment curves.
    """
    target_success = max(0.0, min(1.0, target_success))
    d = dict(prior_outcomes)
    fail_keys = [k for k in d if k != "oil_eval_success"]
    fail_sum = sum(d[k] for k in fail_keys)
    out = {"oil_eval_success": target_success}
    remaining = 1.0 - target_success
    if fail_sum <= 0:
        # No failure structure to preserve — split residual across non-eval reservoir
        share = remaining / len(fail_keys) if fail_keys else 0.0
        for k in fail_keys:
            out[k] = share
    else:
        for k in fail_keys:
            out[k] = remaining * (d[k] / fail_sum)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Per-pillar attribution — Classic (log-split, spreadsheet method)
# ─────────────────────────────────────────────────────────────────────────────

def _safe_log(x: float, floor: float = 1e-12) -> float:
    return math.log(max(x, floor))


def _reservoir_posterior(post_outcomes: dict[str, float]) -> float:
    """Sum of posteriors with evaluable reservoir (workbook col 43 = ``AQ5``)."""
    return (
        post_outcomes["oil_eval_success"]
        + post_outcomes["water_eval_failure"]
        + post_outcomes["lsg_eval_failure"]
        + post_outcomes["other_eval_failure"]
    )


def attribute_classic(pillars: PriorPillars,
                      post: DFIPosterior) -> PriorPillars:
    """Reservoir-aware log-attribution (mirrors workbook cols 43..55).

    Two-step decomposition:

    1. **Reservoir vs non-reservoir split.**
       ``reservoir_contribution = sum of eval-reservoir posteriors`` (``AQ5``).
       ``ctr_contribution = posterior_pg / reservoir_contribution`` (``AR5``) —
       the residual share that the Charge/Trap/Retention pillars need to
       multiply to.

    2. **Per-pillar log split within Charge/Trap/Retention** (``AS5``, ``AT5``,
       ``AU5``)::

           AS5 = AR5 ^ ( ln(D*H) / ln(D*E*G*H*I*K) )
           AT5 = AR5 ^ ( ln(E*I) / ln(D*E*G*H*I*K) )
           AU5 = AR5 ^ ( ln(G*K) / ln(D*E*G*H*I*K) )

       so that ``AS5 × AT5 × AU5 = AR5``.  Within each pillar, Play vs Cond is
       split by the same log-ratio.

    The Reservoir pillar pair (``F``, ``J``) absorbs the entire
    ``reservoir_contribution`` (``AQ5``) directly.

    Invariant: ``∏(8 modified pillars) = posterior_pg`` exactly when no pillar
    is at 1.0 (those stay at 1.0 by construction).
    """
    if pillars.prior_pg <= 0:
        return pillars

    # Step 1: reservoir contribution AQ5
    AQ = _reservoir_posterior(post.posterior_outcomes)
    # Step 2: Charge/Trap/Retention contribution AR5
    AR = (post.posterior_pg / AQ) if AQ > 0 else 1.0

    # Pillar pair products
    D, H = pillars.charge_play,    pillars.charge_cond
    E, I = pillars.trap_play,      pillars.trap_cond
    F, J = pillars.reservoir_play, pillars.reservoir_cond
    G, K = pillars.retention_play, pillars.retention_cond

    DH, EI, FJ, GK = D * H, E * I, F * J, G * K
    non_res_prod = DH * EI * GK  # = D*E*G*H*I*K

    def _attr_pair(AR_or_AQ: float, prod_pair: float, denom_prod: float) -> float:
        """Compute pillar-pair contribution X = AR_or_AQ ^ (ln(pair) / ln(denom))."""
        if prod_pair >= 1.0:  # ln(1) = 0 → workbook formula returns 1
            return 1.0
        if denom_prod >= 1.0 or denom_prod <= 0:
            return AR_or_AQ
        return AR_or_AQ ** (_safe_log(prod_pair) / _safe_log(denom_prod))

    # Individual pillar-pair contributions (AS5, AT5, AU5)
    AS = _attr_pair(AR, DH, non_res_prod)  # Charge
    AT = _attr_pair(AR, EI, non_res_prod)  # Trap
    AU = _attr_pair(AR, GK, non_res_prod)  # Retention
    # Reservoir pair absorbs AQ directly (workbook uses AQ5 for Reservoir attribution)
    AQ_pair = AQ

    def _split(pair_contrib: float, pair_prod: float, leg_value: float) -> float:
        """Split a pillar-pair contribution between Play (leg) and Cond legs
        by the same log-ratio:  leg_new = pair_contrib ^ (ln(leg) / ln(pair_prod))."""
        if pair_prod >= 1.0:
            return 1.0
        if leg_value >= 1.0 or leg_value <= 0:
            return leg_value
        return pair_contrib ** (_safe_log(leg_value) / _safe_log(pair_prod))

    return PriorPillars(
        charge_play    = _split(AS,      DH, D),
        trap_play      = _split(AT,      EI, E),
        reservoir_play = _split(AQ_pair, FJ, F),
        retention_play = _split(AU,      GK, G),
        charge_cond    = _split(AS,      DH, H),
        trap_cond      = _split(AT,      EI, I),
        reservoir_cond = _split(AQ_pair, FJ, J),
        retention_cond = _split(AU,      GK, K),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Per-pillar attribution — ESL Option A (equal multiplicative + reverse-engineer masses)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ESLMasses:
    """ESL Italian-Flag masses for one pillar element."""
    s_for:     float
    s_against: float

    @property
    def white(self) -> float:
        return max(0.0, 1.0 - self.s_for - self.s_against)

    @property
    def commitment(self) -> float:
        return self.s_for + self.s_against


def policy_p(m: ESLMasses, w: float) -> float:
    return m.s_for + w * m.white


def reverse_engineer_masses_preserving_commitment(
    pg_target: float, current: ESLMasses, w: float,
) -> ESLMasses:
    """Find new (S_for, S_against) with **commitment C unchanged** such that
    ``policy_p(new, w) = pg_target``.

    With C = S_for + S_against fixed:
        pg_target = S_for_new + w × (1 − C)
        ⇒ S_for_new = pg_target − w × (1 − C)
        ⇒ S_against_new = C − S_for_new

    If the result violates [0, 1] bounds on S_for_new or S_against_new, we
    relax the commitment-preservation constraint and clamp.
    """
    C = current.commitment
    # If the prior pillar had no white (C=1) and w != current effective stance,
    # we cannot move pg without changing C.  In that case allocate change to
    # S_for and complement to S_against.
    if C <= 0:
        # Prior was completely uncommitted → put everything to S_for or S_against
        new_sf = max(0.0, min(1.0, pg_target))
        return ESLMasses(s_for=new_sf, s_against=0.0)
    white = 1.0 - C
    new_sf = pg_target - w * white
    new_sa = C - new_sf
    # Clamp to valid range; if out of bounds, drop the commitment-preserving
    # constraint and shift accordingly.
    if new_sf < 0.0:
        # pg_target is unachievable at this C and w → push S_for to 0, white to absorb
        new_sf = 0.0
        new_white = pg_target / max(w, 1e-9) if w > 0 else 0.0
        new_white = min(new_white, 1.0)
        new_sa = max(0.0, 1.0 - new_sf - new_white)
    elif new_sa < 0.0:
        # pg_target too low for the original commitment → reduce S_against to 0
        new_sa = 0.0
        # Recompute new_sf so that S_for + w*White = pg_target with S_against=0
        # pg_target = sf + w*(1 - sf - 0) = sf*(1-w) + w
        # ⇒ sf = (pg_target - w)/(1-w)  (if w<1; if w=1, sf=anything between 0..1 with white=1-sf)
        if w < 1.0:
            new_sf = max(0.0, min(1.0, (pg_target - w) / (1.0 - w)))
        else:
            new_sf = pg_target
    new_sf = max(0.0, min(1.0, new_sf))
    new_sa = max(0.0, min(1.0 - new_sf, new_sa))
    return ESLMasses(s_for=new_sf, s_against=new_sa)


def attribute_esl_optionA(
    pillars: PriorPillars,
    pillar_masses: dict[str, dict[str, ESLMasses]],
    posterior_pg: float,
    w: float,
) -> dict[str, dict[str, ESLMasses]]:
    """Equal multiplicative scaling per pillar, then reverse-engineer (S_for, S_against).

    ``pillar_masses`` layout::
        {'charge': {'play': ESLMasses, 'cond': ESLMasses},
         'trap':   {'play': ESLMasses, 'cond': ESLMasses},  ... }

    Returns a dict of the same shape with updated masses.
    """
    prior = pillars.prior_pg
    if prior <= 0 or posterior_pg <= 0:
        return pillar_masses
    ratio = posterior_pg / prior
    # 8 pillar slots — distribute the log-ratio evenly: each pillar takes ratio^(1/8)
    per_pillar_ratio = ratio ** (1.0 / 8.0)

    name_to_pg = {
        ("charge",    "play"): pillars.charge_play,
        ("trap",      "play"): pillars.trap_play,
        ("reservoir", "play"): pillars.reservoir_play,
        ("retention", "play"): pillars.retention_play,
        ("charge",    "cond"): pillars.charge_cond,
        ("trap",      "cond"): pillars.trap_cond,
        ("reservoir", "cond"): pillars.reservoir_cond,
        ("retention", "cond"): pillars.retention_cond,
    }

    out: dict[str, dict[str, ESLMasses]] = {}
    for (pillar, scope), pg_old in name_to_pg.items():
        pg_new = max(0.0, min(1.0, pg_old * per_pillar_ratio))
        new_masses = reverse_engineer_masses_preserving_commitment(
            pg_new, pillar_masses[pillar][scope], w,
        )
        out.setdefault(pillar, {})[scope] = new_masses
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Per-pillar attribution — ESL Option B (Bel/Pl-preserving)
# ─────────────────────────────────────────────────────────────────────────────

def attribute_esl_optionB(
    pillars: PriorPillars,
    pillar_masses: dict[str, dict[str, ESLMasses]],
    dhi_index: float,
    calib: Calibration,
    fluid_weights: FluidWeights,
    sd_mode: str,
    fluid_type: str,
) -> dict[str, dict[str, ESLMasses]]:
    """Recompute the posterior at w=0 (Bel-side) and w=1 (Pl-side), then
    redistribute the change across pillars by equal log-share.

    The per-pillar new ``S_for`` and ``new (1 − S_against)`` are derived from
    the posterior Bel and Pl respectively.
    """
    # Compute posterior at w=0 and w=1 using the Bel-only and Pl-only priors
    bel_pillars = PriorPillars(
        charge_play    = pillar_masses["charge"]["play"].s_for,
        trap_play      = pillar_masses["trap"]["play"].s_for,
        reservoir_play = pillar_masses["reservoir"]["play"].s_for,
        retention_play = pillar_masses["retention"]["play"].s_for,
        charge_cond    = pillar_masses["charge"]["cond"].s_for,
        trap_cond      = pillar_masses["trap"]["cond"].s_for,
        reservoir_cond = pillar_masses["reservoir"]["cond"].s_for,
        retention_cond = pillar_masses["retention"]["cond"].s_for,
    )
    pl_pillars = PriorPillars(
        charge_play    = 1.0 - pillar_masses["charge"]["play"].s_against,
        trap_play      = 1.0 - pillar_masses["trap"]["play"].s_against,
        reservoir_play = 1.0 - pillar_masses["reservoir"]["play"].s_against,
        retention_play = 1.0 - pillar_masses["retention"]["play"].s_against,
        charge_cond    = 1.0 - pillar_masses["charge"]["cond"].s_against,
        trap_cond      = 1.0 - pillar_masses["trap"]["cond"].s_against,
        reservoir_cond = 1.0 - pillar_masses["reservoir"]["cond"].s_against,
        retention_cond = 1.0 - pillar_masses["retention"]["cond"].s_against,
    )

    post_bel = compute_dfi_posterior(bel_pillars, dhi_index, calib,
                                     fluid_weights, sd_mode, fluid_type)
    post_pl  = compute_dfi_posterior(pl_pillars,  dhi_index, calib,
                                     fluid_weights, sd_mode, fluid_type)

    # New Bel and Pl pillar attributions (equal log share per pillar — 8 slots)
    bel_pillars_new = attribute_classic(bel_pillars, post_bel)
    pl_pillars_new  = attribute_classic(pl_pillars,  post_pl)

    name_to_attr = {
        ("charge",    "play"): ("charge_play",    bel_pillars_new.charge_play,    pl_pillars_new.charge_play),
        ("trap",      "play"): ("trap_play",      bel_pillars_new.trap_play,      pl_pillars_new.trap_play),
        ("reservoir", "play"): ("reservoir_play", bel_pillars_new.reservoir_play, pl_pillars_new.reservoir_play),
        ("retention", "play"): ("retention_play", bel_pillars_new.retention_play, pl_pillars_new.retention_play),
        ("charge",    "cond"): ("charge_cond",    bel_pillars_new.charge_cond,    pl_pillars_new.charge_cond),
        ("trap",      "cond"): ("trap_cond",      bel_pillars_new.trap_cond,      pl_pillars_new.trap_cond),
        ("reservoir", "cond"): ("reservoir_cond", bel_pillars_new.reservoir_cond, pl_pillars_new.reservoir_cond),
        ("retention", "cond"): ("retention_cond", bel_pillars_new.retention_cond, pl_pillars_new.retention_cond),
    }

    out: dict[str, dict[str, ESLMasses]] = {}
    for (pillar, scope), (_name, new_bel, new_pl) in name_to_attr.items():
        new_sf = max(0.0, min(1.0, new_bel))
        new_sa = max(0.0, min(1.0 - new_sf, 1.0 - new_pl))
        out.setdefault(pillar, {})[scope] = ESLMasses(s_for=new_sf, s_against=new_sa)
    return out
