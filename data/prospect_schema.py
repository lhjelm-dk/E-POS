"""Prospect data schema and CSV load/save. Phase 2."""

from __future__ import annotations

import csv
import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ProspectData:
    """Unified prospect data carrying inputs for Classic POS, ESL, and BN models."""

    title: str = ""
    analyst: str = ""
    basin: str = ""
    date: str = ""
    version: str = ""
    # ESL: play and conditional dicts (pillar keys: "Charge", "Closure", "Reservoir", "Retention")
    play: dict[str, Any] = field(default_factory=dict)
    conditional: dict[str, Any] = field(default_factory=dict)
    # Classic POS: pillar probabilities 0-1
    classic_charge: float = 0.5
    classic_closure: float = 0.5
    classic_reservoir: float = 0.5
    classic_retention: float = 0.5
    # BN: reserved
    bn_nodes: list[dict] = field(default_factory=list)


PROSPECTS_DIR = Path(__file__).parent / "prospects"


def _default_filename(basin: str, title: str) -> str:
    """Generate filename: {basin}_{title}_{yyyymmdd}.csv"""
    safe_basin = "".join(c if c.isalnum() or c in "_-" else "_" for c in basin or "unknown")[:40]
    safe_title = "".join(c if c.isalnum() or c in "_-" else "_" for c in title or "prospect")[:40]
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    return f"{safe_basin}_{safe_title}_{date_str}.csv"


def save_prospect(data: ProspectData, filepath: Path | str | None = None) -> Path:
    """Save prospect to CSV. Uses data/prospects/ if filepath not given."""
    path = Path(filepath) if filepath else PROSPECTS_DIR / _default_filename(data.basin, data.title)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# GeoRisk Prospect", data.title, data.analyst, data.basin, data.date, data.version])
        w.writerow(["# ESL play", json.dumps(data.play, default=str)])
        w.writerow(["# ESL conditional", json.dumps(data.conditional, default=str)])
        w.writerow(["# Classic POS", data.classic_charge, data.classic_closure, data.classic_reservoir, data.classic_retention])
        w.writerow(["model", "pillar", "sub_element", "success_criteria", "p_success", "support_against", "evidence_for", "evidence_against", "uncertainty_note"])
        for pillar, el in (data.play or {}).items():
            if isinstance(el, dict) and "support_for" in el:
                w.writerow([
                    "esl", pillar, "",
                    el.get("success_criteria", ""),
                    el.get("support_for", 0.5),
                    el.get("support_against", 0.1),
                    el.get("evidence_for", ""),
                    el.get("evidence_against", ""),
                    el.get("uncertainty_note", ""),
                ])
        for pillar, elements in (data.conditional or {}).items():
            for elem in elements if isinstance(elements, list) else []:
                if isinstance(elem, dict):
                    w.writerow([
                        "esl", pillar, elem.get("label", ""),
                        elem.get("success_criteria", ""),
                        elem.get("support_for", 0.5),
                        elem.get("support_against", 0.1),
                        elem.get("evidence_for", ""),
                        elem.get("evidence_against", ""),
                        elem.get("uncertainty_note", ""),
                    ])
    return path


def load_prospect(filepath: Path | str) -> ProspectData:
    """Load prospect from CSV."""
    data = ProspectData()
    path = Path(filepath)
    if not path.exists():
        return data

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            if (row[0].startswith("# E-POS Prospect") or row[0].startswith("# GeoRisk Prospect")) and len(row) >= 5:
                data.title = row[1].strip() if len(row) > 1 else ""
                data.analyst = row[2].strip() if len(row) > 2 else ""
                data.basin = row[3].strip() if len(row) > 3 else ""
                data.date = row[4].strip() if len(row) > 4 else ""
                data.version = row[5].strip() if len(row) > 5 else ""
            elif row[0].startswith("# ESL play") and len(row) >= 2:
                try:
                    data.play = json.loads(row[1])
                except (json.JSONDecodeError, IndexError):
                    pass
            elif row[0].startswith("# ESL conditional") and len(row) >= 2:
                try:
                    data.conditional = json.loads(row[1])
                except (json.JSONDecodeError, IndexError):
                    pass
            elif row[0].startswith("# Classic POS") and len(row) >= 5:
                try:
                    data.classic_charge = float(row[1])
                    data.classic_closure = float(row[2])
                    data.classic_reservoir = float(row[3])
                    data.classic_retention = float(row[4])
                except (ValueError, IndexError):
                    pass
    return data


def list_prospects(prospects_dir: Path | str | None = None) -> list[str]:
    """List available prospect CSV filenames."""
    path = Path(prospects_dir) if prospects_dir else PROSPECTS_DIR
    if not path.exists():
        return []
    return sorted([p.name for p in path.glob("*.csv")], reverse=True)
