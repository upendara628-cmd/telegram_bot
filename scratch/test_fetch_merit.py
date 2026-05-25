import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
from scraper import fetch_merit_data

email = "2511cs020116@mallareddyuniversity.ac.in"
try:
    data = fetch_merit_data(email)
    print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")
