"""
Intercepts API calls made by the LMS page to find the subjects endpoint.
"""
import sys, json, os, shutil
sys.stdout.reconfigure(encoding='utf-8')

from playwright.sync_api import sync_playwright

EMAIL = "2511cs020116@mallareddyuniversity.ac.in"
PASSWORD = "151391"
PROFILE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "chrome_profile_lms"))

captured = []

def handle_response(response):
    url = response.url
    if "api.campx.in" in url and response.status == 200:
        try:
            body = response.json()
            captured.append({"url": url, "body": body})
            print(f"[API] {response.status} {url}")
        except:
            pass

def run():
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
        page.on("response", handle_response)

        print("[*] Navigating to LMS page...")
        page.goto("https://mruh.campx.in/mruh/student-workspace/learning-management", timeout=60000)

        print("[*] Waiting for login form...")
        page.wait_for_selector("#loginId", timeout=30000)

        print("[*] Logging in...")
        page.locator("#loginId").fill(EMAIL)
        page.locator("#password").fill(PASSWORD)
        page.locator("#password").press("Enter")

        print("[*] Waiting for LMS page to load...")
        for _ in range(40):
            page.wait_for_timeout(1000)
            if "learning-management" in page.url and "auth" not in page.url:
                break

        # Extra wait for all API calls to fire
        page.wait_for_timeout(5000)
        print(f"\n[+] Captured {len(captured)} API responses")

        context.close()

    # Save full results
    with open("lms_api_dump.json", "w", encoding="utf-8") as f:
        json.dump(captured, f, indent=2, default=str)
    print("[+] Saved to lms_api_dump.json")

    # Print summary
    print("\n=== API ENDPOINTS FOUND ===")
    for item in captured:
        url = item["url"]
        body = item["body"]
        if isinstance(body, list):
            print(f"  LIST({len(body)}) -> {url}")
        elif isinstance(body, dict):
            keys = list(body.keys())[:5]
            print(f"  DICT{keys} -> {url}")

if __name__ == "__main__":
    run()
    if os.path.exists(PROFILE_DIR):
        shutil.rmtree(PROFILE_DIR)
