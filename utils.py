# utils.py
import os
import requests
import logging

def fetch_json(url, params=None):
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.warning(f"Request to {url} failed: {e}")
        return None

def ensure_folder(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)