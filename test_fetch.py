import sys
from scraper import fetch_mru_results, AuthenticationRequiredError

email = "test@example.com"
try:
    results = fetch_mru_results(email)
    print('Results keys:', list(results.keys()))
except AuthenticationRequiredError as e:
    print('Authentication error as expected:', e)
except Exception as e:
    print('Other error:', e)
