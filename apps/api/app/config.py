"""Vertical config loader — the config-not-code boundary.

Everything strategy-shaped (flags, thresholds, ladder, personas, voice,
disclosure) comes from config/verticals/<vertical>.yaml. Code in this app
must consult the config rather than hard-coding vertical knowledge.

Set VERTICAL env var to switch verticals (e.g. VERTICAL=moving).
"""
import os
from functools import lru_cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
VERTICALS_DIR = REPO_ROOT / "config" / "verticals"
SEED_DIR = REPO_ROOT / "data" / "seed"

ACTIVE_VERTICAL = os.environ.get("VERTICAL", "medical_bills")


@lru_cache
def load_vertical(name: str = ACTIVE_VERTICAL) -> dict:
    with open(VERTICALS_DIR / f"{name}.yaml") as f:
        return yaml.safe_load(f)
