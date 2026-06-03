"""
Shared ESL aggregation: group-by-label conditional pillars, product across categories, then total.
Used by Prospect Hub logic table, overview table, and should match the main ESL tab math.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from logic.esl_logic import apply_and_logic, apply_product_logic
from logic.session_keys import SK

# ── ESL operator constants (work on S_for/S_against mass pairs) ───────────────
# Canonical operator strings (session keys mode_cond_*, mode_group_*)
ESL_MODE_OPTIONS: tuple[str, ...] = (
    "ESL-IPT (sufficiency/dependency)",
    "ESL-ALL (min/min)",
    "ESL-ANY (max/max)",
    "Product (Π)",
    "Mean",
)
DEFAULT_ESL_MODE = "ESL-ALL (min/min)"
_ESL_VALID = frozenset(ESL_MODE_OPTIONS)

# ── Classic POS operator constants (work on Policy POS probability values) ────
# These are independent of ESL operators — stored under classic_mode_* session keys.
CLASSIC_POS_OPERATOR_OPTIONS: tuple[str, ...] = (
    "Min (weakest link)",   # Traditional AAPG/Rose: worst element dominates
    "Product (Π)",          # Independent factors multiplied (Rose cross-factor)
    "Mean",                 # Arithmetic average
    "Max",                  # Any alternative suffices (disjunctive)
)
DEFAULT_CLASSIC_POS_MODE = "Min (weakest link)"
_CLASSIC_VALID = frozenset(CLASSIC_POS_OPERATOR_OPTIONS)

# Recommendation: when user sets an ESL operator, suggest the closest Classic POS equivalent.
ESL_TO_CLASSIC_RECOMMENDATION: dict[str, str] = {
    "ESL-ALL (min/min)":               "Min (weakest link)",
    "ESL-ANY (max/max)":               "Max",
    "ESL-IPT (sufficiency/dependency)": "Product (Π)",
    "Product (Π)":                     "Product (Π)",
    "Mean":                            "Mean",
}


def group_by_label(elements: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for element in elements:
        groups.setdefault(element["label"], []).append(element)
    return groups


def combine_ipt(nodes: list[dict], dependency: float) -> tuple[float, float]:
    def _side(key_support: str, key_suff: str) -> float:
        values = [
            max(0.0, min(1.0, float(n.get(key_support, 0.0)) * float(n.get(key_suff, 1.0))))
            for n in nodes
        ]
        if not values:
            return 0.0
        ind = 1.0
        for v in values:
            ind *= 1.0 - v
        ind = 1.0 - ind
        dep = max(values)
        return (1.0 - dependency) * ind + dependency * dep

    return _side("support_for", "suff_for"), _side("support_against", "suff_against")


def _get_support(node: dict) -> tuple[float, float]:
    return float(node["support_for"]), float(node["support_against"])


def combine_with_mode(nodes: list[dict], mode: str, dependency: float = 0.0) -> tuple[float, float]:
    """Combine sibling nodes using ESL / Classic operator label (Classic retained for CSV import & Classic POS paths)."""
    supports = [_get_support(n) for n in nodes]
    if not supports:
        return 0.0, 0.0
    if mode.startswith("ESL-IPT"):
        return combine_ipt(nodes, dependency)
    if mode.startswith("ESL-ANY"):
        return max(s[0] for s in supports), max(s[1] for s in supports)
    if mode.startswith("ESL-ALL"):
        return min(s[0] for s in supports), min(s[1] for s in supports)
    if mode.startswith("Classic (max/max)"):
        return max(s[0] for s in supports), max(s[1] for s in supports)
    if mode.startswith("Classic (avg)") or mode.startswith("Mean"):
        n = len(supports)
        return (
            sum(s[0] for s in supports) / n,
            sum(s[1] for s in supports) / n,
        )
    if mode.startswith("Product"):
        # Multiplicative (Rose product rule): S_total = Π(sf_i),
        # R_total = 1 − Π(1 − sa_i)  ← DeMorgan complement, matches apply_product_logic
        sf = 1.0
        r_prod = 1.0
        for s in supports:
            sf *= max(0.0, min(1.0, s[0]))
            r_prod *= max(0.0, min(1.0, 1.0 - s[1]))
        return sf, 1.0 - r_prod
    return apply_and_logic(nodes)


def compute_conditional_results(
    conditional: dict[str, list[dict]],
    get_mode: Callable[[str], str],
    get_dep: Callable[[str], float],
) -> dict[str, dict[str, float]]:
    """Aggregate each conditional category from grouped sub-elements to a single (for, against) pair."""
    conditional_results: dict[str, dict[str, float]] = {}
    for category, elements in conditional.items():
        grouped = group_by_label(elements)
        group_results: list[dict] = []
        for group_label, group_elements in grouped.items():
            if len(group_elements) == 1:
                e = group_elements[0]
                group_results.append(
                    {"support_for": e["support_for"], "support_against": e["support_against"]}
                )
            else:
                f, a = combine_with_mode(
                    group_elements,
                    get_mode(SK.esl_group_mode(category, group_label)),
                    get_dep(SK.esl_group_dependency(category, group_label)),
                )
                group_results.append({"support_for": f, "support_against": a})
        f, a = combine_with_mode(
            group_results,
            get_mode(SK.esl_mode(category)),
            get_dep(SK.esl_dependency(category)),
        )
        conditional_results[category] = {"for": f, "against": a}
    return conditional_results


@dataclass(frozen=True)
class ESLRollup:
    conditional_results: dict[str, dict[str, float]]
    # Per-pillar play masses — dynamic dict, keys are pillar_ids (e.g. "Charge", "Closure" …)
    pillar_for: dict[str, float]
    pillar_against: dict[str, float]
    # Aggregated totals
    play_for: float
    play_against: float
    conditional_for: float
    conditional_against: float
    total_for: float
    total_against: float


def compute_esl_rollup(
    play: dict,
    conditional: dict[str, list[dict]],
    get_mode: Callable[[str], str],
    get_dep: Callable[[str], float],
) -> ESLRollup:
    """Full play × conditional product tree (same math as hub / overview).

    Fully dynamic — works with any set of pillar names, not just the legacy 4.
    """
    conditional_results = compute_conditional_results(conditional, get_mode, get_dep)

    # Per-pillar play masses (dynamic)
    pillar_for: dict[str, float] = {}
    pillar_against: dict[str, float] = {}
    play_nodes: list[dict] = []
    for pid, pdata in play.items():
        sf = float(pdata.get("support_for", 0.5))
        sa = float(pdata.get("support_against", 0.1))
        pillar_for[pid] = sf
        pillar_against[pid] = sa
        play_nodes.append({"support_for": sf, "support_against": sa})

    play_for, play_against = apply_product_logic(play_nodes) if play_nodes else (0.5, 0.1)

    cond_nodes = [
        {"support_for": v["for"], "support_against": v["against"]}
        for v in conditional_results.values()
    ]
    conditional_for, conditional_against = (
        apply_product_logic(cond_nodes) if cond_nodes else (0.5, 0.1)
    )
    total_for, total_against = apply_product_logic(
        [
            {"support_for": play_for, "support_against": play_against},
            {"support_for": conditional_for, "support_against": conditional_against},
        ]
    )

    return ESLRollup(
        conditional_results=conditional_results,
        pillar_for=pillar_for,
        pillar_against=pillar_against,
        play_for=play_for,
        play_against=play_against,
        conditional_for=conditional_for,
        conditional_against=conditional_against,
        total_for=total_for,
        total_against=total_against,
    )


def make_session_mode_dep_getters(session_state) -> tuple[Callable[[str], str], Callable[[str], float]]:
    """get_mode / get_dep reading Streamlit session_state with ESL mode validation."""

    def get_mode(key: str) -> str:
        v = session_state.get(key, DEFAULT_ESL_MODE)
        return v if v in _ESL_VALID else DEFAULT_ESL_MODE

    def get_dep(key: str) -> float:
        return float(session_state.get(key, 0.0))

    return get_mode, get_dep


# ── Classic POS combination (operates on probability values, not ESL masses) ──

def combine_classic_pos(probs: list[float], mode: str) -> float:
    """Combine Policy POS values using a Classic POS operator.

    Unlike combine_with_mode() which operates on (S_for, S_against) mass pairs,
    this function takes plain probability values [0, 1] and applies the chosen
    Classic POS combination rule.

    Args:
        probs: list of Policy POS values (each in [0, 1])
        mode:  one of CLASSIC_POS_OPERATOR_OPTIONS

    Returns:
        Combined POS ∈ [0, 1]
    """
    if not probs:
        return 0.0
    p = [max(0.0, min(1.0, float(x))) for x in probs]
    if mode == "Max":
        return max(p)
    if mode == "Mean":
        return sum(p) / len(p)
    if mode.startswith("Product"):
        result = 1.0
        for v in p:
            result *= v
        return result
    # Default: "Min (weakest link)"
    return min(p)


def make_session_classic_mode_getter(session_state) -> Callable[[str], str]:
    """Return a getter for Classic POS operator keys, with validation and default."""

    def get_classic_mode(key: str) -> str:
        v = session_state.get(key, DEFAULT_CLASSIC_POS_MODE)
        return v if v in _CLASSIC_VALID else DEFAULT_CLASSIC_POS_MODE

    return get_classic_mode
