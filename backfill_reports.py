import os
import json
import re
from datetime import datetime

REPORT_FOLDER = "reports"
OUTPUT_PATH = "data/accumulated.json"

def parse_report(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()

    data = {
        "date": re.search(r"\d{4}-\d{2}-\d{2}", lines[0]).group(),
        "maxis": {},
        "top_movers": [],
        "market_caps": {},
        "tvl_data": [],
        "chain_flows": [],
        "news": []
    }

    section = None
    for line in lines:
        line = line.strip()

        if "The Maxis" in line:
            section = "maxis"
        elif "Top Movers" in line:
            section = "top_movers"
        elif "Aggregate Market Capitalizations" in line:
            section = "market_caps"
        elif "TVL Data" in line:
            section = "tvl_data"
        elif "Top Chains by Inflow" in line:
            section = "inflows"
        elif "Top Chains by Outflow" in line:
            section = "outflows"
        elif "Hot News" in line:
            section = "news"
        elif not line:
            continue
        else:
            if section == "maxis":
                match = re.search(r"(\w+).*?\$([\d,\.]+).*?([-+]?[\d\.]+)%", line)
                if match:
                    name, price, _ = match.groups()
                    data["maxis"][name.upper()] = float(price.replace(",", ""))
            elif section == "top_movers":
                match = re.search(r"(\w+)\s\((\w+)\).*?\$([\d,\.]+).*?([-+]?[\d\.]+)%", line)
                if match:
                    name, symbol, price, change = match.groups()
                    data["top_movers"].append({
                        "name": name,
                        "symbol": symbol,
                        "price": float(price.replace(",", "")),
                        "change_24h": float(change)
                    })
            elif section == "market_caps":
                match = re.search(r"(.+): \$([\d,\.]+)", line)
                if match:
                    sector, cap = match.groups()
                    data["market_caps"][sector.strip()] = float(cap.replace(",", ""))
            elif section == "tvl_data":
                match = re.search(r"(.+), TVL: \$([\d,\.]+)", line)
                if match:
                    name, tvl = match.groups()
                    data["tvl_data"].append({
                        "name": name.strip(),
                        "tvl": float(tvl.replace(",", ""))
                    })
            elif section == "inflows" or section == "outflows":
                match = re.search(r"(.+): TVL Change 1D: \$([-+]?[\d,\.]+)", line)
                if match:
                    name, change = match.groups()
                    data["chain_flows"].append({
                        "name": name.strip(),
                        "tvlChange1d": float(change.replace(",", ""))
                    })
            elif section == "news":
                match = re.search(r"(.+?) - (http.+)", line)
                if match:
                    title, _ = match.groups()
                    data["news"].append(title.strip())

    return data

def backfill():
    if not os.path.exists(REPORT_FOLDER):
        print("No reports folder found.")
        return

    files = sorted([
        f for f in os.listdir(REPORT_FOLDER)
        if f.endswith(".txt") and f.startswith("crypto_report_")
    ])

    accumulated = []
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r") as f:
            accumulated = json.load(f)

    existing_dates = {entry["date"] for entry in accumulated}

    for file in files:
        try:
            path = os.path.join(REPORT_FOLDER, file)
            parsed = parse_report(path)
            if parsed["date"] not in existing_dates:
                accumulated.append(parsed)
        except Exception as e:
            print(f"Failed to parse {file}: {e}")

    with open(OUTPUT_PATH, "w") as f:
        json.dump(sorted(accumulated, key=lambda x: x["date"]), f, indent=2)

    print(f"Backfilled {len(accumulated)} entries into {OUTPUT_PATH}")

if __name__ == "__main__":
    backfill()