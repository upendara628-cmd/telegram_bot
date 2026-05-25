import os
import json
import logging
from playwright.sync_api import sync_playwright, Request, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NetworkTracer")

def handle_request(request: Request):
    url = request.url
    if "api.campx.in" in url:
        print(f"\n>>> REQUEST: {request.method} {url}")
        try:
            headers = request.all_headers()
            for k, v in headers.items():
                if k.lower() in ["authorization", "cookie", "token", "tenant"]:
                    print(f"    {k}: {v[:120]}...")
        except Exception as e:
            print(f"    Error reading headers: {e}")

def handle_response(response: Response):
    url = response.url
    if "api.campx.in" in url:
        print(f"<<< RESPONSE: {response.status} {url}")
        try:
            headers = response.all_headers()
            for k, v in headers.items():
                if "token" in k.lower() or "set-cookie" in k.lower() or "auth" in k.lower():
                    print(f"    {k}: {v[:120]}...")
        except Exception as e:
            print(f"    Error reading headers: {e}")

def trace():
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "chrome_profile"))
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.on("request", handle_request)
        page.on("response", handle_response)
        
        logger.info("Navigating to timetable page...")
        page.goto("https://mruh.campx.in/mruh/student-workspace/timetable", timeout=60000)
        page.wait_for_timeout(10000)
        
        context.close()

if __name__ == "__main__":
    trace()
