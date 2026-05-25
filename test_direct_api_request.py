import os
import json
import logging
from playwright.sync_api import sync_playwright
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DirectAPITest")

def test():
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "chrome_profile"))
    
    # 1. Extract cookies from playwright
    logger.info("Extracting cookies from Chrome profile...")
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
        
    logger.info(f"Extracted cookies: {cookies_dict}")
    
    # 2. Perform direct HTTP requests
    logger.info("Performing direct HTTP requests...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://mruh.campx.in/",
        "Origin": "https://mruh.campx.in"
    }
    
    with httpx.Client(cookies=cookies_dict, headers=headers) as client:
        # Test workspaces
        r_work = client.get("https://api.campx.in/auth-server/auth-v2/workspaces")
        print(f"\nWorkspaces status: {r_work.status_code}")
        print("Workspaces response snippet:")
        print(r_work.text[:500])
        
        # Test timetable
        r_time = client.get("https://api.campx.in/student-api/classroom-timetables")
        print(f"\nTimetable status: {r_time.status_code}")
        print("Timetable response size:", len(r_time.text))
        if r_time.status_code == 200:
            try:
                data = r_time.json()
                print(f"Number of timetable entries: {len(data)}")
                if data:
                    print("First entry sample:")
                    print(json.dumps(data[0], indent=2)[:500])
            except Exception as e:
                print("Error parsing timetable JSON:", e)

if __name__ == "__main__":
    test()
