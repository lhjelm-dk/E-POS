"""Classic POS: Rose-style multiplicative probability of success."""

from __future__ import annotations


def classic_pos_product(pillar_probs: list[float]) -> float:
    """POS = P(Charge) × P(Closure) × P(Reservoir) × P(Retention)."""
    if not pillar_probs:
        return 0.0
    result = 1.0
    for p in pillar_probs:
        result *= max(0.0, min(1.0, float(p)))
    return result
