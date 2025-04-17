import requests

url = "https://api.coingecko.com/api/v3/coins/categories"

try:
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        categories = response.json()
        category_id = [category["id"] for category in categories]
        print("Category IDs:")
        print(category_id)
    else:
        print(f"Error: Received status code {response.status_code}")
except requests.exceptions.RequestException as e:
    print(f"Error: {e}")


#import json

#url = "https://api.coingecko.com/api/v3/coins/categories"
#response = requests.get(url)
#if response.status_code == 200:
    #categories_data = response.json()
    # Pretty-print the response for inspection
    #print(json.dumps(categories_data, indent=2))
#else:
    #print(f"Error fetching categories: {response.status_code}")