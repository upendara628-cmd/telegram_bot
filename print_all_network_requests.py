import os
from playwright.sync_api import sync_playwright, Request

def handle_request(request: Request):
    print(f"[{request.method}] {request.url}")

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
        
        attendance_url = "https://mruh.campx.in/mruh/student-workspace/attendance"
        page.goto(attendance_url, timeout=60000)
        page.wait_for_timeout(8000)
        
        # Click close if modal is there
        try:
            close_btn = page.locator("button[data-slot='dialog-close']").first
            if close_btn.count() > 0:
                close_btn.click()
        except:
            pass
            
        page.wait_for_timeout(5000)
        context.close()

if __name__ == "__main__":
    trace()
