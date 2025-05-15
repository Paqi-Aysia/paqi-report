# utils.py
import os
import requests
import logging
import time

def fetch_json(url, params=None, retries=6, delay=3, backoff=2):
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logging.warning(f"Request to {url} failed (attempt {attempt + 1}): {e}")
            time.sleep(delay)
            delay *= backoff  # Exponential backoff
    return None

def ensure_folder(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)