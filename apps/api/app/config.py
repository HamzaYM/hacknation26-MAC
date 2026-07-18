"""Vertical config loader — the config-not-code boundary.

Everything strategy-shaped (flags, thresholds, ladder, personas, voice,
disclosure) comes from config/verticals/<vertical>.yaml. Code in this app
must consult the config rather than hard-coding vertical knowledge.
"""
from functools import lru_cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
VERTICALS_DIR = REPO_ROOT / "config" / "verticals"
SEED_DIR = REPO_ROOT / "data" / "seed"


@lru_cache
def load_vertical(name: str = "medical_bills") -> dict:
    with open(VERTICALS_DIR / f"{name}.yaml") as f:
        return yaml.safe_load(f)
