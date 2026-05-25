import os
import json
import logging
from playwright.sync_api import sync_playwright, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JWTCapturer")

def handle_response(response: Response):
    url = response.url
    if "classroom-timetables" in url:
        headers = response.request.headers
        auth = headers.get("authorization") or headers.get("Authorization")
        if auth:
            print("\n" + "="*80)
            print("FOUND AUTHORIZATION TOKEN FOR TIMETABLE:")
            print(auth)
            print("="*80 + "\n")
            # Write it to a file for easy use
            with open("jwt_token.txt", "w") as f:
                f.write(auth)

def capture():
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
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.on("response", handle_response)
        
        logger.info("Navigating to timetable page...")
        page.goto("https://mruh.campx.in/mruh/student-workspace/timetable", timeout=60000)
        page.wait_for_timeout(8000)
        
        context.close()

if __name__ == "__main__":
    capture()
