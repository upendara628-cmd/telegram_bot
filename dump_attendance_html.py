import os
from playwright.sync_api import sync_playwright

def dump():
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "chrome_profile"))
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        attendance_url = "https://mruh.campx.in/mruh/student-workspace/attendance"
        page.goto(attendance_url, timeout=60000)
        page.wait_for_timeout(8000)
        
        html = page.content()
        with open("attendance_page.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        context.close()

if __name__ == "__main__":
    dump()
