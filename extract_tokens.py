import os
import json
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TokenExtractor")

def extract():
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
        
        timetable_url = "https://mruh.campx.in/mruh/student-workspace/timetable"
        logger.info(f"Navigating to timetable to extract storage: {timetable_url}")
        page.goto(timetable_url, timeout=60000)
        page.wait_for_timeout(5000)
        
        logger.info(f"Current page URL: {page.url}")
        
        # Extract localStorage
        local_storage = page.evaluate("() => JSON.stringify(window.localStorage)")
        storage_dict = json.loads(local_storage)
        print("\n=== LOCAL STORAGE KEYS & VALUES ===")
        for k, v in storage_dict.items():
            # If value is long, truncate it
            val_str = str(v)
            if len(val_str) > 100:
                val_str = val_str[:100] + "... (truncated)"
            print(f"{k}: {val_str}")
            
        # Extract sessionStorage
        session_storage = page.evaluate("() => JSON.stringify(window.sessionStorage)")
        sess_dict = json.loads(session_storage)
        print("\n=== SESSION STORAGE KEYS & VALUES ===")
        for k, v in sess_dict.items():
            val_str = str(v)
            if len(val_str) > 100:
                val_str = val_str[:100] + "... (truncated)"
            print(f"{k}: {val_str}")
            
        # Also print cookies
        cookies = context.cookies()
        print("\n=== COOKIES ===")
        for cookie in cookies:
            print(f"{cookie.get('name')}: {cookie.get('value')[:50]}... Domain={cookie.get('domain')}")
            
        context.close()

if __name__ == "__main__":
    extract()
