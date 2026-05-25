import os
import shutil
import json
import logging
from playwright.sync_api import sync_playwright, Page, Response

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ForceLogin")

jwt_token = None

def handle_response(response: Response):
    global jwt_token
    url = response.url
    if "classroom-timetables" in url or "workspaces" in url:
        headers = response.request.headers
        auth = headers.get("authorization") or headers.get("Authorization")
        if auth and not jwt_token:
            jwt_token = auth
            logger.info(f"Captured JWT Token: {jwt_token}")
            with open("jwt_token.txt", "w") as f:
                f.write(jwt_token)

def main():
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "chrome_profile"))
    
    # Clean the profile directory
    logger.info(f"Cleaning profile directory: {profile_dir}")
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir)
            logger.info("Successfully cleaned profile directory.")
        except Exception as e:
            logger.warning(f"Error cleaning directory: {e}.")
            
    os.makedirs(profile_dir, exist_ok=True)
    
    email = "2511cs020116@mallareddyuniversity.ac.in"
    password = "151391"
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.on("response", handle_response)
        
        timetable_url = "https://mruh.campx.in/mruh/student-workspace/timetable"
        logger.info(f"Navigating to: {timetable_url}")
        page.goto(timetable_url, timeout=60000)
        
        logger.info("Waiting for login inputs (#loginId) to load...")
        try:
            page.wait_for_selector("#loginId", timeout=30000)
            logger.info("Login inputs detected.")
        except Exception as e:
            logger.error(f"Timeout waiting for #loginId: {e}")
            page.screenshot(path="force_login_load_error.png")
            with open("force_login_load_error.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            context.close()
            return
            
        username_field = page.locator("#loginId")
        password_field = page.locator("#password")
        
        logger.info("Entering credentials...")
        username_field.fill(email)
        password_field.fill(password)
        
        # Click submit button or press Enter
        password_field.press("Enter")
        
        # Wait up to 20 seconds for workspace redirect and token capture
        logger.info("Waiting for redirect and auth token capture...")
        success = False
        for i in range(25):
            page.wait_for_timeout(1000)
            curr_url = page.url.lower()
            if "student-workspace" in curr_url and "auth" not in curr_url:
                logger.info("✅ Redirect to workspace detected!")
                success = True
                break
                
        if success:
            # Let the page render and perform API requests
            page.wait_for_timeout(5000)
            logger.info("Login finished successfully. Session is saved.")
            page.screenshot(path="force_login_success.png")
        else:
            logger.error(f"Failed to redirect. Current URL: {page.url}")
            page.screenshot(path="force_login_failed.png")
            with open("force_login_failed.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            
        context.close()

if __name__ == "__main__":
    main()
