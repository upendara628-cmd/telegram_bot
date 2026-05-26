import json, os, sys
sys.path.append(os.getcwd())
from scraper import fetch_mru_results

email = "2511cs020116@mallareddyuniversity.ac.in"
try:
    results = fetch_mru_results(email)
    print(json.dumps(results, indent=2)[:1000])
except Exception as e:
    print('Error:', e)
