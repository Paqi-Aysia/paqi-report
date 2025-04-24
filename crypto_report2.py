from backfill_reports import backfill as run_backfill

from dotenv import load_dotenv
import os
load_dotenv()
import json
import time
import logging
from datetime import datetime
from flask import Flask, jsonify, render_template
# from apscheduler.schedulers.blocking import BlockingScheduler
from zoneinfo import ZoneInfo

from utils import fetch_json, ensure_folder

# Configure logging
logging.basicConfig(level=logging.INFO)

# --- API FETCHING FUNCTIONS ---

def get_market_data():
    time.sleep(2)
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 200, #checks only top movers for top 200 tokens
        "page": 1,
        "price_change_percentage": "24h",
    }
    return fetch_json(url, params) or []

def get_market_caps():
    time.sleep(2)
    url = "https://api.coingecko.com/api/v3/coins/categories"
    data = fetch_json(url)

    if not data:
        logging.warning("CoinGecko categories request failed — returning empty caps")
        return {key: 0 for key in [
            "L1", "L2", "Gaming", "DeFi", "AI", "RWA", "Stablecoins",
            "Solana Meme", "AI Agent", "DePIN"
        ]}

    categories = {
        "L1": "layer-1",
        "L2": "layer-2",
        "Gaming": "gaming",
        "DeFi": "decentralized-finance-defi",
        "AI": "artificial-intelligence",
        "RWA": "real-world-assets-rwa",
        "Stablecoins": "stablecoins",
        "Solana Meme": "solana-meme-coins",
        "AI Agent": "ai-agents",
        "DePIN": "depin"
    }

    caps = {}
    for name, cid in categories.items():
        cat = next((c for c in data if c["id"] == cid), None)
        caps[name] = cat.get("market_cap", 0) if cat else 0
    return caps

def get_defillama_data():
    url = "https://api.llama.fi/protocols"
    protocols = fetch_json(url) or []
    excluded = {"CEX", "Centralized", "Custodial", "Bridge"}
    filtered = [p for p in protocols if p.get("category", "") not in excluded]

    sorted_protocols = sorted(filtered, key=lambda x: x.get("tvl", 0) or 0, reverse=True)[:20]
    for p in sorted_protocols:
        p["tvl_change_1d"] = p.get("change_1d", "N/A")
        p["tvl_change_7d"] = p.get("change_7d", "N/A")
    return sorted_protocols

def get_historical_tvl(chain):
    url = f"https://api.llama.fi/v2/historicalChainTvl/{chain}"
    return fetch_json(url) or []

from datetime import datetime, timedelta

def get_chain_inflow_outflow_v2():
    url = "https://api.llama.fi/v2/chains"
    chains = fetch_json(url) or []
    results = []

    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)

    for chain in chains:
        name = chain.get("name")
        hist = get_historical_tvl(name)
        logging.info(f"🔁 Processing {name}, History length: {len(hist)}")

        tvl_today = None
        tvl_yesterday = None

        for entry in reversed(hist):
            try:
                entry_date = datetime.utcfromtimestamp(entry["date"]).date()  # 🔥 Fix is here
            except Exception:
                logging.warning(f"⚠️ Could not parse date for {name}: {entry}")
                continue

            if entry_date == today and tvl_today is None:
                tvl_today = entry["tvl"]
            elif entry_date == yesterday and tvl_yesterday is None:
                tvl_yesterday = entry["tvl"]

            if tvl_today is not None and tvl_yesterday is not None:
                break

        if tvl_today is not None and tvl_yesterday is not None:
            delta = tvl_today - tvl_yesterday
            results.append({"name": name, "tvlChange1d": delta})
        else:
            logging.warning(f"⚠️ {name} missing data: today={tvl_today}, yesterday={tvl_yesterday}")

        time.sleep(0.1)

    logging.info("🔍 All TVL Deltas:")
    for c in results:
        logging.info(f"{c['name']}: {c['tvlChange1d']}")

    inflows = sorted([c for c in results if c["tvlChange1d"] > 0], key=lambda x: x["tvlChange1d"], reverse=True)[:5]
    outflows = sorted([c for c in results if c["tvlChange1d"] < 0], key=lambda x: x["tvlChange1d"])[:5]

    return inflows, outflows

