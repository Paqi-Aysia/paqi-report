from __future__ import annotations
import json, time
from pathlib import Path
from typing import Optional, Dict, Any
from utils import fetch_json  # your retry/backoff helper

DATA_DIR = Path("/mnt/data")
SNAPSHOT = DATA_DIR / "usde.json"

def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def _safe_float(x) -> Optional[float]:
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(x)
    except Exception:
        return None

def get_usde_snapshot() -> dict:
    """Return the most recent saved snapshot, or a placeholder if none exists yet."""
    if SNAPSHOT.exists():
        try:
            return json.loads(SNAPSHOT.read_text())
        except Exception:
            pass
    return {"as_of": None, "error": "No snapshot yet"}

# --------------------------
# Fetch PRICE (Llama) + TVL (Llama)
# --------------------------

def _fetch_llama_price() -> tuple[Optional[float], str]:
    """
    Get USDe price from DeFiLlama stablecoins API.
    Only accept a price that looks like a USD stablecoin (0.8 - 1.2).
    """
    res = fetch_json("https://stablecoins.llama.fi/stablecoins?includePrices=true")
    if not res or "peggedAssets" not in res:
        return None, "DeFiLlama stablecoins FAILED (no peggedAssets)"

    target = None
    for asset in res["peggedAssets"]:
        sym = str(asset.get("symbol", "")).lower()
        name = str(asset.get("name", "")).lower()
        if "usde" in sym or "usde" in name or "ethena" in name:
            target = asset
            break

    if target is None:
        return None, "DeFiLlama stablecoins FAILED (no USDe match)"

    # Try direct price first
    price_val = _safe_float(target.get("price"))

    # Fallback: chainPrices/prices (per-chain series)
    if price_val is None:
        chain_prices = target.get("chainPrices") or target.get("prices") or {}
        if isinstance(chain_prices, dict):
            for _, series in chain_prices.items():
                if isinstance(series, list) and series:
                    last_entry = series[-1]
                    cand = _safe_float(
                        last_entry.get("price")
                        or last_entry.get("value")
                        or last_entry.get("usdPrice")
                    )
                    if cand is not None:
                        price_val = cand
                        break

    # sanity filter: must look like a stablecoin
    if price_val is not None and not (0.8 <= price_val <= 1.2):
        price_val = None

    return price_val, "DeFiLlama stablecoins (price)"

def _fetch_llama_tvl() -> tuple[Optional[float], str]:
    """
    Return latest Ethena TVL in USD as a single float.
    Uses /tvl/ethena with fallback to /protocol/ethena.
    """
    raw = fetch_json("https://api.llama.fi/tvl/ethena")

    # Case 1: it's just a number
    if isinstance(raw, (int, float)):
        return float(raw), "DeFiLlama tvl/ethena (number)"

    # Case 2: it's a list of datapoints
    if isinstance(raw, list) and raw:
        last = raw[-1]
        tvl_candidates = [
            last.get("totalLiquidityUSD"),
            last.get("tvl"),
            last.get("totalLiquidity"),
            last.get("totalLiquidityUsd"),
        ]
        for cand in tvl_candidates:
            val = _safe_float(cand)
            if val is not None:
                return val, "DeFiLlama tvl/ethena (timeseries latest)"

    # Fallback to /protocol/ethena
    proto = fetch_json("https://api.llama.fi/protocol/ethena")
    if isinstance(proto, dict):
        tvl_field = proto.get("tvl")
        # tvl might again be number OR list
        if isinstance(tvl_field, (int, float)):
            return float(tvl_field), "DeFiLlama protocol/ethena (number)"
        if isinstance(tvl_field, list) and tvl_field:
            last = tvl_field[-1]
            if isinstance(last, dict):
                for k in ("totalLiquidityUSD", "tvl", "totalLiquidity", "totalLiquidityUsd"):
                    val = _safe_float(last.get(k))
                    if val is not None:
                        return val, "DeFiLlama protocol/ethena (series latest)"

    return None, "DeFiLlama tvl FAILED"

# --------------------------
# Fetch SUPPLY (CoinGecko)
# --------------------------

def _fetch_supply_from_coingecko() -> tuple[Optional[float], str]:
    """
    Get circulating supply of Ethena USDe from CoinGecko.
    We use /coins/ethena-usde and read market_data.circulating_supply.
    We do NOT trust CoinGecko for price, only supply.
    """
    full = fetch_json("https://api.coingecko.com/api/v3/coins/ethena-usde")
    if not isinstance(full, dict):
        return None, "CoinGecko FAILED (no data)"

    md = full.get("market_data", {})
    circ = _safe_float(md.get("circulating_supply"))
    if circ is not None and circ > 0:
        return circ, "CoinGecko circulating_supply"
    return None, "CoinGecko FAILED (no circulating_supply)"

# --------------------------
# Peg math
# --------------------------

def _peg_bps(price: Optional[float]) -> Optional[float]:
    """
    Basis points off $1.00.
    If price is 0.999, deviation is -10 bps.
    """
    if price is None:
        return None
    return round((price - 1.0) * 10000, 2)

# --------------------------
# Snapshot builder
# --------------------------

def refresh_usde_snapshot() -> Dict[str, Any]:
    """
    Compose the USDe snapshot from our data sources:
      - price: DeFiLlama stablecoins
      - tvl: DeFiLlama tvl/ethena
      - supply: CoinGecko circulating_supply
    """
    _ensure_data_dir()

    price_val, price_src = _fetch_llama_price()
    tvl_val, tvl_src = _fetch_llama_tvl()
    supply_val, supply_src = _fetch_supply_from_coingecko()

    snap = {
        "as_of": int(time.time()),
        "price": price_val,
        "supply": supply_val,
        "tvl": tvl_val,
        "peg_deviation_bps": _peg_bps(price_val),
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

    SNAPSHOT.write_text(json.dumps(snap, indent=2))
    return snap