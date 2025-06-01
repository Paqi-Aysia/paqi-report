import json
import os

path = "/mnt/data/accumulated.json"
dates_to_remove = {"2025-05-19", "2025-05-20"} #update dates you want to clean here

if os.path.exists(path):
    with open(path, "r") as f:
        data = json.load(f)

    original_len = len(data)
    data = [entry for entry in data if entry.get("date") not in dates_to_remove]

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"✅ Removed entries for {dates_to_remove}.")
    print(f"🗂️  {original_len - len(data)} entries deleted. {len(data)} remain.")
else:
    print("❌ accumulated.json not found.")