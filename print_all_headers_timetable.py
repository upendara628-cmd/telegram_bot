import os
import json
import logging
from playwright.sync_api import sync_playwright, Request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HeaderDumper")

def handle_request(request: Request):
    url = request.url
    if "classroom-timetables" in url:
        print(f"\n>>> TIMETABLE REQUEST HEADERS:")
        try:
            headers = request.all_headers()
            for k, v in headers.items():
                print(f"    {k}: {v}")
        except Exception as e:
            print(f"    Error: {e}")

def trace():
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "chrome_profile"))
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.on("request", handle_request)
        
        logger.info("Navigating to timetable page...")
        page.goto("https://mruh.campx.in/mruh/student-workspace/timetable", timeout=60000)
        page.wait_for_timeout(10000)
        
        context.close()

if __name__ == "__main__":
    trace()
