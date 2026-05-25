import os
import json
import logging
from playwright.sync_api import sync_playwright
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TimetableDumper")

def dump():
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
        
    # 2. Build headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/148.0.7778.96 Safari/537.36",
        "Referer": "https://mruh.campx.in/",
        "Origin": "https://mruh.campx.in",
        "accept": "application/json, text/plain, */*",
        "x-institution-code": "mruh",
        "x-platform-id": "campx",
        "x-tenant-id": "mruh"
    }
    
    # 3. Request
    with httpx.Client(cookies=cookies_dict, headers=headers) as client:
        r = client.get("https://api.campx.in/student-api/classroom-timetables")
        if r.status_code == 200:
            data = r.json()
            with open("timetable_data.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Successfully dumped {len(data)} timetable entries to timetable_data.json")
            
            # Print first 3 entries
            print("\n=== SAMPLE TIMETABLE ENTRIES ===")
            for i, entry in enumerate(data[:3]):
                print(f"\nEntry {i+1}:")
                print(json.dumps(entry, indent=2))
        else:
            logger.error(f"Failed to fetch timetable: {r.status_code} {r.text}")

if __name__ == "__main__":
    dump()
