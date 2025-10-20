# services/usde_service.py
from __future__ import annotations
import json, time
from pathlib import Path

DATA_DIR = Path("/mnt/data")
SNAPSHOT = DATA_DIR / "usde.json"

def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def get_usde_snapshot() -> dict:
    """Read the latest saved USDe snapshot (or a placeholder if none exists)."""
    if SNAPSHOT.exists():
        try:
            return json.loads(SNAPSHOT.read_text())
        except Exception:
            pass
    return {"as_of": None, "error": "No snapshot yet"}

def refresh_usde_snapshot() -> dict:
    """
    For now: write a tiny placeholder so the page renders.
    We’ll replace this with real API fetches in the next step.
    """
    _ensure_data_dir()
    data = {
        "as_of": int(time.time()),
        "price": None,
        "supply": None,
        "peg_deviation_bps": None,
        "tvl": None,
        "backing": {"stETH": None, "ETH": None, "other": None},
        "yield_components": {"staking": None, "funding": None, "other": None},
        "notes": [],
        "sources": ["(placeholder)"],
    }
    SNAPSHOT.write_text(json.dumps(data, indent=2))
    return data