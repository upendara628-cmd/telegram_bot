import os
import sys
import json
import logging
from playwright.sync_api import sync_playwright, Page

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CampXDirectLogin")

def try_login(page: Page, username: str, password: str) -> bool:
    timetable_url = "https://mruh.campx.in/mruh/student-workspace/timetable"
    logger.info(f"Navigating to timetable page: {timetable_url}")
    page.goto(timetable_url, timeout=60000)
    page.wait_for_timeout(5000) # Wait for redirects to settle
    
    # Check if already logged in
    url = page.url.lower()
    if "student-workspace" in url and "auth" not in url and "login" not in url:
        logger.info("Already logged in!")
        return True
        
    logger.info(f"Currently on URL: {page.url}. Attempting login for username: {username}")
    
    # Locate inputs
    username_field = None
    for sel in ["input[type='email']", "input[type='text']", "input[name*='username']", "input[placeholder*='username' i]", "input[placeholder*='email' i]"]:
        try:
            if page.locator(sel).count() > 0 and page.locator(sel).first.is_visible():
                username_field = page.locator(sel).first
                break
        except:
            continue
            
    password_field = None
    for sel in ["input[type='password']", "input[name*='password']"]:
        try:
            if page.locator(sel).count() > 0 and page.locator(sel).first.is_visible():
                password_field = page.locator(sel).first
                break
        except:
            continue
            
    if not username_field or not password_field:
        logger.error("Could not find username or password inputs on the login screen!")
        return False
        
    username_field.fill(username)
    password_field.fill(password)
    
    # Click submit
    submit_btn = None
    for sel in ["button[type='submit']", "button:has-text('Login')", "button:has-text('Sign In')", "input[type='submit']"]:
        try:
            if page.locator(sel).count() > 0 and page.locator(sel).first.is_visible():
                submit_btn = page.locator(sel).first
                break
        except:
            continue
            
    if submit_btn:
        logger.info("Clicking submit button...")
        submit_btn.click()
    else:
        logger.info("Pressing Enter...")
        password_field.press("Enter")
        
    # Wait up to 15 seconds for workspace redirect
    for i in range(15):
        page.wait_for_timeout(1000)
        curr_url = page.url.lower()
        if "student-workspace" in curr_url and "auth" not in curr_url and "login" not in curr_url:
            logger.info("✅ Login Succeeded!")
            return True
            
    logger.warning(f"❌ Login attempt failed to redirect. Current URL: {page.url}")
    return False

def main():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "r") as f:
        config = json.load(f)
        
    profile_dir = config.get("chrome_profile_dir", "chrome_profile")
    if not os.path.isabs(profile_dir):
        profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), profile_dir))
        
    os.makedirs(profile_dir, exist_ok=True)
    
    email = "2511cs020116@mallareddyuniversity.ac.in"
    roll_number = "2511cs020116"
    password = "151391"
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        success = False
        try:
            logger.info("--- ATTEMPTING LOGIN WITH EMAIL ---")
            success = try_login(page, email, password)
            
            if not success:
                logger.info("--- ATTEMPTING LOGIN WITH ROLL NUMBER ---")
                success = try_login(page, roll_number, password)
                
            if success:
                logger.info("SUCCESS: Browser session successfully authenticated.")
            else:
                logger.error("FAILURE: Login failed.")
        except Exception as e:
            logger.error(f"Error during login: {e}")
        finally:
            context.close()
            
    if success:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
