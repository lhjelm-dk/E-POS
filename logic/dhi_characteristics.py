"""DHI characteristic scoring — Monigle 2025 alternative to the conceptual DHI model DHI Index.

The five current DHI quality attributes (Monigle 2025, post-2021 iCOS) are each
scored on a 5-category scale (verbal). Per-category likelihood ratios are looked
up from the drilled-prospect database statistics in
``data/dhi_characteristic_stats.json``. The product of the LRs gives a
prospect-level R (capped at 3 — Simm 2016 empirical maximum), which then drives
Simm's simple 2-state Bayesian update against the geological prior.

Key references:
  - Simm 2016 (FORCE Nov 2016) — Simple Bayesian formulation, R as L_hc/L_nohc,
    rule-of-thumb for R magnitude.
  - Monigle et al. 2025 (AAPG Bulletin 109/5) — drilled-prospect histograms and
    discernibility weighting.

Public API:
  - ``load_characteristic_stats(base_dir=None)``
  - ``category_lr(stats, attribute_key, category)``
  - ``compute_r_char(stats, selections)``
  - ``apply_discernibility(R, bucket)``
  - ``simm_bayes_posterior(prior_pg, R)``
  - ``dhi_score_from_r(R)``
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Defensible bounds (Simm 2016 empirical)
# ─────────────────────────────────────────────────────────────────────────────

R_HARD_CAP: float = 3.0          # Simm's empirical maximum (10–90% SR range)
R_FLOOR:    float = 1.0 / 3.0    # Symmetric lower bound (strong negative DHI)
LAPLACE_ADD: float = 0.5         # Smoothing prior — avoids zero-cell LR

# Discernibility-aware caps on R_char (log-symmetric).  Rationale: Simm's [1/3, 3]
# is calibrated to a *single* DFI line of evidence, but R_char is a *composite* of
# five attributes — effectively several lines, so a single-line cap is too tight
# when the geophysics is genuinely discernible. Monigle 2025's signature result is
# the strong downgrade for an expected-but-absent DHI (e.g. their Prospect B,
# GCOS 46% → iCOS 8%), which the flat [1/3, 3] cap cannot express. We widen the cap
# as discernibility rises and keep it tight (Simm) when discernibility is low, so
# the DHI can only move the prior hard when the data genuinely supports it.
DISCERNIBILITY_CAPS: dict[str, tuple[float, float]] = {
    "high":     (1.0 / 10.0, 10.0),   # composite, trustworthy geophysics → wide
    "moderate": (1.0 /  6.0,  6.0),
    "low":      (1.0 /  3.0,  3.0),   # Simm single-DFI bound
    "absent":   (1.0 /  3.0,  3.0),   # moot — d = 0 squashes R_eff to 1 anyway
}


# Default characteristic-scoring selection seeded into the sliders on first use
# (per analyst request). Keyed by attribute; values are category labels.
CHARACTERISTIC_DEFAULT_SELECTIONS: dict[str, str] = {
    "anomaly_strength":           "Very strong",
    "lateral_amplitude_contrast": "Medium",
    "fit_to_structure":           "Fair",
    "amplitude_terminations":     "Poor",
    "fluid_contact_reflection":   "Poor",
}


def correlation_discount_exponent(k: int, rho: float) -> float:
    """Effective-evidence exponent for ``k`` correlated attributes.

    The naive-Bayes composite ``R = ∏ LRᵢ`` assumes the attributes are
    *conditionally independent given class*. The five Monigle attributes are
    physically correlated (a bright anomaly tends to come with strong lateral
    contrast and a good structural fit), so the product double-counts shared
    signal and overstates the evidence.

    We discount it with the classic **design-effect / effective-sample-size**
    correction. For ``k`` observations with average pairwise correlation ``ρ``
    the effective independent count is ``k_eff = k / (1 + (k−1)·ρ)``, so the
    log-evidence should be scaled by ``f = k_eff / k = 1 / (1 + (k−1)·ρ)``::

        R_corr = exp( f · Σ log LRᵢ ) = R_naive ** f

    Limits: ``ρ = 0`` → ``f = 1`` (independent; naive Bayes unchanged);
    ``ρ → 1`` → ``f → 1/k`` (fully redundant; the k attributes count as one).
    This composes naturally with the discernibility squash ``R**d`` — both are
    exponents on R.
    """
    rho = max(0.0, min(0.99, float(rho)))
    k = max(1, int(k))
    if k == 1 or rho <= 0.0:
        return 1.0
    return 1.0 / (1.0 + (k - 1) * rho)


def cap_for_bucket(bucket_name: str, *, enabled: bool = True) -> tuple[float, float]:
    """Return ``(floor, hard_cap)`` for R_char given the discernibility bucket.

    ``enabled=False`` removes the cap entirely (``(0, inf)``) — the raw, unconstrained
    naive product, for diagnostics only.
    """
    if not enabled:
        return (0.0, float("inf"))
    return DISCERNIBILITY_CAPS.get(bucket_name, (R_FLOOR, R_HARD_CAP))


_STATS_PATH = "data/dhi_characteristic_stats.json"


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ModeStats:
    """Mode-specific category labels + success/failure counts for one attribute."""
    categories: list[str]
    success:    list[int]
    failure:    list[int]

    @property
    def n_success(self) -> int:
        return sum(self.success)

    @property
    def n_failure(self) -> int:
        return sum(self.failure)


@dataclass
class AttributeStats:
    """An attribute with mode-specific stats. Categories and counts may differ
    between modes (e.g. Monigle Fig 3 vs Fig 4 use different bucket labels and
    distinct datasets for the same physical attribute)."""
    key:           str
    display_name:  str
    role:          str = "current_5"      # current_5 | historical_quality | confidence | transitional
    active_modes:  tuple[str, ...] = ()    # which modes display this attribute
    placeholder:   bool = False            # True if counts are stubs pending data
    in_r_calc:     bool = True             # False -> contributes LR = 1 always (display-only)
    comment:       str = ""
    mode_stats:    dict = field(default_factory=dict)   # {mode_key: ModeStats}

    def stats_for(self, mode_key: str) -> ModeStats:
        if mode_key not in self.mode_stats:
            raise KeyError(f"Attribute {self.key!r} has no stats for mode {mode_key!r}")
        return self.mode_stats[mode_key]

    def categories(self, mode_key: str) -> list[str]:
        return self.stats_for(mode_key).categories

    def category_lr(self, category: str, mode_key: str) -> float:
        """Per-category likelihood ratio LR = P(c | success) / P(c | failure)
        for the given mode. Laplace-smoothed to keep zero-cell LRs finite."""
        ms = self.stats_for(mode_key)
        if category not in ms.categories:
            raise ValueError(f"Unknown category {category!r} for {self.key} in {mode_key}")
        i = ms.categories.index(category)
        s = ms.success[i] + LAPLACE_ADD
        f = ms.failure[i] + LAPLACE_ADD
        ns = ms.n_success + LAPLACE_ADD * len(ms.categories)
        nf = ms.n_failure + LAPLACE_ADD * len(ms.categories)
        p_c_succ = s / ns
        p_c_fail = f / nf
        return p_c_succ / p_c_fail


@dataclass
class DiscernibilityBucket:
    name: str
    d:    float
    description: str


@dataclass
class ModeInfo:
    key:                    str
    label:                  str
    description:            str
    attribute_roles_used:   tuple[str, ...]


@dataclass
class CharacteristicStats:
    """Loaded calibration for the characteristic-scoring DHI pathway."""
    version:        str
    source:         str
    description:    str
    attributes:     dict[str, AttributeStats]   # keyed by attribute_key
    buckets:        dict[str, DiscernibilityBucket]
    modes:          dict[str, ModeInfo]
    file_path:      str

    def attributes_for_mode(self, mode_key: str) -> dict[str, AttributeStats]:
        """All attributes (display + math) for the given mode, in JSON order."""
        return {k: a for k, a in self.attributes.items() if mode_key in a.active_modes}

    def attributes_in_r_for_mode(self, mode_key: str) -> dict[str, AttributeStats]:
        """Subset that contributes to R (excludes confidence / display-only)."""
        return {k: a for k, a in self.attributes_for_mode(mode_key).items() if a.in_r_calc}

    @property
    def default_mode_key(self) -> str:
        return "5_current"


# ─────────────────────────────────────────────────────────────────────────────
# Loader (mtime-cached, mutation-safe)
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=4)
def _load_json_cached(path_str: str, mtime: float) -> dict:
    with open(path_str, "r", encoding="utf-8") as f:
        return json.load(f)


def load_characteristic_stats(base_dir: "str | Path | None" = None) -> CharacteristicStats:
    """Load the committed Monigle 2025 characteristic-stats file."""
    root = Path(base_dir) if base_dir is not None else Path.cwd()
    path = root / _STATS_PATH
    if not path.is_file():
        raise FileNotFoundError(f"DHI characteristic stats not found: {path}")
    raw = copy.deepcopy(_load_json_cached(str(path), path.stat().st_mtime))

    attrs: dict[str, AttributeStats] = {}
    for key, a in raw["attributes"].items():
        mode_stats: dict[str, ModeStats] = {}
        for mk, ms in (a.get("mode_stats") or {}).items():
            mode_stats[mk] = ModeStats(
                categories=list(ms["categories"]),
                success=[int(x) for x in ms["success"]],
                failure=[int(x) for x in ms["failure"]],
            )
        attrs[key] = AttributeStats(
            key=key,
            display_name=a["display_name"],
            role=str(a.get("role", "current_5")),
            active_modes=tuple(a.get("active_modes", [])),
            placeholder=bool(a.get("placeholder", False)),
            in_r_calc=bool(a.get("in_r_calc", True)),
            comment=str(a.get("comment", "")),
            mode_stats=mode_stats,
        )
    buckets: dict[str, DiscernibilityBucket] = {}
    for bname, b in raw["discernibility"]["buckets"].items():
        buckets[bname] = DiscernibilityBucket(
            name=bname, d=float(b["d"]), description=b.get("description", "")
        )
    modes: dict[str, ModeInfo] = {}
    for mkey, m in (raw.get("modes") or {}).items():
        modes[mkey] = ModeInfo(
            key=mkey,
            label=str(m.get("label", mkey)),
            description=str(m.get("description", "")),
            attribute_roles_used=tuple(m.get("attribute_roles_used", [])),
        )
    return CharacteristicStats(
        version     = str(raw.get("version", "unknown")),
        source      = str(raw.get("source", "")),
        description = str(raw.get("description", "")),
        attributes  = attrs,
        buckets     = buckets,
        modes       = modes,
        file_path   = str(path),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Combination math
# ─────────────────────────────────────────────────────────────────────────────

def _middle_category(attr: AttributeStats, mode_key: str) -> str:
    """Middle category label for the given mode (slider-neutral position)."""
    cats = attr.categories(mode_key)
    return cats[len(cats) // 2]


def _assemble_r_result(per_attribute: dict, log_product: float, n_in_r: int,
                       hard_cap: float, floor: float, relative_to_middle: bool,
                       mode_key: str, corr_rho: float, *, inferred: bool = False) -> dict:
    """Shared tail for both R pathways: naive product → correlation discount → cap.

    ``raw_r`` is the naive-independence product ``exp(Σ log LR)``. When
    ``corr_rho > 0`` the log-evidence is scaled by the effective-evidence
    exponent ``f = 1/(1+(k−1)ρ)`` (see :func:`correlation_discount_exponent`),
    giving ``discounted_r = raw_r ** f``. The cap is then applied to the
    discounted value, so ``r_char`` is what drives the Bayesian update.
    """
    import math
    raw_r = math.exp(log_product)
    f = correlation_discount_exponent(n_in_r, corr_rho)
    discounted_r = math.exp(log_product * f)            # == raw_r ** f
    capped_r = max(floor, min(hard_cap, discounted_r))
    capped = abs(discounted_r - capped_r) > 1e-9
    out = {
        "per_attribute_lr":   per_attribute,
        "raw_r":              raw_r,
        "discounted_r":       discounted_r,
        "corr_rho":           max(0.0, min(0.99, float(corr_rho))),
        "corr_exponent":      f,
        "r_char":             capped_r,
        "was_capped":         capped,
        "hard_cap":           hard_cap,
        "floor":              floor,
        "relative_to_middle": relative_to_middle,
        "mode_key":           mode_key,
        "n_attributes_in_r":  n_in_r,
    }
    if inferred:
        out["inferred"] = True
    return out


def compute_r_char(stats: CharacteristicStats,
                   selections: dict[str, str],
                   *,
                   mode_key: str = "5_current",
                   hard_cap: float = R_HARD_CAP,
                   floor: float = R_FLOOR,
                   relative_to_middle: bool = False,
                   corr_rho: float = 0.0) -> dict:
    """Combine per-attribute LRs into a prospect-level R (naive-independence product).

    Only attributes that (a) are active in the chosen ``mode_key`` AND (b) have
    ``in_r_calc=True`` contribute to R. Any display-only attributes are ignored
    for the math but their LR is still reported in ``per_attribute_lr`` for the
    radar plot.

    **Default (``relative_to_middle=False``):** each attribute's LR is the
    base-rate-relative Bayesian likelihood ratio ``odds(category) / odds(base)``
    — the conceptually correct evidential strength (a category whose success rate
    equals the dataset base rate contributes LR = 1; one above it lifts, below it
    downgrades). Set ``relative_to_middle=True`` for the legacy slider-UX anchoring
    that forces the *middle verbal category* to LR = 1 (so an all-middle selection
    yields R = 1). The legacy mode discards genuine evidence when the middle
    category is itself far from the base rate (e.g. the non-monotonic
    fluid-contact-reflection attribute, where "Fair" sits at 82 % vs a 56 % base).

    ``selections``: ``{attribute_key: category_label}``. Attributes missing from
    selections contribute LR = 1.
    """
    import math
    per_attribute: dict[str, float] = {}
    log_product = 0.0
    n_in_r = 0
    active_in_mode = stats.attributes_for_mode(mode_key)
    for key, attr in active_in_mode.items():
        cat = selections.get(key)
        if cat is None or cat not in attr.categories(mode_key):
            per_attribute[key] = 1.0
            continue
        lr = attr.category_lr(cat, mode_key)
        if relative_to_middle:
            mid_lr = attr.category_lr(_middle_category(attr, mode_key), mode_key)
            lr = lr / mid_lr if mid_lr > 0 else 1.0
        per_attribute[key] = lr
        # Confidence/display-only attributes don't contribute to R, even if scored
        if attr.in_r_calc:
            log_product += math.log(max(lr, 1e-12))
            n_in_r += 1
    return _assemble_r_result(per_attribute, log_product, n_in_r, hard_cap, floor,
                              relative_to_middle, mode_key, corr_rho)


# ─────────────────────────────────────────────────────────────────────────────
# Inferred (smoothed / monotone) success-rate pathway
# ─────────────────────────────────────────────────────────────────────────────
#
# RAW pathway uses the discrete per-category likelihood ratios verbatim — which
# faithfully reproduces empirical non-monotonicity (e.g. Monigle Fig 4 fluid-
# contact-reflection where Fair 82% out-performs Good 67%).
#
# INFERRED pathway treats the categories as ordinal anchors of an underlying
# monotone success-rate curve. It (1) Laplace-smooths each category success
# rate, (2) enforces non-decreasing order with *weighted isotonic regression*
# (pool-adjacent-violators, weighted by category n) so Good ≥ Fair, then
# (3) interpolates a near-continuous curve so the slider is seamless. The
# likelihood ratio at any slider position x∈[0,1] is recovered from the
# success-rate odds:
#
#     LR(x) = [ SR(x) / (1 - SR(x)) ] / ( N_HC / N_dry )
#
# and, when ``relative_to_middle`` is on, divided by LR at the middle anchor so
# the neutral slider yields LR = 1 (the base-rate odds cancels).


def _laplace_success_rate_anchors(attr: AttributeStats,
                                  mode_key: str) -> "tuple[list[float], list[float]]":
    """Per-category Laplace-smoothed success rate SR_c and weights n_c.

    ``SR_c = (s+a) / (s+f+2a)``  with ``a = LAPLACE_ADD``;
    weight ``n_c = s+f+2a`` (used by the isotonic regression).
    """
    ms = attr.stats_for(mode_key)
    rates: list[float] = []
    weights: list[float] = []
    for s, f in zip(ms.success, ms.failure):
        n = s + f + 2.0 * LAPLACE_ADD
        rates.append((s + LAPLACE_ADD) / n)
        weights.append(n)
    return rates, weights


def _pava_isotonic(values: "list[float]", weights: "list[float]") -> "list[float]":
    """Weighted isotonic regression (non-decreasing) via pool-adjacent-violators.

    Returns a list the same length as ``values`` whose entries are non-decreasing
    and are the weighted L2 projection of ``values`` onto the monotone cone.
    Already-monotone input is returned unchanged.
    """
    stack: list[list[float]] = []   # each block: [mean, total_weight, count]
    for v, w in zip(values, weights):
        stack.append([float(v), float(w), 1.0])
        while len(stack) > 1 and stack[-2][0] > stack[-1][0]:
            v2, w2, c2 = stack.pop()
            v1, w1, c1 = stack.pop()
            nw = w1 + w2
            stack.append([(v1 * w1 + v2 * w2) / nw, nw, c1 + c2])
    out: list[float] = []
    for mean, _w, count in stack:
        out.extend([mean] * int(count))
    return out


def _interp_uniform(x: float, anchors: "list[float]") -> float:
    """Linear interpolation of ``anchors`` (placed at i/(K-1)) at position x∈[0,1]."""
    k = len(anchors)
    if k == 0:
        return 0.0
    if k == 1:
        return anchors[0]
    x = max(0.0, min(1.0, x))
    pos = x * (k - 1)
    i = int(pos)
    if i >= k - 1:
        return anchors[-1]
    t = pos - i
    return anchors[i] * (1.0 - t) + anchors[i + 1] * t


def inferred_success_curve(attr: AttributeStats, mode_key: str) -> "list[float]":
    """Monotone (isotonic) Laplace-smoothed success-rate anchors, one per category."""
    rates, weights = _laplace_success_rate_anchors(attr, mode_key)
    return _pava_isotonic(rates, weights)


def _base_success_odds(attr: AttributeStats, mode_key: str) -> float:
    """Overall base-rate odds N_HC / N_dry (Laplace-smoothed totals)."""
    ms = attr.stats_for(mode_key)
    k = len(ms.categories)
    ns = ms.n_success + LAPLACE_ADD * k
    nf = ms.n_failure + LAPLACE_ADD * k
    return ns / nf if nf > 0 else 1.0


def inferred_success_rate_at(attr: AttributeStats, mode_key: str, x: float) -> float:
    """Interpolated monotone success rate at slider position x∈[0,1]."""
    return _interp_uniform(x, inferred_success_curve(attr, mode_key))


def inferred_lr_at(attr: AttributeStats, mode_key: str, x: float,
                   *, relative_to_middle: bool = False) -> float:
    """Likelihood ratio at continuous slider position x∈[0,1] (inferred pathway)."""
    mono = inferred_success_curve(attr, mode_key)
    base = _base_success_odds(attr, mode_key)
    sr = _interp_uniform(x, mono)
    sr = min(max(sr, 1e-6), 1.0 - 1e-6)
    lr = (sr / (1.0 - sr)) / base if base > 0 else 1.0
    if relative_to_middle:
        k = len(mono)
        mid_x = (k // 2) / (k - 1) if k > 1 else 0.5
        sr_m = _interp_uniform(mid_x, mono)
        sr_m = min(max(sr_m, 1e-6), 1.0 - 1e-6)
        lr_mid = (sr_m / (1.0 - sr_m)) / base if base > 0 else 1.0
        lr = lr / lr_mid if lr_mid > 0 else 1.0
    return lr


def compute_r_char_inferred(stats: CharacteristicStats,
                            positions: "dict[str, float]",
                            *,
                            mode_key: str = "5_current",
                            hard_cap: float = R_HARD_CAP,
                            floor: float = R_FLOOR,
                            relative_to_middle: bool = False,
                            corr_rho: float = 0.0) -> dict:
    """Inferred-pathway counterpart of :func:`compute_r_char`.

    ``positions``: ``{attribute_key: x}`` with x∈[0,1] (continuous slider). The
    monotone isotonic success-rate curve supplies a likelihood ratio at each
    position; the naive-independence product gives prospect-level R. Result
    dict mirrors :func:`compute_r_char` (plus ``"inferred": True``).
    """
    import math
    per_attribute: dict[str, float] = {}
    log_product = 0.0
    n_in_r = 0
    active_in_mode = stats.attributes_for_mode(mode_key)
    for key, attr in active_in_mode.items():
        x = positions.get(key)
        if x is None:
            per_attribute[key] = 1.0
            continue
        lr = inferred_lr_at(attr, mode_key, float(x),
                            relative_to_middle=relative_to_middle)
        per_attribute[key] = lr
        if attr.in_r_calc:
            log_product += math.log(max(lr, 1e-12))
            n_in_r += 1
    return _assemble_r_result(per_attribute, log_product, n_in_r, hard_cap, floor,
                              relative_to_middle, mode_key, corr_rho, inferred=True)


def score_class_logr_moments(stats: CharacteristicStats, mode_key: str = "5_current",
                             *, inferred: bool = False,
                             relative_to_middle: bool = False) -> dict:
    """Per-class mean & variance of the composite log-LR ``L = Σ log LRᵢ`` over the
    Monigle drilled population, under **success** and under **failure**.

    Under the naive-independence model each attribute's category is drawn from
    ``P(c|class)`` (Laplace-smoothed, exactly as the LRs are built), so:

        E_class[L]   = Σᵢ Σ_c P(c|class) · log LRᵢ(c)
        Var_class[L] = Σᵢ ( Σ_c P(c|class) · log LRᵢ(c)²  −  E_i² )   (independence)

    Returns ``{"succ": (μ, var), "fail": (μ, var), "k": n_in_r}`` in log-R space.
    These moments are population properties (they do *not* depend on the current
    prospect's slider selections); the prospect is a read-off point at its own L.
    """
    import math
    attrs = stats.attributes_in_r_for_mode(mode_key)   # only R-contributing attrs
    mu = {"succ": 0.0, "fail": 0.0}
    var = {"succ": 0.0, "fail": 0.0}
    k = 0
    for key, attr in attrs.items():
        ms = attr.stats_for(mode_key)
        cats = ms.categories
        K = len(cats)
        if K == 0:
            continue
        # Per-category log-LR (raw discrete, or inferred-monotone at the anchors)
        loglrs: list[float] = []
        if inferred:
            for i in range(K):
                x = i / (K - 1) if K > 1 else 0.5
                lr = inferred_lr_at(attr, mode_key, x, relative_to_middle=relative_to_middle)
                loglrs.append(math.log(max(lr, 1e-12)))
        else:
            mid_lr = (attr.category_lr(_middle_category(attr, mode_key), mode_key)
                      if relative_to_middle else 1.0)
            for c in cats:
                lr = attr.category_lr(c, mode_key)
                if relative_to_middle and mid_lr > 0:
                    lr = lr / mid_lr
                loglrs.append(math.log(max(lr, 1e-12)))
        # Class-conditional category probabilities (Laplace-smoothed)
        ns = ms.n_success + LAPLACE_ADD * K
        nf = ms.n_failure + LAPLACE_ADD * K
        for cls, ntot, counts in (("succ", ns, ms.success), ("fail", nf, ms.failure)):
            e = e2 = 0.0
            for i in range(K):
                p = (counts[i] + LAPLACE_ADD) / ntot if ntot > 0 else 1.0 / K
                e += p * loglrs[i]
                e2 += p * loglrs[i] * loglrs[i]
            mu[cls] += e
            var[cls] += max(0.0, e2 - e * e)
        k += 1
    return {"succ": (mu["succ"], var["succ"]), "fail": (mu["fail"], var["fail"]), "k": k}


def score_class_gaussians(stats: CharacteristicStats, mode_key: str = "5_current",
                          *, inferred: bool = False, relative_to_middle: bool = False,
                          corr_rho: float = 0.0) -> dict:
    """Gaussian (μ, σ) in log-R space for the success and failure populations.

    Wraps :func:`score_class_logr_moments` and folds in the correlation-independence
    discount ``f`` (so the curves live on the *same* discounted log-R axis as the
    prospect's R_disc read-off). With k independent attributes the CLT makes L
    approximately Gaussian under each class — the two bells mirror the Custom-tool
    P(DFI|HC) / P(DFI|No-HC) curves, but here on the DHI-score axis.

    Returns ``{"succ": (μ, σ), "fail": (μ, σ), "k": k, "corr_exponent": f}``.
    """
    import math
    m = score_class_logr_moments(stats, mode_key, inferred=inferred,
                                 relative_to_middle=relative_to_middle)
    f = correlation_discount_exponent(m["k"], corr_rho)
    out: dict = {"k": m["k"], "corr_exponent": f}
    for cls in ("succ", "fail"):
        mu, vr = m[cls]
        out[cls] = (mu * f, max(math.sqrt(max(vr, 1e-12)) * f, 1e-6))
    return out


def score_class_convolution_raw(stats: CharacteristicStats, mode_key: str = "5_current",
                                *, relative_to_middle: bool = False, corr_rho: float = 0.0,
                                nbins: int = 44, max_cells: int = 300_000) -> "dict | None":
    """**Exact** naive-independence distribution of the composite DHI score under
    each class — no CLT approximation.

    Convolves the per-attribute *discrete* log-LR distributions: every combination
    of one category per attribute is a cell with probability ``∏ P(cᵢ|class)`` and
    composite ``L = Σ log LRᵢ(cᵢ)`` (then discounted by the correlation exponent
    ``f`` and mapped to the score ``σ(f·L)``). Binning those cells gives a lumpy,
    possibly multi-modal "rugged" distribution — the literal raw-evidence counterpart
    of the smooth Gaussian :func:`score_class_gaussians`.

    Returns ``{"centers", "succ", "fail", "k", "corr_exponent", "n_cells"}`` with
    densities (mass / bin-width, so each integrates to ~1 over [0,1]). Returns
    ``None`` when the cell count exceeds ``max_cells`` (caller should fall back to
    the Gaussian model).
    """
    import math
    import itertools
    attrs = list(stats.attributes_in_r_for_mode(mode_key).values())
    # Guard against combinatorial blow-up (e.g. a many-attribute mode).
    n_cells = 1
    for attr in attrs:
        n_cells *= max(1, len(attr.categories(mode_key)))
    if n_cells > max_cells:
        return None
    # Per-attribute rows: (log LR, P(cat|success), P(cat|failure)).
    per_attr: list[list[tuple[float, float, float]]] = []
    for attr in attrs:
        ms = attr.stats_for(mode_key)
        K = len(ms.categories)
        ns = ms.n_success + LAPLACE_ADD * K
        nf = ms.n_failure + LAPLACE_ADD * K
        mid_lr = (attr.category_lr(_middle_category(attr, mode_key), mode_key)
                  if relative_to_middle else 1.0)
        rows: list[tuple[float, float, float]] = []
        for i, c in enumerate(ms.categories):
            lr = attr.category_lr(c, mode_key)
            if relative_to_middle and mid_lr > 0:
                lr = lr / mid_lr
            ps = (ms.success[i] + LAPLACE_ADD) / ns if ns > 0 else 1.0 / K
            pf = (ms.failure[i] + LAPLACE_ADD) / nf if nf > 0 else 1.0 / K
            rows.append((math.log(max(lr, 1e-12)), ps, pf))
        per_attr.append(rows)
    k = len(per_attr)
    f = correlation_discount_exponent(k, corr_rho)
    nbins = max(4, int(nbins))
    succ = [0.0] * nbins
    fail = [0.0] * nbins
    for combo in itertools.product(*per_attr):
        L = 0.0
        ps = pf = 1.0
        for lr, p_s, p_f in combo:
            L += lr
            ps *= p_s
            pf *= p_f
        s = 1.0 / (1.0 + math.exp(-f * L))
        b = min(nbins - 1, max(0, int(s * nbins)))
        succ[b] += ps
        fail[b] += pf
    bw = 1.0 / nbins
    centers = [(j + 0.5) * bw for j in range(nbins)]
    return {
        "centers": centers,
        "succ": [v / bw for v in succ],
        "fail": [v / bw for v in fail],
        "k": k, "corr_exponent": f, "n_cells": n_cells,
    }


def apply_discernibility(r: float, bucket: DiscernibilityBucket) -> float:
    """Squash R toward 1 by the discernibility weight ``d`` (Monigle 2025).

    ``R_effective = R ** d`` for d ∈ [0, 1].  d=1 → unchanged; d=0 → R=1 (no effect).
    Thin wrapper over :func:`logic.dfi_simm.apply_discernibility` that unpacks the
    ``DiscernibilityBucket``.
    """
    return _simm_apply_discernibility(r, bucket.d)


# ─────────────────────────────────────────────────────────────────────────────
# Simm 2016 two-state primitives — canonical home is ``logic.dfi_simm``.
# Re-exported here so existing ``from logic.dhi_characteristics import …`` sites
# keep working and all three DFI pathways share one implementation.
# ─────────────────────────────────────────────────────────────────────────────
from logic.dfi_simm import (  # noqa: E402  (re-export after class defs)
    simm_bayes_posterior,
    dhi_score_from_r,
    simm_rule_of_thumb,
    SIMM_R_BANDS,
    SIMM_RULE_OF_THUMB,
    apply_discernibility as _simm_apply_discernibility,
)


def characteristic_channels(r_char: float):
    """Express the characteristic (Monigle 2025) evidence in the shared channel
    language. It is a single success/failure curve pair, so it is **aggregate-only**
    (a 2-channel model cannot separate reservoir failure from fluid failure) and
    updates only the headline POS.
    """
    from logic.dfi_pillar_update import aggregate_channels
    return aggregate_channels(r_char, "Characteristic scoring (Monigle 2025)")
