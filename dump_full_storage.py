import os
import json
from playwright.sync_api import sync_playwright

def dump():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "r") as f:
        config = json.load(f)
        
    profile_dir = config.get("chrome_profile_dir", "chrome_profile")
    if not os.path.isabs(profile_dir):
        profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), profile_dir))
        
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://mruh.campx.in/mruh/student-workspace/timetable")
        page.wait_for_timeout(5000)
        
        # Get campx_workspace_data
        data = page.evaluate("() => window.localStorage.getItem('campx_workspace_data')")
        print("\n=== campx_workspace_data ===")
        if data:
            parsed = json.loads(data)
            print(json.dumps(parsed, indent=2))
        else:
            print("Not found")
            
        context.close()

if __name__ == "__main__":
    dump()
