import json
import os
import re

# File paths
report_path = "data/reports/crypto_report_2025_04_18.txt" #change crypto report file in path for other data to import
accumulated_path = "/mnt/data/accumulated.json"

# Load the report text
with open(report_path, "r") as f:
    content = f.read()

# Extract date
date_match = re.search(r"Crypto Market Report - (\d{4}-\d{2}-\d{2})", content)
if not date_match:
    raise ValueError("Could not extract date from report.")
date = date_match.group(1)

# Extract BTC and ETH prices
btc_match = re.search(r"Bitcoin \(BTC\): Current Price \$(\d+(?:\.\d+)?)", content)
eth_match = re.search(r"Ethereum \(ETH\): Current Price \$(\d+(?:\.\d+)?)", content)
btc_price = float(btc_match.group(1)) if btc_match else None
eth_price = float(eth_match.group(1)) if eth_match else None

# Extract top movers
top_movers = []
mover_section = re.findall(r"Top Movers.*?\n((?:.+?: \$.*?%\n)+)", content, re.DOTALL)
if mover_section:
    lines = mover_section[0].strip().splitlines()
    for line in lines:
        match = re.match(r"(.+?) \((.+?)\): \$([0-9.]+) \| 24-Hour Change: ([\d\.\-]+)%", line)
        if match:
            name, symbol, price, change = match.groups()
            top_movers.append({
                "name": name.strip(),
                "symbol": symbol.strip(),
                "price": float(price),
                "change_24h": float(change)
            })

# Extract market caps
market_caps = {}
cap_lines = re.findall(r"Aggregate Market Capitalizations:\n((?:.+?: \$[0-9,]+\.\d+\n)+)", content)
if cap_lines:
    for line in cap_lines[0].strip().splitlines():
        sector, value = line.split(": $")
        market_caps[sector.strip()] = float(value.replace(",", ""))

# Extract TVL data
tvl_data = []
tvl_lines = re.findall(r"TVL Data.*?\n((?:.+?, TVL: \$[0-9.]+\n)+)", content)
if tvl_lines:
    for line in tvl_lines[0].strip().splitlines():
        if ", TVL: $" in line:
            name, val = line.split(", TVL: $")
            tvl_data.append({"name": name.strip(), "tvl": float(val)})

# Extract chain flows
inflow = []
outflow = []
inflow_lines = re.findall(r"Top Chains by Inflow:\n((?:.+?: TVL Change 1D: \$[\d,.\-]+\n)+)", content)
if inflow_lines:
    for line in inflow_lines[0].strip().splitlines():
        name, val = line.split(": TVL Change 1D: $")
        inflow.append({"name": name.strip(), "tvlChange1d": float(val.replace(",", ""))})
outflow_lines = re.findall(r"Top Chains by Outflow:\n((?:.+?: TVL Change 1D: \$[\d,.\-]+\n)+)", content)
if outflow_lines:
    for line in outflow_lines[0].strip().splitlines():
        name, val = line.split(": TVL Change 1D: $")
        outflow.append({"name": name.strip(), "tvlChange1d": float(val.replace(",", ""))})

# Extract news headlines
news = re.findall(r"Hot News:\n((?:.+ - https?://[^\n]+\n)+)", content)
news_titles = []
if news:
    for line in news[0].strip().splitlines():
        title = line.split(" - ")[0].strip()
        news_titles.append(title)

# Combine structured data
entry = {
    "date": date,
    "maxis": {"BTC": btc_price, "ETH": eth_price},
    "top_movers": top_movers,
    "market_caps": market_caps,
    "tvl_data": tvl_data,
    "chain_flows": inflow + outflow,
    "news": news_titles[:5]
}

# Load and update accumulated.json
if os.path.exists(accumulated_path):
    with open(accumulated_path, "r") as f:
        accumulated_data = json.load(f)
else:
    accumulated_data = []

# Replace if date already exists and sort by date
accumulated_data = [e for e in accumulated_data if e["date"] != date]
accumulated_data.append(entry)
accumulated_data = sorted(accumulated_data, key=lambda x: x["date"])

with open(accumulated_path, "w") as f:
    json.dump(accumulated_data, f, indent=2)

print(f"✅ Appended data for {date} to accumulated.json.")