def get_crypto_news():
    url = "https://cryptopanic.com/api/v1/posts/"
    token = os.getenv("CRYPTOPANIC_TOKEN")
    if not token:
        print("❗CRYPTO PANIC TOKEN NOT FOUND")
    else:
        print("🔑 CryptoPanic token loaded")

    params = {"auth_token": token, "public": "true", "filter": "hot"}
    res = fetch_json(url, params)
    
    if not res:
        print("❗No response from CryptoPanic")
    else:
        print(f"📰 CryptoPanic returned {len(res.get('results', []))} articles")

    return res.get("results", []) if res else []

# --- REPORT GENERATION ---
def generate_report():
    time.sleep(4)
    market_data = get_market_data()

    time.sleep(8)
    market_caps = get_market_caps()

    defillama_data = get_defillama_data()

    crypto_news = get_crypto_news()

    inflow, outflow = get_chain_inflow_outflow_v2()

    now = datetime.now().strftime('%Y-%m-%d')
    report = f"Crypto Market Report - {now}\n\n"

    report += "The Maxis:\n"
    for coin_id in ["bitcoin", "ethereum"]:
        coin = next((c for c in market_data if c['id'] == coin_id), None)
        if coin:
            report += f"{coin['name']} ({coin['symbol'].upper()}): Current Price ${coin['current_price']} | 24-Hour Change: {coin['price_change_percentage_24h']:.2f}%\n"

    report += "\nTop Movers (Last 24 Hours, Top 500 MC):\n"
    top_movers = sorted(market_data, key=lambda x: x.get("price_change_percentage_24h", 0), reverse=True)[:5]
    for coin in top_movers:
        report += f"{coin['name']} ({coin['symbol']}): ${coin['current_price']} | 24-Hour Change: {coin['price_change_percentage_24h']:.2f}%\n"

    report += "\nAggregate Market Capitalizations:\n"
    for sector, cap in market_caps.items():
        report += f"{sector}: ${cap:,.2f}\n"

    report += "\nTVL Data (Top TVLs):\n"
    for p in defillama_data:
        report += f"{p['name']}, TVL: ${p['tvl']:.2f}\n"

    report += "\nInflow and Outflow:\n"
    # Already sorted in v2, no need to re-sort
    if inflow or outflow:

        report += "Top Chains by Inflow:\n"
        for chain in inflow:
            report += f"{chain['name']}: TVL Change 1D: ${chain.get('tvlChange1d', 0):,.2f}\n"

        report += "\nTop Chains by Outflow:\n"
        for chain in outflow:
            report += f"{chain['name']}: TVL Change 1D: ${chain.get('tvlChange1d', 0):,.2f}\n"

    if crypto_news:
        news_items = {n["title"]: n for n in crypto_news}.values()
        report += "\nHot News:\n"
        for n in list(news_items)[:10]:
            report += f"{n['title']} - {n['url']}\n"

    btc = next((c for c in market_data if c['id'] == 'bitcoin'), {})
    eth = next((c for c in market_data if c['id'] == 'ethereum'), {})

    structured_data = {
        "date": now,
        "maxis": {
            "BTC": btc.get("current_price"),
            "ETH": eth.get("current_price")
        },
        "top_movers": [
            {
                "name": coin["name"],
                "symbol": coin["symbol"],
                "price": coin["current_price"],
                "change_24h": coin.get("price_change_percentage_24h", 0)
            }
            for coin in top_movers
        ],
        "market_caps": market_caps,
        "tvl_data": [
            {"name": p["name"], "tvl": p["tvl"]} for p in defillama_data
        ],
        "chain_flows": [
            {
                "name": c["name"],
                "tvlChange1d": c.get("tvlChange1d", 0)
            }
            for c in inflow + outflow
        ],
        "news": list({n["title"] for n in crypto_news})[:5]
    }

    return report, structured_data

