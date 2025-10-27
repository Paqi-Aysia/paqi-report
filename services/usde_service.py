# services/usde_service.py
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Optional, Dict, Any
from utils import fetch_json  # uses your retry/backoff logic

DATA_DIR = Path("/mnt/data")
SNAPSHOT = DATA_DIR / "usde.json"

def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def get_usde_snapshot() -> dict:
    """Return the most recent saved snapshot, or a placeholder if none exists."""
    if SNAPSHOT.exists():
        try:
            return json.loads(SNAPSHOT.read_text())
        except Exception:
            pass
    return {"as_of": None, "error": "No snapshot yet"}

# ---------- Utility helpers ----------

def _safe_float(x) -> Optional[float]:
    """Convert to float if possible, else return None."""
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(x)
    except Exception:
        return None

# ---------- Data fetchers ----------

def _fetch_price() -> tuple[Optional[float], str]:
    """
    Try to get USDe price from CoinGecko simple/price endpoint using several IDs.
    Returns (price, info_string)
    """
    ids_to_try = ["usde", "ethena-usde", "ethena-usd"]
    for cid in ids_to_try:
        res = fetch_json(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": cid, "vs_currencies": "usd"}
        )
        if isinstance(res, dict) and cid in res:
            usd_val = res[cid].get("usd")
            p = _safe_float(usd_val)
            if p is not None:
                return p, f"CoinGecko simple price ({cid})"
    return None, "CoinGecko simple price FAILED"

def _fetch_supply() -> tuple[Optional[float], str]:
    """
    Try to get circulating supply from DeFiLlama stablecoins dataset.
    Returns (supply, info_string)
    """
    res = fetch_json("https://stablecoins.llama.fi/stablecoins?includePrices=true")
    if not res or "peggedAssets" not in res:
        return None, "DeFiLlama stablecoins FAILED (no peggedAssets)"
    for asset in res["peggedAssets"]:
        if asset.get("symbol", "").upper() == "USDE":
            hist = asset.get("circulating") or asset.get("chainCirculating") or []
            if isinstance(hist, list) and hist:
                last = hist[-1]
                for k in ("circulating", "totalCirculating"):
                    if k in last:
                        sup = _safe_float(last[k])
                        if sup is not None:
                            return sup, "DeFiLlama stablecoins (hist)"
            direct = _safe_float(asset.get("circulating"))
            if direct is not None:
                return direct, "DeFiLlama stablecoins (direct)"
    return None, "DeFiLlama stablecoins FAILED (no USDe match)"

def _fetch_tvl() -> tuple[Optional[float], str]:
    """
    Return latest Ethena TVL in USD as a single float.
    Try /tvl/ethena first. That may return:
      - a single number
      - OR a list of { date, totalLiquidityUSD } objects.
    Fallback to /protocol/ethena.
    """

    raw = fetch_json("https://api.llama.fi/tvl/ethena")

    # Case 1: it's already just a number
    if isinstance(raw, (int, float)):
        return float(raw), "DeFiLlama tvl/ethena (number)"

    # Case 2: it's a list of datapoints
    if isinstance(raw, list) and len(raw) > 0:
        last = raw[-1]
        # try common keys
        tvl_candidates = [
            last.get("totalLiquidityUSD"),
            last.get("tvl"),
            last.get("totalLiquidity"),  # backup naming
        ]
        for cand in tvl_candidates:
            val = _safe_float(cand)
            if val is not None:
                return val, "DeFiLlama tvl/ethena (timeseries latest)"

    # Fallback: /protocol/ethena
    proto = fetch_json("https://api.llama.fi/protocol/ethena")
    if isinstance(proto, dict):
        tvl_field = proto.get("tvl")
        # tvl might again be a number OR a list
        if isinstance(tvl_field, (int, float)):
            return float(tvl_field), "DeFiLlama protocol/ethena (number)"
        if isinstance(tvl_field, list) and len(tvl_field) > 0:
            last = tvl_field[-1]
            if isinstance(last, dict):
                # common keys in protocol history objects
                for k in ("totalLiquidityUSD", "tvl", "totalLiquidity"):
                    val = _safe_float(last.get(k))
                    if val is not None:
                        return val, "DeFiLlama protocol/ethena (series latest)"

    return None, "DeFiLlama tvl FAILED"

def _peg_bps(price: Optional[float]) -> Optional[float]:
    """Calculate basis points deviation from $1 peg."""
    if price is None:
        return None
    return round((price - 1.0) * 10000, 2)

# ---------- Main snapshot builder ----------

def refresh_usde_snapshot() -> Dict[str, Any]:
    """Fetch latest data from APIs, build snapshot, and save it."""
    _ensure_data_dir()

    price, price_src = _fetch_price()
    supply, supply_src = _fetch_supply()
    tvl, tvl_src = _fetch_tvl()

    data = {
        "as_of": int(time.time()),
        "price": price,
        "supply": supply,
        "tvl": tvl,
        "peg_deviation_bps": _peg_bps(price),
        "backing": {
            "stETH": None,
            "ETH": None,
            "other": None
        },
        "yield_components": {
            "staking": None,
            "funding": None,
            "other": None
        },
        "notes": [],
        "sources": [price_src, supply_src, tvl_src],
    }

    SNAPSHOT.write_text(json.dumps(data, indent=2))
    return data