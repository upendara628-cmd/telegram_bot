import os
import json
import logging
import shutil
import math
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple
from playwright.sync_api import sync_playwright, Page, Response
import httpx
from attendance import calculate_bunks_or_attendance_required

# Configure logger
logger = logging.getLogger("CampXScraper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "database.json"))

class AuthenticationRequiredError(Exception):
    """Raised when the session is invalid and credentials/SSO login is required."""
    pass

class ScrapingError(Exception):
    """Raised when parsing or navigation fails."""
    pass

def load_db() -> Dict[str, Any]:
    if not os.path.exists(DB_FILE):
        return {"users": {}}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading database.json: {e}")
        return {"users": {}}

def save_db(db: Dict[str, Any]):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving database.json: {e}")

def get_user_data(telegram_id: str) -> Dict[str, Any]:
    db = load_db()
    return db.get("users", {}).get(str(telegram_id), {})

def save_user_data(telegram_id: str, user_info: Dict[str, Any]):
    db = load_db()
    if "users" not in db:
        db["users"] = {}
    db["users"][str(telegram_id)] = user_info
    save_db(db)

def login_and_save_session(telegram_id: str, email: str, password: str) -> bool:
    """
    Automates login via Playwright headlessly.
    Extracts session cookies, queries workspaces API to get current semNo, 
    and saves credentials & session data to database.json.
    """
    telegram_id_str = str(telegram_id)
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), f"chrome_profile_{telegram_id_str}"))
    
    # Force clean user-specific profile folder to avoid stale states
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir)
        except Exception as e:
            logger.warning(f"Could not clean profile directory {profile_dir}: {e}")
            
    os.makedirs(profile_dir, exist_ok=True)
    
    logger.info(f"[{telegram_id_str}] Launching browser for direct login...")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        try:
            timetable_url = "https://mruh.campx.in/mruh/student-workspace/timetable"
            page.goto(timetable_url, timeout=60000)
            
            # Wait for redirect to login screen
            logger.info(f"[{telegram_id_str}] Waiting for login page to load...")
            page.wait_for_selector("#loginId", timeout=30000)
            
            # Fill credentials
            logger.info(f"[{telegram_id_str}] Filling credentials...")
            page.locator("#loginId").fill(email)
            page.locator("#password").fill(password)
            page.locator("#password").press("Enter")
            
            # Wait for workspace redirect
            logger.info(f"[{telegram_id_str}] Waiting for student workspace redirect...")
            success = False
            for _ in range(25):
                page.wait_for_timeout(1000)
                if "student-workspace" in page.url.lower() and "auth" not in page.url.lower():
                    success = True
                    break
                    
            if not success:
                # Capture failed page info for debugging
                page.screenshot(path=f"login_failed_{telegram_id_str}.png")
                raise ScrapingError("Login failed: The portal rejected the credentials or required Google SSO.")
                
            # Wait 5 seconds to let initial workspace details load
            page.wait_for_timeout(5000)
            
            # Retrieve cookies
            playwright_cookies = context.cookies()
            cookies_dict = {}
            for cookie in playwright_cookies:
                if cookie.get("domain") in [".campx.in", "mruh.campx.in", "api.campx.in"]:
                    cookies_dict[cookie.get("name")] = cookie.get("value")
                    
            if "campx_session_key" not in cookies_dict:
                raise ScrapingError("Could not retrieve campx_session_key from session cookies.")
                
            # Perform HTTP request to fetch user info and semester
            logger.info(f"[{telegram_id_str}] Extracting student semester information...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/148.0.7778.96 Safari/537.36",
                "Referer": "https://mruh.campx.in/",
                "Origin": "https://mruh.campx.in"
            }
            
            with httpx.Client(cookies=cookies_dict, headers=headers) as client:
                r = client.get("https://api.campx.in/auth-server/auth-v2/workspaces")
                if r.status_code == 200:
                    resp_data = r.json()
                    user_data = resp_data.get("user", {})
                    sem_no = user_data.get("semNo", 2)  # Fallback to Sem 2 if not found
                else:
                    logger.warning(f"Could not retrieve workspaces data: {r.status_code}. Defaulting semNo to 2.")
                    sem_no = 2
                    
            # Save all data to database.json
            user_info = {
                "email": email,
                "password": password,
                "semNo": sem_no,
                "cookies": cookies_dict,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            save_user_data(telegram_id_str, user_info)
            logger.info(f"[{telegram_id_str}] ✅ Successfully saved session data (Semester {sem_no}).")
            
        finally:
            context.close()
            # Clean profile directory to save disk space
            try:
                shutil.rmtree(profile_dir)
            except:
                pass
                
    return True

def fetch_portal_data(telegram_id: str) -> Dict[str, Any]:
    """
    Fetches raw timetable and attendance data using cached cookies.
    If session expired (401), automatically attempts credentials login to renew.
    """
    telegram_id_str = str(telegram_id)
    user_info = get_user_data(telegram_id_str)
    
    if not user_info:
        raise AuthenticationRequiredError("No session or credentials found for this user.")
        
    cookies = user_info.get("cookies", {})
    email = user_info.get("email")
    password = user_info.get("password")
    user_sem = user_info.get("semNo", 2)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/148.0.7778.96 Safari/537.36",
        "Referer": "https://mruh.campx.in/",
        "Origin": "https://mruh.campx.in",
        "accept": "application/json, text/plain, */*",
        "x-institution-code": "mruh",
        "x-platform-id": "campx",
        "x-tenant-id": "mruh"
    }
    
    logger.info(f"[{telegram_id_str}] Making direct API request for timetables...")
    
    try:
        with httpx.Client(cookies=cookies, headers=headers, timeout=30.0) as client:
            r = client.get("https://api.campx.in/student-api/classroom-timetables")
            
            # Handle unauthorized session (session expired)
            if r.status_code == 401:
                if email and password:
                    logger.info(f"[{telegram_id_str}] Session expired (401). Retrying with credentials login...")
                    # Perform background login
                    login_and_save_session(telegram_id_str, email, password)
                    # Reload user info and cookies
                    user_info = get_user_data(telegram_id_str)
                    cookies = user_info.get("cookies", {})
                    # Re-request
                    r = client.get("https://api.campx.in/student-api/classroom-timetables", cookies=cookies)
                else:
                    raise AuthenticationRequiredError("Session expired and no credentials available to re-authenticate.")
                    
            if r.status_code != 200:
                raise ScrapingError(f"CampX portal returned error status: {r.status_code}")
                
            timetable_data = r.json()
            
    except httpx.RequestError as e:
        raise ScrapingError(f"HTTP network request failed: {e}")
        
    # Process raw API data
    # 1. Extract Today's Timetable
    # Compute today's date in Indian Standard Time (IST = UTC+5:30)
    ist_time = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    today_str = ist_time.strftime("%Y-%m-%d")

    today_timetable = []
    all_dates = set()

    for entry in timetable_data:
        session_date = entry.get("sessionDate", "")
        if session_date:
            all_dates.add(session_date)
        if session_date == today_str:
            from_time = entry.get("fromTime", "")[:5]
            to_time   = entry.get("toTime",   "")[:5]
            sub_name  = entry.get("subject", {}).get("name", "Unknown Subject")
            faculties = entry.get("faculties", [])
            fac_name  = faculties[0].get("fullName", "") if faculties else ""
            if fac_name:
                today_timetable.append(f"🕒 {from_time} - {to_time} | {sub_name} ({fac_name})")
            else:
                today_timetable.append(f"🕒 {from_time} - {to_time} | {sub_name}")

    # Find most recent past class date (for holiday/break message)
    past_dates = sorted(d for d in all_dates if d < today_str)
    last_class_date = ""
    if past_dates:
        raw = past_dates[-1]
        try:
            last_class_date = datetime.strptime(raw, "%Y-%m-%d").strftime("%d %b %Y")
        except:
            last_class_date = raw

    # 2. Extract Subject-Wise Attendance (for current semester)
    subject_stats = {}
    for entry in timetable_data:
        if entry.get("semNo") != user_sem:
            continue
        subject  = entry.get("subject", {})
        sub_name = subject.get("name")
        if not sub_name:
            continue
        is_completed = entry.get("completed", False)
        student_att  = entry.get("studentAttendance")
        if sub_name not in subject_stats:
            subject_stats[sub_name] = {"conducted": 0, "attended": 0}
        if is_completed and student_att:
            subject_stats[sub_name]["conducted"] += 1
            if student_att.get("status", False):
                subject_stats[sub_name]["attended"] += 1

    # Format attendance results
    attendance_results = []
    for sub, stats in subject_stats.items():
        cond = stats["conducted"]
        att  = stats["attended"]
        pct  = (att / cond * 100.0) if cond > 0 else 0.0
        bunk_info = calculate_bunks_or_attendance_required(att, cond, target_percentage=75.0)
        attendance_results.append({
            "subject":   sub,
            "conducted": cond,
            "attended":  att,
            "percentage": pct,
            "bunk_info":  bunk_info
        })

    return {
        "timetable":       today_timetable,
        "attendance":      attendance_results,
        "last_class_date": last_class_date,
    }

