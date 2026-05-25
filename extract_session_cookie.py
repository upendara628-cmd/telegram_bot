"""
Auto-extracts fresh campx_session_key using Playwright (runs locally where Chrome is available).
Saves the cookie directly to database.json.
"""
import sys, json, os, shutil
sys.stdout.reconfigure(encoding='utf-8')

EMAIL = "2511cs020116@mallareddyuniversity.ac.in"
PASSWORD = "151391"
DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "database.json"))
PROFILE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "chrome_profile_autoextract"))

def extract_cookie():
    from playwright.sync_api import sync_playwright
    print("[*] Launching browser to extract fresh campx_session_key...")
    if os.path.exists(PROFILE_DIR):
        shutil.rmtree(PROFILE_DIR)
    os.makedirs(PROFILE_DIR, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=True,
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()

        print("[*] Navigating to CampX portal...")
        page.goto("https://mruh.campx.in/mruh/student-workspace/timetable", timeout=60000)

        print("[*] Waiting for login form...")
        page.wait_for_selector("#loginId", timeout=30000)

        print("[*] Filling credentials...")
        page.locator("#loginId").fill(EMAIL)
        page.locator("#password").fill(PASSWORD)
        page.locator("#password").press("Enter")

        print("[*] Waiting for dashboard redirect...")
        success = False
        for _ in range(30):
            page.wait_for_timeout(1000)
            if "student-workspace" in page.url and "auth" not in page.url:
                success = True
                break

        if not success:
            print(f"[X] Login failed! Current URL: {page.url}")
            context.close()
            return None

        print("[+] Logged in! Extracting cookies...")
        page.wait_for_timeout(3000)

        cookies_dict = {}
        for c in context.cookies():
            if c.get("domain", "") in [".campx.in", "mruh.campx.in", "api.campx.in"]:
                cookies_dict[c["name"]] = c["value"]

        context.close()

        session_key = cookies_dict.get("campx_session_key")
        if not session_key:
            print("[X] campx_session_key not found in cookies!")
            print(f"    Available cookies: {list(cookies_dict.keys())}")
            return None

        print(f"[+] Got session key: {session_key[:12]}...{session_key[-6:]}")
        return cookies_dict

def save_to_db(cookies_dict):
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
    except:
        db = {"users": {}}

    if "default" not in db["users"]:
        db["users"]["default"] = {}

    db["users"]["default"]["cookies"] = cookies_dict
    db["users"]["default"]["email"] = EMAIL
    db["users"]["default"]["password"] = PASSWORD
    db["users"]["default"]["semNo"] = db["users"]["default"].get("semNo", 2)

    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)

    print("[+] Saved to database.json!")
    return cookies_dict.get("campx_session_key")

if __name__ == "__main__":
    cookies = extract_cookie()
    if cookies:
        session_key = save_to_db(cookies)
        print("=" * 60)
        print("SUCCESS! Fresh cookie extracted and saved.")
        print("=" * 60)
        print(f"campx_session_key = {session_key}")
        print()
        print(">>> Set this as CAMPX_SESSION_KEY in Railway environment variables.")
        print("=" * 60)
    else:
        print("[X] Failed to extract cookie. Check your credentials.")

    if os.path.exists(PROFILE_DIR):
        shutil.rmtree(PROFILE_DIR)
