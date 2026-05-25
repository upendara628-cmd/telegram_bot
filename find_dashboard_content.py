import os
import json
import logging
from playwright.sync_api import sync_playwright, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DashboardFinder")

def handle_response(response: Response):
    url = response.url
    if "api.campx.in" in url:
        print(f"[{response.request.method}] {url} ({response.status})")
        # Check if the response body contains attendance info
        try:
            if "application/json" in response.headers.get("content-type", ""):
                body = response.json()
                body_str = json.dumps(body)
                if "conducted" in body_str.lower() or "attended" in body_str.lower() or "attendance" in body_str.lower() or "subject" in body_str.lower():
                    print(f"    [INTERESTING API RESPONSE]: {url}")
                    print(f"    Data snippet: {body_str[:400]}...")
        except Exception as e:
            pass

def find():
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "chrome_profile"))
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.on("response", handle_response)
        
        dashboard_url = "https://mruh.campx.in/mruh/student-workspace/dashboard"
        logger.info(f"Navigating to: {dashboard_url}")
        page.goto(dashboard_url, timeout=60000)
        page.wait_for_timeout(5000)
        
        # Check if "Close" button is present and click it
        logger.info("Attempting to dismiss modal...")
        try:
            close_btn = page.locator("button[data-slot='dialog-close']").first
            if close_btn.count() > 0:
                logger.info("Found dialog-close button. Clicking it...")
                close_btn.click()
            else:
                logger.info("Pressing Escape...")
                page.keyboard.press("Escape")
        except Exception as e:
            logger.warning(f"Error dismissing modal: {e}")
            
        page.wait_for_timeout(8000)
        
        # Write text
        text = page.inner_text("body")
        with open("dashboard_page_text.txt", "w", encoding="utf-8") as f:
            f.write(text)
            
        page.screenshot(path="dashboard_page.png")
        context.close()

if __name__ == "__main__":
    find()