def scrape_portal(headless: bool = True) -> Dict[str, Any]:
    """
    Fallback function matching the old scraper structure.
    Tries to use a default or first user in the database.
    """
    db = load_db()
    users = db.get("users", {})
    if not users:
        raise AuthenticationRequiredError("No session profile found. Please configure credentials.")
    first_user = list(users.keys())[0]
    return fetch_portal_data(first_user)

def fetch_mru_results(email: str) -> Dict[str, Any]:
    """
    Scrapes semester-wise results from mruexams.com using Playwright.
    Derives the Roll Number from the email prefix (e.g. 2511cs020116@... -> 2511CS020116).
    Uses the Roll Number as both username and password.
    """
    if not email or "@" not in email:
        raise ValueError("Invalid email address for deriving Roll Number.")
        
    roll_no = email.split("@")[0].upper()
    password = roll_no
    
    login_url = "https://mruexams.com/SBLogin.aspx"
    results_url = "https://mruexams.com/STUDENTLOGIN/Frm_SemwiseStudMarks.aspx"
    
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), f"chrome_profile_results_{roll_no}"))
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir)
        except Exception as e:
            logger.warning(f"Could not clean profile directory {profile_dir}: {e}")
            
    os.makedirs(profile_dir, exist_ok=True)
    
    results_data = {}
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            viewport={"width": 1280, "height": 900},
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        try:
            logger.info(f"[{roll_no}] Loading login page...")
            page.goto(login_url, timeout=40000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            
            # Login
            logger.info(f"[{roll_no}] Logging in to mruexams.com...")
            page.fill("input[name*='txtUserName'], input[id*='txtUserName']", roll_no)
            page.fill("input[type='password']", password)
            
            login_btn = page.query_selector("input[type='submit'], button[type='submit']")
            if login_btn:
                login_btn.click()
            else:
                page.keyboard.press("Enter")
                
            page.wait_for_timeout(4000)
            
            if "login" in page.url.lower():
                raise AuthenticationRequiredError("MRU Exams portal login failed. Please ensure your credentials are correct.")
            
            # Navigate to results page
            logger.info(f"[{roll_no}] Navigating to results page...")
            page.goto(results_url, timeout=40000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            
            # Click tabs and parse results
            for sem in range(1, 9):
                tab_id = f"__tab_Stud_cpBody_tabResult_PanelSem{sem}"
                tab_selector = f"span#{tab_id}"
                
                tab_element = page.query_selector(tab_selector)
                if not tab_element:
                    continue
                    
                tab_title = tab_element.inner_text().strip()
                logger.info(f"[{roll_no}] Clicking semester tab: {tab_title}")
                tab_element.click()
                page.wait_for_timeout(2000)
                
                grid_id = f"Stud_cpBody_tabResult_PanelSem{sem}_gridSem{sem}"
                grid_tbl = page.query_selector(f"table#{grid_id}")
                
                if not grid_tbl:
                    continue
                    
                rows = grid_tbl.query_selector_all("tr")
                subjects = []
                headers = []
                
                for r_idx, row in enumerate(rows):
                    cells = [c.inner_text().strip() for c in row.query_selector_all("td, th")]
                    if r_idx == 0:
                        headers = cells
                    else:
                        if len(cells) >= len(headers) and any(cells):
                            subj = dict(zip(headers, cells))
                            subjects.append(subj)
                            
                if subjects:
                    # Query SGPA / CGPA labels
                    sgpa_elem = page.query_selector("#Stud_cpBody_lblSGPA")
                    cgpa_elem = page.query_selector("#Stud_cpBody_lblCGPA")
                    sgpa = sgpa_elem.inner_text().strip() if sgpa_elem else ""
                    cgpa = cgpa_elem.inner_text().strip() if cgpa_elem else ""
                    
                    results_data[f"Semester {sem}"] = {
                        "tab_title": tab_title,
                        "subjects": subjects,
                        "sgpa": sgpa,
                        "cgpa": cgpa
                    }
                    
        finally:
            context.close()
            try:
                shutil.rmtree(profile_dir)
            except:
                pass
                
    return results_data

