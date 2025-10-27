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

def _fetch_price_and_supply_from_llama() -> tuple[Optional[float], Optional[float], str]:
    """
    Pull USDe info from DeFiLlama stablecoins API.
    Returns (price, supply, source_string).

    DeFiLlama shape (simplified):
    {
      "peggedAssets": [
        {
          "symbol": "USDe",
          "name": "USDe",
          "circulating": [ { "circulating": 10379093520.89, ... }, ... ],
          "price": 0.9993  <-- sometimes this exists, sometimes per-chainPrices
          ...
        },
        ...
      ]
    }
    """
    res = fetch_json("https://stablecoins.llama.fi/stablecoins?includePrices=true")
    if not res or "peggedAssets" not in res:
        return None, None, "DeFiLlama stablecoins FAILED (no peggedAssets)"

    # Find the asset that looks like USDe (case-insensitive, fuzzy match)
    target = None
    for asset in res["peggedAssets"]:
        sym = str(asset.get("symbol", "")).lower()
        name = str(asset.get("name", "")).lower()
        if "usde" in sym or "usde" in name or "ethena" in name:
            target = asset
            break

    if target is None:
        return None, None, "DeFiLlama stablecoins FAILED (no USDe match)"

    # ---- supply ----
    supply_val = None
    hist = target.get("circulating") or target.get("chainCirculating") or []
    if isinstance(hist, list) and hist:
        last_point = hist[-1]
        # try common keys
        for key in ("circulating", "totalCirculating"):
            cand = _safe_float(last_point.get(key))
            if cand is not None:
                supply_val = cand
                break
    if supply_val is None:
        # fallback direct field on the asset
        supply_val = _safe_float(target.get("circulating"))

    # ---- price ----
    # Llama may give a direct "price" on the asset, or per-chain prices.
    price_val = None

    direct_price = _safe_float(target.get("price"))
    if direct_price is not None:
        price_val = direct_price

    # If not, try per-chain price series
    if price_val is None:
        # some entries have "chainPrices": {"ethereum":[{...latest...}, ...], ...}
        chain_prices = target.get("chainPrices") or target.get("prices") or {}
        # try to walk the dict-of-lists and grab the last numeric "price"
        if isinstance(chain_prices, dict):
            for chain_name, series in chain_prices.items():
                if isinstance(series, list) and series:
                    last_entry = series[-1]
                    cand = _safe_float(last_entry.get("price") or last_entry.get("value"))
                    if cand is not None:
                        price_val = cand
                        break

    # sanity filter: only accept stable-ish price
    if price_val is not None and not (0.8 <= price_val <= 1.2):
        price_val = None  # reject obvious nonsense

    # Done
    return price_val, supply_val, "DeFiLlama stablecoins (price & supply)"

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
    _ensure_data_dir()

    # Get price & supply from Llama stablecoin API
    llama_price, llama_supply, llama_src = _fetch_price_and_supply_from_llama()

    # Get TVL from Llama protocol/tvl endpoints (your working _fetch_tvl)
    tvl_val, tvl_src = _fetch_tvl()

    # Peg deviation (in bps) from 1.00
    def peg_bps(p):
        if p is None:
            return None
        return round((p - 1.0) * 10000, 2)

    data = {
        "as_of": int(time.time()),
        "price": llama_price,
        "supply": llama_supply,
        "tvl": tvl_val,
        "peg_deviation_bps": peg_bps(llama_price),
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
        "sources": [llama_src, tvl_src],
    }

    SNAPSHOT.write_text(json.dumps(data, indent=2))
    return data