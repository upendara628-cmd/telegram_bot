import os
import json
import logging
from playwright.sync_api import sync_playwright, Page

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TestLogin")

def try_login(page: Page, username: str, password: str) -> bool:
    timetable_url = "https://mruh.campx.in/mruh/student-workspace/timetable"
    logger.info(f"Navigating to timetable page for login attempt with username: {username} and password: {password}")
    page.goto(timetable_url, timeout=60000)
    page.wait_for_timeout(3000)
    
    # Check if already logged in
    url = page.url.lower()
    if "student-workspace" in url and "login" not in url and "auth" not in url:
        logger.info("Already logged in!")
        return True
        
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
        # Let's save a screenshot
        page.screenshot(path="login_error.png")
        with open("login_error.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        return False
        
    username_field.fill(username)
    password_field.fill(password)
    
    submit_btn = None
    for sel in ["button[type='submit']", "button:has-text('Login')", "button:has-text('Sign In')", "input[type='submit']"]:
        try:
            if page.locator(sel).count() > 0 and page.locator(sel).first.is_visible():
                submit_btn = page.locator(sel).first
                break
        except:
            continue
            
    if submit_btn:
        submit_btn.click()
    else:
        password_field.press("Enter")
        
    # Wait for login
    for i in range(15):
        page.wait_for_timeout(1000)
        curr_url = page.url.lower()
        if "student-workspace" in curr_url and "auth" not in curr_url:
            logger.info("✅ Login Succeeded!")
            page.screenshot(path="login_success.png")
            return True
        if "login" in curr_url or "auth" in curr_url:
            # Check if there is an error message visible on page
            body_text = page.inner_text("body").lower()
            if "invalid" in body_text or "incorrect" in body_text or "failed" in body_text:
                logger.warning(f"Failed indicator in body text at second {i}")
                
    logger.warning("❌ Login attempt did not redirect to student workspace. Current URL: " + page.url)
    page.screenshot(path="login_failed_final.png")
    with open("login_failed_final.html", "w", encoding="utf-8") as f:
        f.write(page.content())
    return False

def main():
    profile_dir = "chrome_profile_test"
    email = "2511cs020116@mallareddyuniversity.ac.in"
    
    passwords = ["mruh portel", "mruh portal", "151391"]
    
    with sync_playwright() as p:
        # Launch persistent context
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        for pwd in passwords:
            logger.info(f"Trying password: '{pwd}'")
            if try_login(page, email, pwd):
                logger.info(f"SUCCESS with password: '{pwd}'")
                context.close()
                return
            else:
                logger.warning(f"FAILED with password: '{pwd}'")
                
        context.close()
        logger.error("All password attempts failed.")

if __name__ == "__main__":
    main()
