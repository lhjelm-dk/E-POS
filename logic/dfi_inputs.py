"""Single source of truth for the DFI input bundle held in Streamlit session state.

Before this module, the same six session keys and their default values were
copy-pasted across five UI/methods modules (``tab_dfi``, ``tab_dashboard``,
``tab_analysis``, ``prospect_hub``, ``methods.classic_pos``).  That duplication
let two copies silently drift onto *wrong* key names (``dfi_w_water`` /
``dfi_dhi_index`` instead of ``dfi_fluid_water`` / ``dfi_index``), so those DFI
overlays always read the hard-coded defaults regardless of analyst input.

Reading the bundle through :func:`read_dfi_inputs` makes that whole class of bug
structurally impossible: the canonical keys and defaults live here once.

This module is pure; it takes a session-state-like mapping as an argument and
does not import Streamlit, so it stays unit-testable.
"""
from __future__ import annotations

from dataclasses import dataclass

from logic.dfi_bayes import FluidWeights

# ── Canonical session keys (must match the widget ``key=`` on the DFI Setup tab) ──
KEY_DHI         = "dfi_index"
KEY_SD_MODE     = "dfi_sd_mode"
KEY_FLUID_TYPE  = "dfi_fluid_type"
KEY_FLUID_WATER = "dfi_fluid_water"
KEY_FLUID_LSG   = "dfi_fluid_lsg"
KEY_FLUID_OTHER = "dfi_fluid_other"
KEY_ESL_ATTR    = "dfi_esl_attribution"

# ── Default values (applied when the analyst has not set the widget yet) ──
DEFAULT_DHI         = 19.0
DEFAULT_SD_MODE     = "upper"
DEFAULT_FLUID_TYPE  = "Success"
DEFAULT_FLUID_WATER = 0.80
DEFAULT_FLUID_LSG   = 0.20
DEFAULT_FLUID_OTHER = 0.00
DEFAULT_ESL_ATTR    = "A"


@dataclass(frozen=True)
class DFIInputs:
    """The DFI inputs an analyst sets on the DFI Setup tab.

    ``fluid_weights`` is returned **unnormalised** (exactly as entered); call
    :meth:`FluidWeights.normalised` if you need the renormalised values for
    display.  The Bayesian core (:func:`logic.dfi_bayes.decompose_prior`)
    normalises internally, so passing the raw weights to ``compute_dfi_posterior``
    yields identical results.
    """
    dhi: float
    sd_mode: str
    fluid_type: str
    fluid_weights: FluidWeights
    esl_attribution: str


def read_dfi_inputs(ss) -> DFIInputs:
    """Read the DFI input bundle from a ``session_state``-like mapping.

    ``ss`` is anything supporting ``.get(key, default)`` — Streamlit's
    ``st.session_state`` or a plain ``dict`` (handy for tests).
    """
    fw = FluidWeights(
        water=float(ss.get(KEY_FLUID_WATER, DEFAULT_FLUID_WATER)),
        lsg  =float(ss.get(KEY_FLUID_LSG,   DEFAULT_FLUID_LSG)),
        other=float(ss.get(KEY_FLUID_OTHER, DEFAULT_FLUID_OTHER)),
    )
    return DFIInputs(
        dhi=float(ss.get(KEY_DHI, DEFAULT_DHI)),
        sd_mode=str(ss.get(KEY_SD_MODE, DEFAULT_SD_MODE)),
        fluid_type=str(ss.get(KEY_FLUID_TYPE, DEFAULT_FLUID_TYPE)),
        fluid_weights=fw,
        esl_attribution=str(ss.get(KEY_ESL_ATTR, DEFAULT_ESL_ATTR)),
    )
