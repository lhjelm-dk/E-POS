"""Bayesian Network logic: 8-node causal DAG, CPT, belief propagation. Step 5."""

from __future__ import annotations

from typing import Any

try:
    from pgmpy.models import DiscreteBayesianNetwork
    from pgmpy.factors.discrete import TabularCPD
    from pgmpy.inference import VariableElimination

    PGMPY_AVAILABLE = True
except ImportError:
    PGMPY_AVAILABLE = False
    DiscreteBayesianNetwork = None
    TabularCPD = None
    VariableElimination = None


STATES = ["Adequate", "Inadequate"]
# BN graph uses internal geological names, NOT the ESL pillar ids.
# "ClosureGeometry" ↔ pillar "Trap" (display "Closure"); "Retention" ↔ pillar "Retention".
ROOT_NODES = ["SourceMaturity", "ClosureGeometry", "ReservoirPresence", "Retention"]
CHILD_NODES = ["Charge", "SealIntegrity", "ReservoirQuality"]
ALL_NODES = ROOT_NODES + CHILD_NODES + ["Discovery"]

# Explicit mapping from ESL pillar_id → positional slot in build_petroleum_bn().
# Slot 0 = p_source, 1 = p_closure, 2 = p_reservoir, 3 = p_retention.
# "Closure" is accepted as an alias for the display name of "Trap".
# Any pillar_id NOT listed here → slot not mapped → BN uses neutral prior 0.5.
N_BN_ROOT_SLOTS: int = 4
BN_PILLAR_SLOT: dict[str, int] = {
    "Charge":    0,   # SourceMaturity
    "Trap":      1,   # ClosureGeometry
    "Closure":   1,   # display-name alias for Trap
    "Reservoir": 2,   # ReservoirPresence
    "Retention": 3,   # Retention
}

# Default CPT values (user-editable via UI in methods/bayesian.py)
DEFAULT_CPTS = {
    # Charge: [P(A|SrcA,ClsA), P(A|SrcA,ClsI), P(A|SrcI,ClsA), P(A|SrcI,ClsI)]
    "Charge": [0.85, 0.05, 0.10, 0.01],
    # SealIntegrity: [P(A|ClsA), P(A|ClsI)]
    "SealIntegrity": [0.75, 0.35],
    # ReservoirQuality: [P(A|ResA), P(A|ResI)]
    "ReservoirQuality": [0.70, 0.02],
}

def build_petroleum_bn(
    p_source: float = 0.6,
    p_closure: float = 0.7,
    p_reservoir: float = 0.8,
    p_retention: float = 0.7,
    cpt_overrides: dict | None = None,
) -> tuple[Any, Any] | tuple[None, None]:
    """Build 8-node causal petroleum BN with geological dependencies.

    Root nodes: SourceMaturity, ClosureGeometry, ReservoirPresence, Retention.
    Derived: Charge (SourceMaturity, ClosureGeometry), SealIntegrity (ClosureGeometry),
    ReservoirQuality (ReservoirPresence). Discovery = AND of Charge, SealIntegrity,
    ReservoirQuality, Retention.

    Returns (model, inference) or (None, None) if pgmpy not available.
    """
    if not PGMPY_AVAILABLE:
        return None, None

    cpts = dict(DEFAULT_CPTS)
    if cpt_overrides:
        cpts.update(cpt_overrides)

    model = DiscreteBayesianNetwork(
        [
            ("SourceMaturity", "Charge"),
            ("ClosureGeometry", "Charge"),
            ("ClosureGeometry", "SealIntegrity"),
            ("ReservoirPresence", "ReservoirQuality"),
            ("Charge", "Discovery"),
            ("SealIntegrity", "Discovery"),
            ("ReservoirQuality", "Discovery"),
            ("Retention", "Discovery"),
        ]
    )

    sn = {n: STATES for n in ALL_NODES}

    # Root node priors
    for node, p in [
        ("SourceMaturity", p_source),
        ("ClosureGeometry", p_closure),
        ("ReservoirPresence", p_reservoir),
        ("Retention", p_retention),
    ]:
        model.add_cpds(
            TabularCPD(
                variable=node,
                variable_card=2,
                values=[[p], [1 - p]],
                state_names=sn,
            )
        )

    # Charge CPT (2 parents: SourceMaturity, ClosureGeometry)
    # Order: (SrcA,ClsA), (SrcA,ClsI), (SrcI,ClsA), (SrcI,ClsI)
    cv = cpts["Charge"]
    model.add_cpds(
        TabularCPD(
            variable="Charge",
            variable_card=2,
            values=[
                [cv[0], cv[1], cv[2], cv[3]],
                [1 - cv[0], 1 - cv[1], 1 - cv[2], 1 - cv[3]],
            ],
            evidence=["SourceMaturity", "ClosureGeometry"],
            evidence_card=[2, 2],
            state_names=sn,
        )
    )

    # SealIntegrity CPT (1 parent: ClosureGeometry)
    sv = cpts["SealIntegrity"]
    model.add_cpds(
        TabularCPD(
            variable="SealIntegrity",
            variable_card=2,
            values=[[sv[0], sv[1]], [1 - sv[0], 1 - sv[1]]],
            evidence=["ClosureGeometry"],
            evidence_card=[2],
            state_names=sn,
        )
    )

    # ReservoirQuality CPT (1 parent: ReservoirPresence)
    rv = cpts["ReservoirQuality"]
    model.add_cpds(
        TabularCPD(
            variable="ReservoirQuality",
            variable_card=2,
            values=[[rv[0], rv[1]], [1 - rv[0], 1 - rv[1]]],
            evidence=["ReservoirPresence"],
            evidence_card=[2],
            state_names=sn,
        )
    )

    # Discovery: Adequate iff all 4 parents Adequate — 2^4 = 16 combinations
    # Order: Charge, SealIntegrity, ReservoirQuality, Retention (Adequate first)
    disc_adq = [0.0] * 16
    disc_adq[0] = 1.0  # All Adequate
    model.add_cpds(
        TabularCPD(
            variable="Discovery",
            variable_card=2,
            values=[disc_adq, [1 - v for v in disc_adq]],
            evidence=["Charge", "SealIntegrity", "ReservoirQuality", "Retention"],
            evidence_card=[2, 2, 2, 2],
            state_names=sn,
        )
    )

    model.check_model()
    return model, VariableElimination(model)


def query_pos(inference: Any, evidence: dict[str, str] | None = None) -> float:
    """Query P(Discovery=Adequate). Returns 0.0 if inference is None."""
    if inference is None:
        return 0.0
    try:
        result = inference.query(variables=["Discovery"], evidence=evidence or {})
        return float(result.values[0])
    except Exception:
        return 0.0
