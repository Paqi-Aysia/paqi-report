import json
import time
import logging
from datetime import datetime
from utils import fetch_json  # use your safe version with timeout + retries

logging.basicConfig(level=logging.INFO)

def get_historical_tvl(chain):
    url = f"https://api.llama.fi/v2/historicalChainTvl/{chain}"
    return fetch_json(url) or []

def parse_date_safe(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d")
    except:
        return None

def run_tvl_fallback_update(max_calls=25, delay=1.5):
    logging.info("🧠 Starting fallback update")
    url = "https://api.llama.fi/v2/chains"
    chains = fetch_json(url) or []

    updated_fallbacks = {}
    fallback_count = 0

    for chain in chains:
        name = chain.get("name", "unknown")
        chain_name = name.lower()
        if chain.get("tvlChange1d") and chain["tvlChange1d"] != 0:
            updated_fallbacks[name] = chain["tvlChange1d"]
            continue

        if fallback_count >= max_calls:
            logging.warning("🛑 Max fallback calls reached")
            break

        time.sleep(delay)
        data = get_historical_tvl(chain_name)

        if len(data) >= 2:
            last = data[-1]
            prev = data[-2]
            d1 = parse_date_safe(last.get("date"))
            d2 = parse_date_safe(prev.get("date"))

            if d1 and d2 and (d1 - d2).days == 1:
                delta = last["tvl"] - prev["tvl"]
                updated_fallbacks[name] = delta
                fallback_count += 1
                logging.info(f"✅ {name}: {delta:,.0f}")
            else:
                logging.warning(f"⚠️ {name} skipped: date gap or invalid dates")

    with open("data/tvl_fallbacks.json", "w") as f:
        json.dump(updated_fallbacks, f, indent=2)
    logging.info("📦 tvl_fallbacks.json saved.")

if __name__ == "__main__":
    run_tvl_fallback_update()