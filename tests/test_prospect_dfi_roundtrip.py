"""Save/load round-trip for the DFI state added to ProspectData (rec #3)."""
import tempfile
from pathlib import Path

from data.prospect_schema import ProspectData, save_prospect, load_prospect


def test_dfi_state_round_trips():
    dfi = {
        "dfi_enabled": True,
        "dfi_source_radio": "Custom R tool",
        "dfi_index": 19,
        "dfi_custom_slider": 7.0,
        "dfi_custom_multicase": True,
        "dhi_char_mode": "5_current",
        "dhi_char_apply_cap": True,
        "dhi_char_rel_middle": False,
        "dhi_char_selections": {"anomaly_strength": "Very strong"},
        "_dfi_policy": "2026.06-test",
    }
    data = ProspectData(title="AlphaGammaFoxtrot", basin="Komsaadehvii", dfi=dfi)
    with tempfile.TemporaryDirectory() as d:
        p = save_prospect(data, Path(d) / "p.csv")
        loaded = load_prospect(p)
    assert loaded.dfi == dfi
    assert loaded.title == "AlphaGammaFoxtrot"
    assert loaded.dfi["dfi_custom_slider"] == 7.0
    assert loaded.dfi["dhi_char_selections"]["anomaly_strength"] == "Very strong"


def test_missing_dfi_block_loads_as_empty_dict():
    # A legacy file without the "# DFI state" row must load with dfi == {}.
    data = ProspectData(title="Legacy")
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "legacy.csv"
        # write a file WITHOUT the DFI row by stripping it after save
        save_prospect(data, path)
        text = path.read_text(encoding="utf-8")
        text = "\n".join(l for l in text.splitlines() if not l.startswith("# DFI state"))
        path.write_text(text, encoding="utf-8")
        loaded = load_prospect(path)
    assert loaded.dfi == {}
