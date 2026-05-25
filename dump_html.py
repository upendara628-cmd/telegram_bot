import os
import json
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CampXHTMLDumper")

def dump_pages():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "r") as f:
        config = json.load(f)
        
    profile_dir = config.get("chrome_profile_dir", "chrome_profile")
    if not os.path.isabs(profile_dir):
        profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), profile_dir))
        
    timetable_url = config.get("timetable_url", "https://mruh.campx.in/mruh/student-workspace/timetable")
    attendance_url = config.get("attendance_url", "https://mruh.campx.in/mruh/student-workspace/attendance")
    dashboard_url = "https://mruh.campx.in/mruh/student-workspace/dashboard"
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        # 1. Timetable Page Source
        logger.info(f"Navigating to Timetable: {timetable_url}")
        try:
            page.goto(timetable_url, timeout=45000)
            page.wait_for_timeout(5000)  # Wait for rendering
            timetable_html = page.content()
            with open("debug_timetable.html", "w", encoding="utf-8") as f:
                f.write(timetable_html)
            logger.info("Saved debug_timetable.html")
        except Exception as e:
            logger.error(f"Failed to dump timetable: {e}")
            
        # 2. Attendance Page Source
        logger.info(f"Navigating to Attendance: {attendance_url}")
        try:
            page.goto(attendance_url, timeout=45000)
            page.wait_for_timeout(5000)
            attendance_html = page.content()
            with open("debug_attendance.html", "w", encoding="utf-8") as f:
                f.write(attendance_html)
            logger.info("Saved debug_attendance.html")
        except Exception as e:
            logger.error(f"Failed to dump attendance: {e}")
            
        # 3. Dashboard Page Source
        logger.info(f"Navigating to Dashboard: {dashboard_url}")
        try:
            page.goto(dashboard_url, timeout=45000)
            page.wait_for_timeout(5000)
            dashboard_html = page.content()
            with open("debug_dashboard.html", "w", encoding="utf-8") as f:
                f.write(dashboard_html)
            logger.info("Saved debug_dashboard.html")
        except Exception as e:
            logger.error(f"Failed to dump dashboard: {e}")
            
        context.close()
    
    print("\nPage dumps completed! Please check 'debug_timetable.html', 'debug_attendance.html', and 'debug_dashboard.html'.")

if __name__ == "__main__":
    dump_pages()
