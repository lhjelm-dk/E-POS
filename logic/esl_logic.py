from __future__ import annotations

from typing import Iterable, Tuple


def _extract_support(node) -> Tuple[float, float]:
    if isinstance(node, dict):
        return float(node.get("support_for", 0.0)), float(node.get("support_against", 0.0))
    if isinstance(node, (list, tuple)) and len(node) == 2:
        return float(node[0]), float(node[1])
    raise ValueError("Node must be dict with support_for/support_against or a 2-tuple.")


def apply_and_logic(nodes: Iterable) -> Tuple[float, float]:
    """Weakest link: Green=min(for), Red=max(against)."""
    supports = [_extract_support(n) for n in nodes]
    if not supports:
        return 0.0, 0.0
    return min(s[0] for s in supports), max(s[1] for s in supports)


def apply_or_logic(nodes: Iterable) -> Tuple[float, float]:
    """Any path: Green=max(for), Red=min(against)."""
    supports = [_extract_support(n) for n in nodes]
    if not supports:
        return 0.0, 0.0
    return max(s[0] for s in supports), min(s[1] for s in supports)


def apply_product_logic(nodes: Iterable) -> Tuple[float, float]:
    """Independent pillars: S_total = ∏ S_i, R_total = 1 - ∏(1 - R_i)."""
    supports = [_extract_support(n) for n in nodes]
    if not supports:
        return 0.0, 0.0
    s_prod = 1.0
    for s, _ in supports:
        s_prod *= max(0.0, min(1.0, s))
    r_prod = 1.0
    for _, r in supports:
        r_prod *= max(0.0, min(1.0, 1.0 - r))
    return s_prod, 1.0 - r_prod


def calculate_uncertainty(support_for: float, support_against: float) -> Tuple[float, bool]:
    """Returns uncertainty and conflict flag (for + against > 1)."""
    total = float(support_for) + float(support_against)
    conflict = total > 1.0
    uncertainty = max(0.0, 1.0 - total)
    return uncertainty, conflict
