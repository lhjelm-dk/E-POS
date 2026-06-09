"""Pillar-resolved Bayesian DFI update (single-segment).

This is the engine behind the GeoX-style "DFI modified risk" view: instead of
collapsing a DFI to one scalar ``R`` on the aggregate ``P(G, ESL)``, it resolves
the update onto **two geological channels** and reports per-pillar prior->posterior,
**without changing the headline POS**.

See ``docs/dfi_pillar_update_spec.md`` for the full derivation. The construction is
the single-segment case of the algorithm in US 10,451,762 B2 (Martinelli, Stabell,
Langlie; Schlumberger 2019) — i.e. standard Bayes' theorem + marginalisation. E-POS
does **not** implement the patent's novel multi-segment DFI-dependency-group /
reference-DFI-CPT / correlation-k method; no patent claim is practised here.

Resolution ceiling
-------------------
A DFI is a *fluid* indicator: it can only sense (a) whether a reservoir exists and
(b) what fluid fills it. It cannot tell which of charge / trap / retention failed.
So the maximum resolvable structure is two channels:

    Reservoir channel   <-> Reservoir pillar (whole)
    HC-system channel   <-> Charge . Closure . Retention  (combined; never separable)

Outcome tree (single segment)
-----------------------------
    Reservoir present (P_res):  HC          -> L_HC        (SUCCESS)
                                fluid-fail   -> L_fluidfail (reservoir present, wrong fluid)
    Reservoir absent (1-P_res): non-reservoir-> L_nonres    (RESERVOIR failure)

Multiple fluid sub-cases blend *within* their channel into one L_HC / one
L_fluidfail before reaching this engine; the "x non-reservoir" cases collapse to a
single L_nonres (fluid is moot with no reservoir).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# The three pillars that make up the HC-system channel, in the canonical order
# used elsewhere in the app. Reservoir is handled as its own whole pillar.
HC_SYSTEM_PILLARS: tuple[str, ...] = ("Charge", "Closure", "Retention")

_EPS = 1e-12


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


@dataclass(frozen=True)
class PillarUpdateResult:
    """Outcome of a single-segment pillar-resolved DFI update.

    All probabilities are in [0, 1]. ``pos_prior``/``pos_post`` are the headline
    ``P(G, ESL)`` before/after; the channel marginals decompose the move.
    """
    pos_prior: float
    pos_post: float
    p_res_prior: float
    p_res_post: float
    p_hc_prior: float
    p_hc_post: float
    # Per-leaf posterior weights P(scenario | DFI) — sum to 1.
    post_success: float
    post_fluidfail: float
    post_nonres: float

    @property
    def pos_delta_pp(self) -> float:
        return 100.0 * (self.pos_post - self.pos_prior)

    @property
    def res_delta_pp(self) -> float:
        return 100.0 * (self.p_res_post - self.p_res_prior)

    @property
    def hc_delta_pp(self) -> float:
        return 100.0 * (self.p_hc_post - self.p_hc_prior)

    @property
    def opposes_headline(self) -> bool:
        """True when the reservoir marginal moves *opposite* to the headline POS
        (e.g. POS up but reservoir down) — the key insight pillar resolution
        exposes that the aggregate-R view hides. Uses a small dead-band."""
        dp, dr = self.pos_post - self.pos_prior, self.p_res_post - self.p_res_prior
        return abs(dp) > 1e-6 and abs(dr) > 1e-6 and (dp > 0) != (dr > 0)


def pillar_resolved_update(
    pos: float,
    p_res: float,
    l_hc: float,
    l_fluidfail: float,
    l_nonres: float,
) -> PillarUpdateResult:
    """Joint single-segment DFI update over the 3-leaf outcome tree (spec §5).

    Parameters
    ----------
    pos
        Prior ``P(G, ESL)`` — the aggregate POS that already carries the ESL policy
        weight and discernibility (consumed exactly once here).
    p_res
        Prior Reservoir-pillar marginal (rolled-up ESL value). Must be ``>= pos``
        for consistency (POS includes the reservoir factor); a smaller value is
        clamped up to ``pos`` (degenerate: the HC-system prior becomes 1).
    l_hc, l_fluidfail, l_nonres
        Per-channel DFI likelihoods P(DFI | leaf). Only their *ratios* matter, so
        any common scaling is fine. Must be non-negative.

    Returns
    -------
    PillarUpdateResult
        Headline POS (provably equal to ``simm_bayes_posterior`` with the
        prior-weighted blended failure curve) plus the reservoir and HC-system
        marginals. ``p_res_post * p_hc_post == pos_post`` exactly.
    """
    pos = _clamp01(pos)
    p_res = _clamp01(p_res)
    l_hc = max(0.0, float(l_hc))
    l_fluidfail = max(0.0, float(l_fluidfail))
    l_nonres = max(0.0, float(l_nonres))

    # Consistency guard: the reservoir marginal cannot be below the overall POS.
    if p_res < pos:
        p_res = pos

    # Residual HC-system prior so that P_res * P_hc == POS exactly (spec §4).
    p_hc = pos / p_res if p_res > _EPS else 1.0
    p_hc = _clamp01(p_hc)

    # Leaf priors (sum to 1 by construction).
    pri_success = pos                 # = P_res * P_hc
    pri_fluidfail = p_res - pos       # = P_res * (1 - P_hc)
    pri_nonres = 1.0 - p_res

    # Joint update (spec §5).
    z = pri_success * l_hc + pri_fluidfail * l_fluidfail + pri_nonres * l_nonres
    if z <= _EPS:
        # Degenerate likelihoods (all ~0): no information, return the prior.
        return PillarUpdateResult(
            pos_prior=pos, pos_post=pos,
            p_res_prior=p_res, p_res_post=p_res,
            p_hc_prior=p_hc, p_hc_post=p_hc,
            post_success=pri_success, post_fluidfail=pri_fluidfail, post_nonres=pri_nonres,
        )

    post_success = pri_success * l_hc / z
    post_fluidfail = pri_fluidfail * l_fluidfail / z
    post_nonres = pri_nonres * l_nonres / z

    pos_post = post_success
    p_res_post = post_success + post_fluidfail          # marginal: reservoir present
    p_hc_post = pos_post / p_res_post if p_res_post > _EPS else 0.0

    return PillarUpdateResult(
        pos_prior=pos, pos_post=pos_post,
        p_res_prior=p_res, p_res_post=p_res_post,
        p_hc_prior=p_hc, p_hc_post=_clamp01(p_hc_post),
        post_success=post_success, post_fluidfail=post_fluidfail, post_nonres=post_nonres,
    )


def redistribute_log_proportion(
    p_hc_post: float,
    pillar_priors: dict[str, float],
) -> dict[str, float]:
    """Split the updated HC-system marginal back onto its member pillars by
    **preserving their pre-DFI log-proportions** (the patent's in-group rule,
    spec §5).

    Each pillar's posterior is ``(p_hc_post) ** w_i`` with
    ``w_i = log(prior_i) / sum_j log(prior_j)``. The product of the posteriors
    equals ``p_hc_post`` exactly, and each pillar keeps its original share of the
    combined log-probability.

    Edge cases: a pillar at probability 1 has ``log = 0`` and so takes no share of
    the update (stays at 1). If *every* pillar is 1 (no information to split) the
    update is spread as an equal geometric share.
    """
    keys = list(pillar_priors.keys())
    logs = {k: math.log(_clamp01(pillar_priors[k])) if pillar_priors[k] > _EPS else math.log(_EPS)
            for k in keys}
    total = sum(logs.values())
    p_hc_post = _clamp01(p_hc_post)

    if abs(total) <= _EPS:
        # All pillars ~1: nothing to weight by — split equally (geometric).
        n = max(1, len(keys))
        share = p_hc_post ** (1.0 / n)
        return {k: share for k in keys}

    out: dict[str, float] = {}
    for k in keys:
        w = logs[k] / total
        out[k] = _clamp01(p_hc_post ** w)
    return out
