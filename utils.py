# utils.py
import os
import requests
import logging
import time

def fetch_json(url, params=None, max_retries=5, base_delay=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                wait = base_delay * (2 ** attempt)  # Exponential backoff
                logging.warning(f"429 Too Many Requests for {url} — retrying in {wait}s...")
                time.sleep(wait)
            else:
                logging.warning(f"HTTP error for {url}: {e}")
                break
        except requests.RequestException as e:
            logging.warning(f"Request to {url} failed: {e}")
            break
    return None

def ensure_folder(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)