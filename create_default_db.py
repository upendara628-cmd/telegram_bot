import os
import json
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DBCreator")

def create():
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "chrome_profile"))
    db_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "database.json"))
    
    # Extract cookies
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
        
    user_info = {
        "email": "2511cs020116@mallareddyuniversity.ac.in",
        "password": "151391",
        "semNo": 2,
        "cookies": cookies_dict
    }
    
    db_data = {"users": {"default": user_info}}
    
    with open(db_file, "w", encoding="utf-8") as f:
        json.dump(db_data, f, indent=2)
        
    logger.info("Successfully created database.json with default user session.")

if __name__ == "__main__":
    create()
