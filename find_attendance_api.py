import os
import json
import logging
from playwright.sync_api import sync_playwright, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AttendanceFinder")

def handle_response(response: Response):
    url = response.url
    if "api.campx.in" in url:
        print(f"[{response.request.method}] {url} ({response.status})")

def find():
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "chrome_profile"))
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.on("response", handle_response)
        
        # Navigate directly to attendance
        attendance_url = "https://mruh.campx.in/mruh/student-workspace/attendance"
        logger.info(f"Navigating to attendance: {attendance_url}")
        page.goto(attendance_url, timeout=60000)
        page.wait_for_timeout(10000)
        
        context.close()

if __name__ == "__main__":
    find()
