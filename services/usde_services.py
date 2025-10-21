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

import requests

def refresh_usde_snapshot() -> dict:
    _ensure_data_dir()
    data = {"as_of": int(time.time()), "sources": []}

    # --- 1. CoinGecko for price & supply ---
    try:
        url = "https://api.coingecko.com/api/v3/coins/ethena-usde"
        cg = requests.get(url, timeout=10).json()
        data["price"] = cg["market_data"]["current_price"]["usd"]
        data["supply"] = cg["market_data"]["circulating_supply"]
        data["sources"].append("CoinGecko")
    except Exception as e:
        data["price"] = None
        data["supply"] = None
        data["sources"].append(f"CoinGecko Error: {e}")

    # --- 2. DeFiLlama for TVL ---
    try:
        url = "https://api.llama.fi/protocol/ethena"
        llama = requests.get(url, timeout=10).json()
        data["tvl"] = llama.get("tvl", None)
        data["sources"].append("DeFiLlama")
    except Exception as e:
        data["tvl"] = None
        data["sources"].append(f"DeFiLlama Error: {e}")

    # --- 3. Approximate peg deviation (bps) ---
    try:
        if data.get("price"):
            peg_dev = abs((data["price"] - 1.0) * 10000)
            data["peg_deviation_bps"] = round(peg_dev, 2)
        else:
            data["peg_deviation_bps"] = None
    except Exception:
        data["peg_deviation_bps"] = None

    # --- Save snapshot ---
    SNAPSHOT.write_text(json.dumps(data, indent=2))
    return data