import os
import json
import sys
import logging
from datetime import datetime, timezone
import httpx
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("MUDUAutoLogin")

def get_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found at {config_path}")
        sys.exit(1)
    with open(config_path, "r") as f:
        return json.load(f)

def run_login():
    config = get_config()
    db_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "database.json"))
    
    print("\n" + "=" * 60)
    print("      MRU MUDU Portal Session Setup Utility")
    print("=" * 60)
    
    identifier = input("Enter your MUDU Roll Number or Email (e.g., 2511CS020116): ").strip()
    if not identifier:
        print("Roll number / email is required.")
        return
        
    password = input("Enter your MUDU Password: ").strip()
    if not password:
        print("Password is required.")
        return

    # Attempt fast direct API authentication
    print("\nAttempting fast direct API authentication...")
    from scraper import login_mudu_api, save_user_data, ScrapingError
    try:
        user_info = login_mudu_api(identifier, password)
        save_user_data("default", user_info)
        print("\n" + "=" * 60)
        print("✅ SUCCESS! Logged in via MUDU API.")
        print(f"👤 Name: {user_info.get('fullName')}")
        print(f"🎓 Roll No: {user_info.get('rollNo')}")
        print(f"🏷️ Section ID: {user_info.get('sectionId')}")
        print(f"Session saved to database.json under 'default'.")
        print("=" * 60 + "\n")
        return
    except ScrapingError as se:
        print(f"Direct API login failed: {se}")
        print("Falling back to headful browser login...")

    # Headful browser fallback
    profile_dir = config.get("chrome_profile_dir", "chrome_profile")
    if not os.path.isabs(profile_dir):
        profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), profile_dir))
    os.makedirs(profile_dir, exist_ok=True)

    print("\nStarting Chrome browser window. Please complete login in browser if needed...")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        login_url = "https://mru.mudu.in/login"
        page.goto(login_url, timeout=60000)
        
        try:
            page.wait_for_selector("#email", timeout=15000)
            page.locator("#email").fill(identifier)
            page.locator("#password").fill(password)
            page.locator("button[type='submit']").click()
        except Exception as e:
            logger.info("Automatic form filling encountered an issue; please enter details in the open browser.")

        print("\nWaiting for you to log in in the browser window...")
        input("--> Press ENTER here once you are logged in to the MUDU dashboard: ")
        
        cookies_list = context.cookies()
        cookies_dict = {c["name"]: c["value"] for c in cookies_list if "mudu.in" in c.get("domain", "")}
        context.close()

    # Save to database.json
    from scraper import _validate_mudu_cookie
    user_info = _validate_mudu_cookie(cookies_dict, identifier)
    user_info["password"] = password
    save_user_data("default", user_info)
    print("✅ Setup finished successfully! Session saved.")

if __name__ == "__main__":
    run_login()
