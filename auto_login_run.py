import os
import json
import sys
import random
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CampXAutoRun")

def type_humanlike(page, selector, text):
    page.focus(selector)
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    for char in text:
        page.keyboard.type(char)
        page.wait_for_timeout(random.randint(50, 120))

def run_auto_login():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "r") as f:
        config = json.load(f)
        
    profile_dir = config.get("chrome_profile_dir", "chrome_profile")
    if not os.path.isabs(profile_dir):
        profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), profile_dir))
        
    os.makedirs(profile_dir, exist_ok=True)
    
    email = "2511cs020116@mallareddyuniversity.ac.in"
    password = "151391"
    timetable_url = config.get("timetable_url", "https://mruh.campx.in/mruh/student-workspace/timetable")
    
    logger.info("Starting automated Chrome login process...")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,  # Visible browser so user can see Google login
            viewport=None,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        
        context.add_init_script(
            "const newProto = navigator.__proto__; delete newProto.webdriver; navigator.__proto__ = newProto;"
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        logger.info(f"Navigating to timetable page: {timetable_url}")
        page.goto(timetable_url, timeout=60000)
        page.wait_for_timeout(3000)
        
        # Check if already logged in
        if "student-workspace" in page.url and not any(k in page.url for k in ["login", "signin"]):
            logger.info("Already logged in! Closing.")
            context.close()
            return
            
        try:
            logger.info("Clicking Sign in with Google...")
            # Click Google Login Button
            google_sso_btn = page.locator("button:has-text('Sign in with Google'), a:has-text('Sign in with Google'), .login-btn:has-text('Google')")
            if google_sso_btn.count() > 0:
                google_sso_btn.first.click()
            else:
                page.click("text=Sign in with Google", timeout=10000)
                
            # Wait for email input
            page.wait_for_selector("input[type='email']", timeout=15000)
            page.wait_for_timeout(1000)
            
            # Type Email
            logger.info("Entering Google email...")
            type_humanlike(page, "input[type='email']", email)
            page.wait_for_timeout(500)
            
            # Next button
            next_selectors = ["#identifierNext", "button:has-text('Next')", "#identifierNext button"]
            clicked_next = False
            for sel in next_selectors:
                if page.locator(sel).count() > 0:
                    page.click(sel)
                    clicked_next = True
                    break
            if not clicked_next:
                page.keyboard.press("Enter")
                
            # Wait for password input
            logger.info("Waiting for password input...")
            page.wait_for_selector("input[type='password']", timeout=15000)
            page.wait_for_timeout(1500)
            
            # Type Password
            logger.info("Entering Google password...")
            type_humanlike(page, "input[type='password']", password)
            page.wait_for_timeout(500)
            
            # Click next
            pwd_selectors = ["#passwordNext", "button:has-text('Next')", "#passwordNext button"]
            clicked_pwd = False
            for sel in pwd_selectors:
                if page.locator(sel).count() > 0:
                    page.click(sel)
                    clicked_pwd = True
                    break
            if not clicked_pwd:
                page.keyboard.press("Enter")
                
            # Wait for 2FA or redirection
            logger.info("Waiting for login confirmation or 2-Factor Authentication tap on your phone...")
            logger.info("If your phone prompts you to verify this login, please tap YES now.")
            
            # Wait up to 90 seconds for redirection
            success = False
            for i in range(90):
                page.wait_for_timeout(1000)
                if "student-workspace" in page.url and "auth" not in page.url:
                    logger.info("✅ Login automation succeeded!")
                    success = True
                    break
                    
            if not success:
                logger.error("Failed to login automatically. Please make sure to approve phone notifications.")
                
        except Exception as e:
            logger.error(f"Login failed: {e}")
            
        logger.info("Closing browser session and saving context...")
        context.close()
        logger.info("Done!")

if __name__ == "__main__":
    run_auto_login()
