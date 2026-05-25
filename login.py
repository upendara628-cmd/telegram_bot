import os
import json
import sys
import random
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CampXAutoLogin")

def get_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found at {config_path}")
        sys.exit(1)
    with open(config_path, "r") as f:
        return json.load(f)

def type_humanlike(page, selector, text):
    """Types text character by character with random delays to mimic human behavior."""
    page.focus(selector)
    # Clear field first
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    for char in text:
        page.keyboard.type(char)
        page.wait_for_timeout(random.randint(50, 150))

def run_login():
    config = get_config()
    
    # Resolve absolute path for profile directory
    profile_dir = config.get("chrome_profile_dir", "chrome_profile")
    if not os.path.isabs(profile_dir):
        profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), profile_dir))
        
    logger.info(f"Using persistent Chrome user profile directory at:\n  {profile_dir}")
    os.makedirs(profile_dir, exist_ok=True)
    
    timetable_url = config.get("timetable_url", "https://mruh.campx.in/mruh/student-workspace/timetable")
    
    # Prompt user for credentials if not supplied (helps automate execution)
    print("\n--- Portal Credentials for Automation ---")
    email = input("Enter your portal Google Email (leave blank to type manually in browser): ").strip()
    password = ""
    if email:
        password = input("Enter your portal Google Password (leave blank to type manually in browser): ").strip()
        
    print("\nStarting browser in headful mode. Please wait...")
    
    with sync_playwright() as p:
        # Launch persistent context with anti-detection flags
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            viewport=None,  # Use default viewport size
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"  # Critical to bypass Google security
            ]
        )
        
        # Inject script to remove navigator.webdriver flag
        context.add_init_script(
            "const newProto = navigator.__proto__; delete newProto.webdriver; navigator.__proto__ = newProto;"
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        logger.info(f"Navigating to: {timetable_url}")
        page.goto(timetable_url, timeout=60000)
        page.wait_for_timeout(3000)  # Wait for SPA redirect
        
        # Check if already logged in
        if "student-workspace" in page.url and not any(k in page.url for k in ["login", "signin"]):
            logger.info("Already logged in! Exiting setup.")
            context.close()
            return
            
        # Attempt Google SSO Automation if credentials were provided
        automated_success = False
        if email and password:
            try:
                logger.info("Attempting automated Google login flow...")
                
                # 1. Click "Sign in with Google" button
                google_sso_btn = page.locator("button:has-text('Sign in with Google'), a:has-text('Sign in with Google'), .login-btn:has-text('Google')")
                if google_sso_btn.count() > 0:
                    google_sso_btn.first.click()
                else:
                    # Fallback click on text match
                    page.click("text=Sign in with Google", timeout=10000)
                
                # Wait for Google Sign-In page to render
                page.wait_for_selector("input[type='email']", timeout=15000)
                page.wait_for_timeout(1000)
                
                # 2. Type Email
                logger.info("Typing Google email...")
                type_humanlike(page, "input[type='email']", email)
                page.wait_for_timeout(500)
                
                # Click "Next"
                # Selectors for Google Next buttons:
                next_selectors = ["#identifierNext", "button:has-text('Next')", "#identifierNext button"]
                clicked_next = False
                for sel in next_selectors:
                    if page.locator(sel).count() > 0:
                        page.click(sel)
                        clicked_next = True
                        break
                if not clicked_next:
                    page.keyboard.press("Enter")
                    
                # 3. Wait for Password page
                logger.info("Waiting for password field...")
                page.wait_for_selector("input[type='password']", timeout=15000)
                page.wait_for_timeout(1500)
                
                # 4. Type Password
                logger.info("Typing Google password...")
                type_humanlike(page, "input[type='password']", password)
                page.wait_for_timeout(500)
                
                # Click "Next"
                pwd_selectors = ["#passwordNext", "button:has-text('Next')", "#passwordNext button"]
                clicked_pwd = False
                for sel in pwd_selectors:
                    if page.locator(sel).count() > 0:
                        page.click(sel)
                        clicked_pwd = True
                        break
                if not clicked_pwd:
                    page.keyboard.press("Enter")
                    
                # 5. Handle 2-Factor Authentication or Success Redirection
                logger.info("Checking for login redirection or 2FA prompts...")
                # We wait up to 90 seconds in case they have phone prompt approvals
                for i in range(90):
                    page.wait_for_timeout(1000)
                    current_url = page.url
                    # If we redirect back to CampX student workspace
                    if "student-workspace" in current_url and "auth" not in current_url:
                        logger.info("✅ Login automated successfully!")
                        automated_success = True
                        break
                    # Check if Google blocks us
                    if "deniedsignin" in current_url or "rejected" in current_url:
                        logger.warning("Google SSO rejected automated entry due to security policies.")
                        break
                        
            except Exception as e:
                logger.warning(f"SSO automation encountered an issue: {e}")
                logger.info("Falling back to manual browser control...")
                
        # Fallback to Manual Login Mode if automation was skipped or failed
        if not automated_success:
            print("\n" + "="*80)
            print("MANUAL FALLBACK MODE:")
            print("1. Complete the Google Sign-In manually in the open Chrome browser window.")
            print("2. Navigate until you see your student workspace dashboard / timetable.")
            print("3. Return to this console and press ENTER to save your session.")
            print("="*80 + "\n")
            
            input("--> Press ENTER here once you have successfully logged in: ")
            
        logger.info("Saving browser session profile and closing browser context...")
        context.close()
        logger.info("Setup finished successfully! You can now run the bot.")

if __name__ == "__main__":
    run_login()
