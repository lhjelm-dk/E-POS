"""Tests for the DFI input contract (``logic.dfi_inputs``).

The most valuable test here is :func:`test_every_read_key_has_a_widget` — it is
the guard that would have caught the ``dfi_w_water`` / ``dfi_dhi_index`` dead-key
bug, where two modules read session keys that no widget ever wrote, so their DFI
overlays silently ignored analyst input.  The contract it enforces:

    every session key that ``read_dfi_inputs`` *reads* must also be *written*
    somewhere as a Streamlit widget ``key=...``.

If someone adds a new DFI input but forgets to wire the widget (or misspells the
key), this test fails instead of the feature silently falling back to defaults.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from logic import dfi_inputs
from logic.dfi_inputs import read_dfi_inputs, DFIInputs

REPO_ROOT = Path(__file__).resolve().parents[1]

# The canonical session keys the reader depends on.
CONTRACT_KEYS = [
    dfi_inputs.KEY_DHI,
    dfi_inputs.KEY_SD_MODE,
    dfi_inputs.KEY_FLUID_TYPE,
    dfi_inputs.KEY_FLUID_WATER,
    dfi_inputs.KEY_FLUID_LSG,
    dfi_inputs.KEY_FLUID_OTHER,
    dfi_inputs.KEY_ESL_ATTR,
]


def _python_sources() -> list[Path]:
    """All first-party .py files (skip caches, archives, virtualenvs, tests)."""
    skip = {".venv", "venv", "__pycache__", "_archived", ".git", "node_modules", "tests"}
    out = []
    for p in REPO_ROOT.rglob("*.py"):
        if any(part in skip for part in p.parts):
            continue
        out.append(p)
    return out


def _widget_keys_in_source() -> set[str]:
    """Collect every literal used as a Streamlit widget ``key=...``."""
    # Matches key="foo" or key='foo' (the form used throughout the app).
    pat = re.compile(r"""key\s*=\s*["']([^"']+)["']""")
    found: set[str] = set()
    for path in _python_sources():
        text = path.read_text(encoding="utf-8", errors="ignore")
        found.update(pat.findall(text))
    return found


@pytest.mark.parametrize("key", CONTRACT_KEYS)
def test_every_read_key_has_a_widget(key):
    """Each key read by read_dfi_inputs must be written by some widget key=."""
    widget_keys = _widget_keys_in_source()
    assert key in widget_keys, (
        f"DFI session key {key!r} is read by read_dfi_inputs but no Streamlit "
        f"widget writes it (no key={key!r} found in source). Either wire a widget "
        f"with that key, or fix the key name — this is exactly the dead-key class "
        f"of bug the contract test exists to prevent."
    )


def test_defaults_on_empty_session():
    inp = read_dfi_inputs({})
    assert inp.dhi == dfi_inputs.DEFAULT_DHI
    assert inp.sd_mode == dfi_inputs.DEFAULT_SD_MODE
    assert inp.fluid_type == dfi_inputs.DEFAULT_FLUID_TYPE
    assert inp.esl_attribution == dfi_inputs.DEFAULT_ESL_ATTR
    assert inp.fluid_weights.water == dfi_inputs.DEFAULT_FLUID_WATER
    assert inp.fluid_weights.lsg == dfi_inputs.DEFAULT_FLUID_LSG
    assert inp.fluid_weights.other == dfi_inputs.DEFAULT_FLUID_OTHER


def test_reads_analyst_values():
    ss = {
        "dfi_index": 42,
        "dfi_sd_mode": "calculated",
        "dfi_fluid_type": "Oil",
        "dfi_fluid_water": 0.5,
        "dfi_fluid_lsg": 0.3,
        "dfi_fluid_other": 0.2,
        "dfi_esl_attribution": "B",
    }
    inp = read_dfi_inputs(ss)
    assert isinstance(inp, DFIInputs)
    assert inp.dhi == 42.0 and isinstance(inp.dhi, float)
    assert inp.sd_mode == "calculated"
    assert inp.fluid_type == "Oil"
    assert inp.esl_attribution == "B"
    assert (inp.fluid_weights.water, inp.fluid_weights.lsg, inp.fluid_weights.other) == (0.5, 0.3, 0.2)


def test_fluid_weights_returned_unnormalised():
    """Reader returns raw weights; normalisation is the caller's choice."""
    ss = {"dfi_fluid_water": 0.8, "dfi_fluid_lsg": 0.8, "dfi_fluid_other": 0.0}
    inp = read_dfi_inputs(ss)
    assert inp.fluid_weights.water == 0.8 and inp.fluid_weights.lsg == 0.8
    n = inp.fluid_weights.normalised()
    assert n.water == pytest.approx(0.5) and n.lsg == pytest.approx(0.5)
