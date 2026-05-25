import os
import json
import logging
from playwright.sync_api import sync_playwright, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CampXInterceptor")

def handle_response(response: Response):
    url = response.url
    # Print every request to see the path format
    print(f"Request: {response.request.method} {url} [{response.status}]")
    
    # Check for API-like responses
    if any(keyword in url.lower() for keyword in ["api", "json", "v1", "graphql", "query", "data", "fetch"]):
        try:
            # Print headers
            headers = response.request.headers
            cookie_headers = {k: v for k, v in headers.items() if k.lower() in ["authorization", "cookie", "token", "x-auth-token"]}
            
            # Print response body if JSON or text
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                json_data = response.json()
                print("\n" + "="*80)
                print(f"API RESPONSE JSON: {response.request.method} {url}")
                print(f"Status: {response.status}")
                if cookie_headers:
                    print(f"Auth Headers: {cookie_headers}")
                formatted = json.dumps(json_data, indent=2)
                print("JSON Snippet:")
                print(formatted[:1500] + "\n... (truncated)" if len(formatted) > 1500 else formatted)
                print("="*80 + "\n")
        except Exception as e:
            # Print reading exceptions so we know what went wrong
            print(f"Error reading response for {url}: {e}")


def intercept():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "r") as f:
        config = json.load(f)
        
    profile_dir = config.get("chrome_profile_dir", "chrome_profile")
    if not os.path.isabs(profile_dir):
        profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), profile_dir))
        
    timetable_url = config.get("timetable_url", "https://mruh.campx.in/mruh/student-workspace/timetable")
    attendance_url = config.get("attendance_url", "https://mruh.campx.in/mruh/student-workspace/attendance")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        # Register response interceptor
        page.on("response", handle_response)
        
        logger.info("Navigating to Timetable page...")
        try:
            page.goto(timetable_url, timeout=45000)
            page.wait_for_timeout(5000)
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            
        logger.info("Navigating to Attendance page...")
        try:
            page.goto(attendance_url, timeout=45000)
            page.wait_for_timeout(5000)
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            
        context.close()

if __name__ == "__main__":
    intercept()
