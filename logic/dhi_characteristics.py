"""DHI characteristic scoring — Monigle 2025 alternative to the SAAM DHI Index.

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

R_HARD_CAP: float = 3.0          # Simm's empirical SAAM maximum (10–90% SR range)
R_FLOOR:    float = 1.0 / 3.0    # Symmetric lower bound (strong negative DHI)
LAPLACE_ADD: float = 0.5         # Smoothing prior — avoids zero-cell LR

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


def compute_r_char(stats: CharacteristicStats,
                   selections: dict[str, str],
                   *,
                   mode_key: str = "5_current",
                   hard_cap: float = R_HARD_CAP,
                   floor: float = R_FLOOR,
                   relative_to_middle: bool = False) -> dict:
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
    raw_r = math.exp(log_product)
    capped_r = max(floor, min(hard_cap, raw_r))
    capped = abs(raw_r - capped_r) > 1e-9
    return {
        "per_attribute_lr":  per_attribute,
        "raw_r":             raw_r,
        "r_char":            capped_r,
        "was_capped":        capped,
        "hard_cap":          hard_cap,
        "floor":             floor,
        "relative_to_middle": relative_to_middle,
        "mode_key":          mode_key,
        "n_attributes_in_r": sum(1 for k in per_attribute
                                  if active_in_mode[k].in_r_calc),
    }


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
                            relative_to_middle: bool = False) -> dict:
    """Inferred-pathway counterpart of :func:`compute_r_char`.

    ``positions``: ``{attribute_key: x}`` with x∈[0,1] (continuous slider). The
    monotone isotonic success-rate curve supplies a likelihood ratio at each
    position; the naive-independence product gives prospect-level R. Result
    dict mirrors :func:`compute_r_char` (plus ``"inferred": True``).
    """
    import math
    per_attribute: dict[str, float] = {}
    log_product = 0.0
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
    raw_r = math.exp(log_product)
    capped_r = max(floor, min(hard_cap, raw_r))
    capped = abs(raw_r - capped_r) > 1e-9
    return {
        "per_attribute_lr":   per_attribute,
        "raw_r":              raw_r,
        "r_char":             capped_r,
        "was_capped":         capped,
        "hard_cap":           hard_cap,
        "floor":              floor,
        "relative_to_middle": relative_to_middle,
        "mode_key":           mode_key,
        "inferred":           True,
        "n_attributes_in_r":  sum(1 for k in per_attribute
                                  if active_in_mode[k].in_r_calc),
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
