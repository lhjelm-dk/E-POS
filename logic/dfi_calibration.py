"""DFI calibration loader — manages the SAAM-style likelihood parameters.

Two files are recognised, in priority order:

  1. ``data/saam_calibration.json``             (proprietary, gitignored)
  2. ``data/saam_calibration_placeholder.json`` (synthetic, committed)

The app loads the first one that exists, with a clear warning when only the
placeholder is available.

A calibration is a dict ``{class_name -> {mean, sd_calculated, sd_upper, n}}``
plus a small metadata block (version, source, description).  The class names
are::

    "Success"           — aggregate HC success (default)
    "Oil"               — oil specifically
    "OilGas"            — oil-and-gas
    "Gas"               — gas specifically
    "H2O_failure"       — water in evaluable reservoir
    "LSG_failure"       — LSG / other-fluid failure in evaluable reservoir
                          (Other-fluids share these stats — same SAAM column)
    "Reservoir_failure" — reservoir failure / non-evaluable reservoir
                          (used for any fluid found in a non-evaluable reservoir)

All means and SDs are in **fraction units** (DHI index / 100).  Integer DHI
inputs of -23..+50 map to the fraction range -0.23..+0.50.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Public class names — keep stable; UI labels live separately
# ─────────────────────────────────────────────────────────────────────────────
SUCCESS_CLASSES: tuple[str, ...] = ("Success", "Oil", "OilGas", "Gas")
FAILURE_CLASSES: tuple[str, ...] = ("H2O_failure", "LSG_failure", "Reservoir_failure")
ALL_CLASSES:     tuple[str, ...] = SUCCESS_CLASSES + FAILURE_CLASSES

CLASS_DISPLAY: dict[str, str] = {
    "Success":           "HC Success",
    "Oil":               "Oil",
    "OilGas":            "Oil + Gas",
    "Gas":               "Gas",
    "H2O_failure":       "Water failure",
    "LSG_failure":       "LSG / other failure",
    "Reservoir_failure": "Reservoir failure (non-eval)",
}

DHI_INDEX_MIN_INT: int = -23
DHI_INDEX_MAX_INT: int =  50


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ClassStats:
    """Calibration stats for one outcome class."""
    mean:           float          # mean DHI/100
    sd_calculated:  float          # sample SD
    sd_upper:       float          # chi-squared upper-confidence-bound SD
    n:              int            # sample count
    comment:        str = ""

    def sd(self, mode: str = "upper") -> float:
        """Pick the SD per the requested mode ('upper' or 'calculated')."""
        if mode == "calculated":
            return float(self.sd_calculated)
        return float(self.sd_upper)


@dataclass
class Calibration:
    """Full calibration set + metadata."""
    version:     str
    source:      str
    description: str
    classes:     dict[str, ClassStats] = field(default_factory=dict)
    file_path:   str = ""
    is_placeholder: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Loader
# ─────────────────────────────────────────────────────────────────────────────

_PROPRIETARY_PATH  = Path("data") / "saam_calibration.json"
_PLACEHOLDER_PATH  = Path("data") / "saam_calibration_placeholder.json"


@lru_cache(maxsize=8)
def _load_json_cached(path_str: str, mtime: float) -> dict:
    """Read + parse JSON, cached on (path, mtime).

    Keying on the file's modification time means an edit on disk busts the
    cache automatically (different mtime → cache miss), so file-change pickup
    is preserved while repeated reads of an unchanged file are free.
    """
    with open(path_str, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_json(path: Path) -> dict:
    # Return a fresh copy each call: the caller (load_calibration → _parse_classes)
    # builds new dataclasses, but a defensive copy guarantees the cached dict is
    # never mutated downstream.
    import copy
    return copy.deepcopy(_load_json_cached(str(path), path.stat().st_mtime))


def _parse_classes(raw_classes: dict) -> dict[str, ClassStats]:
    out: dict[str, ClassStats] = {}
    for name in ALL_CLASSES:
        if name not in raw_classes:
            raise ValueError(f"Calibration class missing: {name!r}")
        s = raw_classes[name]
        out[name] = ClassStats(
            mean          = float(s["mean"]),
            sd_calculated = float(s["sd_calculated"]),
            sd_upper      = float(s["sd_upper"]),
            n             = int(s.get("n", 0)),
            comment       = str(s.get("comment", "")),
        )
    return out


def _calibration_from_dict(d: dict, file_path: Path, is_placeholder: bool) -> Calibration:
    return Calibration(
        version        = str(d.get("version", "unknown")),
        source         = str(d.get("source", "")),
        description    = str(d.get("description", "")),
        classes        = _parse_classes(d["classes"]),
        file_path      = str(file_path),
        is_placeholder = is_placeholder,
    )


def load_calibration(base_dir: "str | os.PathLike | None" = None) -> Calibration:
    """Load the active calibration.  Proprietary file wins over placeholder.

    ``base_dir`` defaults to the current working directory, intended to be the
    project root.  Tests can pass an alternate path.
    """
    root = Path(base_dir) if base_dir is not None else Path.cwd()
    propr = root / _PROPRIETARY_PATH
    place = root / _PLACEHOLDER_PATH
    if propr.is_file():
        return _calibration_from_dict(_load_json(propr), propr, is_placeholder=False)
    if place.is_file():
        return _calibration_from_dict(_load_json(place), place, is_placeholder=True)
    raise FileNotFoundError(
        f"No DFI calibration found. Expected one of:\n  {propr}\n  {place}"
    )


def calibration_to_dict(c: Calibration) -> dict:
    """Round-trip serialisation — useful for the in-UI editor saving overrides."""
    return {
        "version": c.version,
        "source":  c.source,
        "description": c.description,
        "classes": {
            name: {
                "mean":          s.mean,
                "sd_calculated": s.sd_calculated,
                "sd_upper":      s.sd_upper,
                "n":             s.n,
                **({"comment": s.comment} if s.comment else {}),
            }
            for name, s in c.classes.items()
        },
    }