def save_report(report):
    folder = "reports"
    ensure_folder(folder)
    filename = f"crypto_report_{datetime.now().strftime('%Y_%m_%d')}.txt"
    path = os.path.join(folder, filename)
    with open(path, 'w') as f:
        f.write(report)
    logging.info(f"Report saved to {path}")

def save_structured_data(new_data, path="data/accumulated.json"):
    if not os.path.exists("data"):
        os.makedirs("data")

    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
    else:
        data = []

    data = [entry for entry in data if entry["date"] != new_data["date"]]
    data.append(new_data)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)
''' 
Commented out since using cron job to generate the daily report.
# --- SCHEDULER ---
def main():
    report, structured_data = generate_report()
    save_report(report)
    save_structured_data(structured_data)

def schedule_daily_report():
    scheduler = BlockingScheduler(timezone=ZoneInfo("America/New_York"))
    scheduler.add_job(main, 'cron', hour=8, minute=0)
    logging.info("Scheduler started. Next job at 8:00 AM ET.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logging.warning("Scheduler stopped.")
''' 
# --- FLASK APP ---
app = Flask(__name__)

@app.route("/")
def home():
    return render_template("DailyReportPage.html")

@app.route("/daily-report")
def daily_report():
    folder = "reports"
    if os.path.exists(folder) and os.listdir(folder):
        files = sorted(os.listdir(folder))
        latest = files[-1]
        with open(os.path.join(folder, latest), 'r') as f:
            content = f.read()
        return jsonify({"status": "success", "latest_report": {
            "date": latest.replace("crypto_report_", "").replace(".txt", "").replace("_", "-"),
            "content": content
        }})
    return jsonify({"status": "error", "message": "No reports available."})

@app.route("/accumulated")
def accumulated():
    return render_template("AccumulatedInsights.html")

@app.route("/blog")
def blog():
    return render_template("blank.html", title="Blog Posts")

@app.route("/paqi")
def paqi():
    return render_template("blank.html", title="Paqi")

@app.route("/contact")
def contact():
    return render_template("blank.html", title="Contact")

@app.route("/accumulated-data")
def accumulated_data():
    path = "data/accumulated.json"
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
        return jsonify({"status": "success", "data": data})
    return jsonify({"status": "error", "message": "No accumulated data found."})

@app.route("/generate-daily-report", methods=["POST"])
def generate_daily_report():
    try:
        print("📩 /generate-daily-report triggered")
        report, structured_data = generate_report()
        print(f"📝 Report generated for {structured_data['date']}")
        save_report(report)
        save_structured_data(structured_data)
        print("✅ Data saved successfully")
        return jsonify({"status": "success", "message": "Daily report generated."})
    except Exception as e:
        import traceback
        print("❌ Error generating report:")
        traceback.print_exc()
        import sys
        sys.stdout.flush()  # <---- force logs to flush
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route("/tvl-fallbacks")
def view_tvl_fallbacks():
    import os
    import json
    from flask import jsonify

    fallback_path = "data/tvl_fallbacks.json"
    if os.path.exists(fallback_path):
        with open(fallback_path, "r") as f:
            data = json.load(f)
        return jsonify({"status": "success", "data": data})
    else:
        return jsonify({"status": "error", "message": "Fallback cache not found."})
    
from datetime import date

def should_run_backfill(path="data/accumulated.json"):
    if not os.path.exists(path) or os.stat(path).st_size == 0:
        return True

    with open(path, "r") as f:
        try:
            data = json.load(f)
        except Exception:
            return True

    today = date.today().strftime("%Y-%m-%d")
    return all(entry["date"] != today for entry in data)

if __name__ == "__main__":
    try:
        if should_run_backfill():
            print("📦 Running one-time backfill...")
            run_backfill()
            print("✅ Backfill completed.")
        else:
            print("📁 Today's data already exists — skipping backfill.")
    except Exception as e:
        import traceback
        print("❌ Backfill failed:")
        traceback.print_exc()
        import sys
        sys.stdout.flush()

    #Removed main line since scheduler above was commented out in favor of cron job
    #main() 
    app.run(host="0.0.0.0", port=5001, debug=True)