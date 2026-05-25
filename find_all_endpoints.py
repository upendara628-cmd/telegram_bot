import os
import json
import logging
from playwright.sync_api import sync_playwright, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EndpointFinder")

def handle_response(response: Response):
    url = response.url
    method = response.request.method
    status = response.status
    if "api" in url or "campx" in url:
        print(f"[{method}] {url} ({status})")
        # Check if we can get request headers to see the Auth token
        headers = response.request.headers
        auth = headers.get("authorization") or headers.get("Authorization")
        if auth:
            print(f"    Authorization: {auth[:50]}...")

def find_endpoints():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "r") as f:
        config = json.load(f)
        
    profile_dir = config.get("chrome_profile_dir", "chrome_profile")
    if not os.path.isabs(profile_dir):
        profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), profile_dir))
        
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.on("response", handle_response)
        
        logger.info("--- NAVIGATING TO DASHBOARD ---")
        page.goto("https://mruh.campx.in/mruh/student-workspace/dashboard", timeout=45000)
        page.wait_for_timeout(10000)
        
        logger.info("--- NAVIGATING TO TIMETABLE ---")
        page.goto("https://mruh.campx.in/mruh/student-workspace/timetable", timeout=45000)
        page.wait_for_timeout(10000)
        
        logger.info("--- NAVIGATING TO ATTENDANCE ---")
        page.goto("https://mruh.campx.in/mruh/student-workspace/attendance", timeout=45000)
        page.wait_for_timeout(10000)
        
        context.close()

if __name__ == "__main__":
    find_endpoints()
