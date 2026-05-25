import os
import json
import logging
from playwright.sync_api import sync_playwright
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HeaderTest")

def test():
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "chrome_profile"))
    
    # 1. Extract cookies
    cookies_dict = {}
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        cookies = context.cookies()
        for cookie in cookies:
            if cookie.get("domain") in [".campx.in", "mruh.campx.in", "api.campx.in"]:
                cookies_dict[cookie.get("name")] = cookie.get("value")
        context.close()
        
    logger.info(f"Cookies: {cookies_dict}")
    
    # 2. Build headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/148.0.7778.96 Safari/537.36",
        "Referer": "https://mruh.campx.in/",
        "Origin": "https://mruh.campx.in",
        "accept": "application/json, text/plain, */*",
        "x-institution-code": "mruh",
        "x-platform-id": "campx",
        "x-tenant-id": "mruh",
        "x-campx-client": "eyJjbGllbnRJZCI6ImVmYTRkZGFiLTMwMzEtNDM3MC1hZDc3LTQ2NTU3ZDRmMDg5MCIsImlhdCI6MTc3OTczOTM1OH0.g0lZvJo1PsN83yZ_zBDTtVIwdvUMVgJrUd7kjzXKQMk"
    }
    
    # Let's test with and without x-campx-client
    with httpx.Client(cookies=cookies_dict, headers=headers) as client:
        r_time_full = client.get("https://api.campx.in/student-api/classroom-timetables")
        print(f"With all headers - Timetable status: {r_time_full.status_code}")
        if r_time_full.status_code == 200:
            print(f"Successfully retrieved timetable entries: {len(r_time_full.json())}")
            
    # Try without x-campx-client
    headers_no_client = headers.copy()
    del headers_no_client["x-campx-client"]
    with httpx.Client(cookies=cookies_dict, headers=headers_no_client) as client:
        r_time_no_client = client.get("https://api.campx.in/student-api/classroom-timetables")
        print(f"Without x-campx-client - Timetable status: {r_time_no_client.status_code}")

if __name__ == "__main__":
    test()
