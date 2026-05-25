"""
Intercepts API calls from both LMS and Assignments pages to find all endpoints.
"""
import sys, json, os, shutil
sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright

EMAIL = "2511cs020116@mallareddyuniversity.ac.in"
PASSWORD = "151391"
PROFILE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "chrome_profile_scan"))

all_captured = {}

def handle_response(response):
    url = response.url
    if "api.campx.in" in url and response.status == 200:
        try:
            body = response.json()
            all_captured[url] = body
            if isinstance(body, list):
                print(f"  [LIST:{len(body)}] {url}")
            else:
                print(f"  [DICT:{list(body.keys())[:3]}] {url}")
        except:
            pass

def visit_page(page, url, label):
    print(f"\n{'='*60}")
    print(f"VISITING: {label}")
    print(f"{'='*60}")
    page.goto(url, timeout=60000, wait_until="networkidle")
    page.wait_for_timeout(4000)
    # Scroll down to trigger lazy loading
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(3000)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(2000)

def run():
    if os.path.exists(PROFILE_DIR):
        shutil.rmtree(PROFILE_DIR)
    os.makedirs(PROFILE_DIR, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=True,
            viewport={"width": 1280, "height": 900},
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.on("response", handle_response)

        # Step 1: Login via timetable page first
        print("[*] Logging in...")
        page.goto("https://mruh.campx.in/mruh/student-workspace/timetable", timeout=60000)
        page.wait_for_selector("#loginId", timeout=30000)
        page.locator("#loginId").fill(EMAIL)
        page.locator("#password").fill(PASSWORD)
        page.locator("#password").press("Enter")
        print("[*] Waiting for login...")
        for _ in range(30):
            page.wait_for_timeout(1000)
            if "student-workspace" in page.url and "auth" not in page.url:
                break
        page.wait_for_timeout(3000)
        print(f"[+] Logged in! URL: {page.url}")

        # Step 2: Visit LMS page
        visit_page(page,
            "https://mruh.campx.in/mruh/student-workspace/learning-management",
            "LEARNING MANAGEMENT (Subjects)"
        )

        # Step 3: Visit Assignments page
        visit_page(page,
            "https://mruh.campx.in/mruh/student-workspace/integrated-assignments",
            "INTEGRATED ASSIGNMENTS"
        )

        context.close()

    # Save all results
    with open("all_pages_api_dump.json", "w", encoding="utf-8") as f:
        json.dump(all_captured, f, indent=2, default=str)

    print(f"\n\n{'='*60}")
    print(f"SUMMARY: {len(all_captured)} unique API endpoints captured")
    print(f"{'='*60}")
    for url, body in all_captured.items():
        if isinstance(body, list):
            print(f"  LIST({len(body):3d}) -> {url}")
            if body:
                # Show first item keys
                if isinstance(body[0], dict):
                    print(f"           keys: {list(body[0].keys())[:6]}")
        elif isinstance(body, dict):
            print(f"  DICT        -> {url}")
            print(f"           keys: {list(body.keys())[:6]}")

if __name__ == "__main__":
    run()
    if os.path.exists(PROFILE_DIR):
        shutil.rmtree(PROFILE_DIR)
