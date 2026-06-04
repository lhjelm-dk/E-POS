"""PROTOTYPE — Dempster–Shafer fusion of the DFI as an ESL evidence source.

This is the option-(B) research prototype discussed in review: instead of
collapsing the ESL Italian Flag to a point Pg and applying a Simm 2-state Bayes
update, treat the **DFI as just another line of evidence** in the same belief-mass
framework the ESL pillars already use, and combine it with **Dempster's rule of
combination**.

Frame of discernment Θ = {G, ¬G} (success / failure). A piece of evidence is a
mass assignment over {G, ¬G, Θ}:

    m(G)   = "green"  — committed belief in success
    m(¬G)  = "red"    — committed belief in failure
    m(Θ)   = "white"  — uncommitted / unknown mass

**The elegant part — discernibility *is* the unknown mass.** The DFI evidence is
built from two numbers already in the app:

    * DHI score  s ∈ [0,1]  — direction/strength (s>0.5 favours G, s<0.5 favours ¬G)
    * discernibility d ∈ [0,1] — how much the DFI can be trusted (Monigle's metric)

    m_DFI(G)  = d · s
    m_DFI(¬G) = d · (1 − s)
    m_DFI(Θ)  = 1 − d          ← a low-discernibility DFI is mostly "I don't know"

The advantage over the point-Bayes update is that the **green/white/red structure
is preserved through the update** (the point update collapses ESL to a single Pg and
discards the white band), and the DFI is **automatically weighted by discernibility**:

    * low discernibility (m_DFI(Θ)→1) → the fusion is ≈ a no-op; the ESL flag is
      barely changed (an ambiguous observation is correctly discounted)
    * high discernibility → the flag sharpens (white shrinks) and shifts toward G or ¬G

Note Dempster combination *reduces* white as evidence accumulates — it does not
add uncertainty; a weak DFI simply leaves the prior almost untouched.

Caveat: Dempster's rule normalises away conflict (the ``K`` term). Under highly
conflicting evidence (a confident DFI that flatly disagrees with a confident ESL)
this is known to give counter-intuitive results (Zadeh's example). ``K`` is returned
so the UI can flag high conflict.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BeliefMass:
    """A mass assignment over {G, ¬G, Θ} (green / red / white). Sums to 1."""

    g: float   # m(G)   — success
    r: float   # m(¬G)  — failure
    w: float   # m(Θ)   — unknown / uncommitted

    @property
    def bel(self) -> float:
        """Belief in success = m(G)."""
        return self.g

    @property
    def pl(self) -> float:
        """Plausibility of success = m(G) + m(Θ)."""
        return self.g + self.w

    def point(self, w_stance: float = 0.5) -> float:
        """Collapse to a point with the ESL Policy-P convention: Bel + w·white."""
        return self.g + max(0.0, min(1.0, w_stance)) * self.w


def esl_mass(total_for: float, total_against: float) -> BeliefMass:
    """ESL Italian-Flag masses for the prospect (green / red / white)."""
    g = max(0.0, min(1.0, total_for))
    r = max(0.0, min(1.0, total_against))
    w = max(0.0, 1.0 - g - r)
    return BeliefMass(g, r, w)


def dfi_mass(dhi_score: float, discernibility: float) -> BeliefMass:
    """DFI evidence as a belief mass — discernibility is the complement of the
    unknown (white) mass; the remainder is split by the DHI score.

        m(G) = d·s,  m(¬G) = d·(1−s),  m(Θ) = 1−d
    """
    s = max(0.0, min(1.0, dhi_score))
    d = max(0.0, min(1.0, discernibility))
    return BeliefMass(g=d * s, r=d * (1.0 - s), w=1.0 - d)


def dempster_combine(a: BeliefMass, b: BeliefMass) -> tuple[BeliefMass, float]:
    """Combine two masses over {G, ¬G, Θ} with Dempster's rule.

    Returns ``(combined_mass, conflict_K)``. ``K`` is the mass that the two sources
    assign to contradictory singletons (G vs ¬G); it is normalised out. High ``K``
    (→1) means the sources strongly disagree — treat the result with caution.
    """
    # Conflict: green-vs-red mass either way → empty intersection.
    K = a.g * b.r + a.r * b.g
    denom = 1.0 - K
    if denom <= 1e-12:
        # Total conflict — fall back to the uninformative vacuous mass.
        return BeliefMass(0.0, 0.0, 1.0), K
    # G survives when both pick G, or one picks G and the other is unknown.
    g = (a.g * b.g + a.g * b.w + a.w * b.g) / denom
    r = (a.r * b.r + a.r * b.w + a.w * b.r) / denom
    w = (a.w * b.w) / denom
    # numerical tidy-up
    tot = g + r + w
    if tot > 0:
        g, r, w = g / tot, r / tot, w / tot
    return BeliefMass(g, r, w), K


def fuse_dfi_into_esl(
    total_for: float, total_against: float,
    dhi_score: float, discernibility: float,
) -> tuple[BeliefMass, BeliefMass, BeliefMass, float]:
    """Full pipeline: build the ESL and DFI masses and Dempster-combine them.

    Returns ``(esl, dfi, posterior, conflict_K)`` — all three masses plus the
    conflict so the UI can show the before/after flags and a conflict warning.
    """
    esl = esl_mass(total_for, total_against)
    dfi = dfi_mass(dhi_score, discernibility)
    post, K = dempster_combine(esl, dfi)
    return esl, dfi, post, K
