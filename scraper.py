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
logger = logging.getLogger("MUDUScraper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Check if running in a production container with a mounted persistent volume /data
DB_DIR = "/data" if os.path.exists("/data") else os.path.dirname(__file__)
DB_FILE = os.path.abspath(os.path.join(DB_DIR, "database.json"))

# Copy default database.json template to persistent volume if not present
if DB_DIR == "/data" and not os.path.exists(DB_FILE):
    default_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "database.json"))
    if os.path.exists(default_db):
        try:
            shutil.copy(default_db, DB_FILE)
            logger.info("Copied default database.json template to persistent volume /data.")
        except Exception as e:
            logger.error(f"Failed to copy default database.json to /data: {e}")

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
    users = db.get("users", {})
    if str(telegram_id) in users:
        return users[str(telegram_id)]
    if "default" in users:
        return users["default"]
    return {}

def save_user_data(telegram_id: str, user_info: Dict[str, Any]):
    db = load_db()
    if "users" not in db:
        db["users"] = {}
    db["users"][str(telegram_id)] = user_info
    save_db(db)

MUDU_BASE_URL = "https://mru.mudu.in/api"
MUDU_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://mru.mudu.in",
    "Referer": "https://mru.mudu.in/",
    "Accept": "application/json, text/plain, */*"
}

def login_mudu_api(email_or_roll: str, password: str) -> Dict[str, Any]:
    """
    Direct API login against MUDU portal (POST /api/auth/login).
    Retrieves JWT session cookies, current user information, and student section details.
    """
    clean_identifier = email_or_roll.strip()
    logger.info(f"[MUDU] Attempting API login for: {clean_identifier}")
    
    headers = {**MUDU_HEADERS, "Content-Type": "application/json"}
    payload = {"email": clean_identifier, "password": password}
    
    try:
        with httpx.Client(headers=headers, timeout=20.0) as client:
            res = client.post(f"{MUDU_BASE_URL}/auth/login", json=payload)
            
            if res.status_code == 401:
                try:
                    err_msg = res.json().get("message", "Invalid email/roll number or password.")
                except Exception:
                    err_msg = "Invalid email/roll number or password."
                logger.warning(f"[MUDU] Login failed: {err_msg}")
                raise ScrapingError(err_msg)
                
            if res.status_code != 200:
                logger.error(f"[MUDU] Login unexpected status: {res.status_code}")
                raise ScrapingError(f"Login failed (status {res.status_code}).")
                
            login_data = res.json()
            user_info_resp = login_data.get("data", {}).get("user", {})
            linked_student_id = user_info_resp.get("linkedStudentId")
            user_id = user_info_resp.get("id")
            full_name = user_info_resp.get("fullName", "")
            
            cookies_dict = dict(client.cookies)
            logger.info(f"[MUDU] Login successful for {clean_identifier}. linkedStudentId={linked_student_id}")
            
            # Fetch student details for sectionId, rollNo, batchId
            section_id = None
            roll_no = clean_identifier
            sem_no = 2
            
            if linked_student_id:
                try:
                    prof_res = client.get(f"{MUDU_BASE_URL}/admin/students/{linked_student_id}")
                    if prof_res.status_code == 200:
                        stud_data = prof_res.json().get("data", {})
                        section_id = stud_data.get("sectionId") or (stud_data.get("section", {}) or {}).get("id")
                        roll_no = stud_data.get("rollNo") or roll_no
                        full_name = stud_data.get("name") or full_name
                        sem_no = stud_data.get("currentSemester") or 2
                        logger.info(f"[MUDU] Retrieved student profile: {full_name} ({roll_no}), Section: {section_id}")
                except Exception as pe:
                    logger.warning(f"[MUDU] Could not fetch student profile details: {pe}")
                    
            return {
                "email": clean_identifier,
                "password": password,
                "userId": user_id,
                "fullName": full_name,
                "rollNo": roll_no,
                "linkedStudentId": linked_student_id,
                "sectionId": section_id,
                "semNo": sem_no,
                "cookies": cookies_dict,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
    except httpx.RequestError as e:
        logger.error(f"[MUDU] Network error during API login: {e}")
        raise ScrapingError(f"Network error connecting to MUDU portal: {e}")

def login_and_save_session(telegram_id: str, email: str, password: str) -> bool:
    """
    Authenticates against MUDU portal and persists session data to database.json.
    Tries direct REST API first. If that fails due to browser restrictions, falls back to Playwright.
    """
    telegram_id_str = str(telegram_id)
    logger.info(f"[{telegram_id_str}] Authenticating with MUDU...")
    
    try:
        user_info = login_mudu_api(email, password)
        save_user_data(telegram_id_str, user_info)
        logger.info(f"[{telegram_id_str}] ✅ Successfully saved MUDU session to database.")
        return True
    except ScrapingError as se:
        if "invalid" in str(se).lower() or "not found" in str(se).lower():
            raise se
        logger.warning(f"[{telegram_id_str}] Direct API login failed, attempting browser fallback: {se}")

    # Fallback to Playwright headless browser
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), f"chrome_profile_{telegram_id_str}"))
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir)
        except Exception:
            pass
    os.makedirs(profile_dir, exist_ok=True)
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            login_url = "https://mru.mudu.in/login"
            page.goto(login_url, timeout=40000, wait_until="networkidle")
            page.wait_for_selector("#email", timeout=20000)
            
            page.locator("#email").fill(email)
            page.locator("#password").fill(password)
            page.locator("button[type='submit']").click()
            
            # Wait for redirect away from /login
            page.wait_for_url(lambda u: "/login" not in u, timeout=25000)
            page.wait_for_timeout(3000)
            
            cookies_list = context.cookies()
            cookies_dict = {c["name"]: c["value"] for c in cookies_list if "mudu.in" in c.get("domain", "")}
            
            with httpx.Client(cookies=cookies_dict, headers=MUDU_HEADERS, timeout=15) as client:
                r_me = client.get(f"{MUDU_BASE_URL}/auth/me")
                user_obj = r_me.json().get("data", {}).get("user", {}) if r_me.status_code == 200 else {}
                linked_sid = user_obj.get("linkedStudentId")
                section_id = None
                roll_no = email
                full_name = user_obj.get("fullName", "")
                sem_no = 2
                
                if linked_sid:
                    r_prof = client.get(f"{MUDU_BASE_URL}/admin/students/{linked_sid}")
                    if r_prof.status_code == 200:
                        sdata = r_prof.json().get("data", {})
                        section_id = sdata.get("sectionId") or (sdata.get("section", {}) or {}).get("id")
                        roll_no = sdata.get("rollNo") or roll_no
                        full_name = sdata.get("name") or full_name
                        sem_no = sdata.get("currentSemester") or 2

            user_info = {
                "email": email,
                "password": password,
                "userId": user_obj.get("id"),
                "fullName": full_name,
                "rollNo": roll_no,
                "linkedStudentId": linked_sid,
                "sectionId": section_id,
                "semNo": sem_no,
                "cookies": cookies_dict,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            save_user_data(telegram_id_str, user_info)
            logger.info(f"[{telegram_id_str}] ✅ Headless browser login successful.")
            return True
        finally:
            context.close()
            try:
                shutil.rmtree(profile_dir)
            except Exception:
                pass

def validate_mudu_cookie(token_or_cookies: Any, identifier: str) -> dict:
    """
    Validate MUDU session cookies/token and fetch student profile details.
    """
    cookies = {}
    if isinstance(token_or_cookies, dict):
        cookies = dict(token_or_cookies)
    elif isinstance(token_or_cookies, str):
        if "=" in token_or_cookies and ";" in token_or_cookies:
            for part in token_or_cookies.split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    cookies[k] = v
        elif "=" in token_or_cookies and not token_or_cookies.startswith("eyJ"):
            k, v = token_or_cookies.split("=", 1)
            cookies[k.strip()] = v.strip()
        else:
            cookies["access_token"] = token_or_cookies
            cookies["refresh_token"] = token_or_cookies

    full_name = ""
    roll_no = identifier
    linked_sid = None
    section_id = None
    sem_no = 2

    try:
        with httpx.Client(cookies=cookies, headers=MUDU_HEADERS, timeout=15) as client:
            rme = client.get(f"{MUDU_BASE_URL}/auth/me")
            if rme.status_code == 200:
                u = rme.json().get("data", {}).get("user", {})
                linked_sid = u.get("linkedStudentId")
                full_name = u.get("fullName", "")
                if linked_sid:
                    rprof = client.get(f"{MUDU_BASE_URL}/admin/students/{linked_sid}")
                    if rprof.status_code == 200:
                        sdata = rprof.json().get("data", {})
                        section_id = sdata.get("sectionId") or (sdata.get("section", {}) or {}).get("id")
                        roll_no = sdata.get("rollNo") or roll_no
                        full_name = sdata.get("name") or full_name
                        sem_no = sdata.get("currentSemester") or 2
    except Exception as e:
        logger.warning(f"Error validating cookie: {e}")

    return {
        "email": identifier,
        "fullName": full_name,
        "rollNo": roll_no,
        "linkedStudentId": linked_sid,
        "sectionId": section_id,
        "semNo": sem_no,
        "cookies": cookies,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

_validate_mudu_cookie = validate_mudu_cookie

def refresh_mudu_session(user_info: Dict[str, Any], telegram_id: str = None) -> Dict[str, str]:
    """
    Refreshes session cookies using refresh_token or auto-login with saved credentials.
    """
    cookies = user_info.get("cookies", {})
    email = user_info.get("email")
    password = user_info.get("password")
    
    # 1. Try refresh endpoint
    if "refresh_token" in cookies:
        try:
            logger.info("[MUDU] Refreshing session with refresh_token...")
            with httpx.Client(cookies=cookies, headers=MUDU_HEADERS, timeout=15) as client:
                r = client.post(f"{MUDU_BASE_URL}/auth/refresh")
                if r.status_code == 200:
                    new_cookies = dict(client.cookies)
                    cookies.update(new_cookies)
                    user_info["cookies"] = cookies
                    user_info["updated_at"] = datetime.now(timezone.utc).isoformat()
                    if telegram_id:
                        save_user_data(str(telegram_id), user_info)
                    logger.info("[MUDU] Session refresh succeeded.")
                    return cookies
        except Exception as re:
            logger.warning(f"[MUDU] Token refresh attempt failed: {re}")
            
    # 2. Try re-login with email/password if available
    if email and password:
        logger.info("[MUDU] Re-authenticating using stored credentials...")
        new_info = login_mudu_api(email, password)
        user_info.update(new_info)
        if telegram_id:
            save_user_data(str(telegram_id), user_info)
        return user_info.get("cookies", {})
        
    raise AuthenticationRequiredError("Session expired and no credentials available to re-authenticate.")

def fetch_portal_data(telegram_id: str) -> Dict[str, Any]:
    """
    Fetches timetable and attendance data from MUDU portal using saved session.
    Automatically refreshes expired session if credentials are saved.
    """
    telegram_id_str = str(telegram_id)
    user_info = get_user_data(telegram_id_str)
    
    if not user_info:
        raise AuthenticationRequiredError("No session or credentials found for this user. Please log in first.")
        
    cookies = user_info.get("cookies", {})
    linked_student_id = user_info.get("linkedStudentId")
    section_id = user_info.get("sectionId")
    
    # Auto-resolve linkedStudentId and sectionId if not cached
    if not linked_student_id or not section_id:
        logger.info(f"[{telegram_id_str}] Resolving missing student/section metadata...")
        try:
            with httpx.Client(cookies=cookies, headers=MUDU_HEADERS, timeout=15) as client:
                if not linked_student_id:
                    rme = client.get(f"{MUDU_BASE_URL}/auth/me")
                    if rme.status_code == 401:
                        cookies = refresh_mudu_session(user_info, telegram_id_str)
                        rme = client.get(f"{MUDU_BASE_URL}/auth/me", cookies=cookies)
                    if rme.status_code == 200:
                        linked_student_id = rme.json().get("data", {}).get("user", {}).get("linkedStudentId")
                        user_info["linkedStudentId"] = linked_student_id
                        
                if linked_student_id and not section_id:
                    rprof = client.get(f"{MUDU_BASE_URL}/admin/students/{linked_student_id}", cookies=cookies)
                    if rprof.status_code == 200:
                        sdata = rprof.json().get("data", {})
                        section_id = sdata.get("sectionId") or (sdata.get("section", {}) or {}).get("id")
                        user_info["sectionId"] = section_id
                        user_info["fullName"] = sdata.get("name") or user_info.get("fullName", "")
                        user_info["rollNo"] = sdata.get("rollNo") or user_info.get("rollNo", "")
                        
                save_user_data(telegram_id_str, user_info)
        except Exception as e:
            logger.warning(f"[{telegram_id_str}] Metadata resolution issue: {e}")

    if not linked_student_id:
        raise ScrapingError("Could not retrieve linked student ID. Please log in again.")

    logger.info(f"[{telegram_id_str}] Fetching MUDU attendance and timetable...")
    
    # 1. Fetch Attendance Summary
    att_summary_url = f"{MUDU_BASE_URL}/admin/attendance/student/{linked_student_id}/summary"
    try:
        with httpx.Client(cookies=cookies, headers=MUDU_HEADERS, timeout=25.0) as client:
            r_att = client.get(att_summary_url)
            if r_att.status_code == 401:
                logger.info(f"[{telegram_id_str}] Attendance 401. Refreshing session...")
                cookies = refresh_mudu_session(user_info, telegram_id_str)
                r_att = client.get(att_summary_url, cookies=cookies)
                
            if r_att.status_code != 200:
                raise ScrapingError(f"MUDU portal attendance error (status {r_att.status_code})")
                
            att_data = r_att.json().get("data", {})
            
            # 2. Fetch Section Timetable
            timetable_raw = []
            if section_id:
                tt_url = f"{MUDU_BASE_URL}/admin/timetable/section/{section_id}"
                r_tt = client.get(tt_url, cookies=cookies)
                if r_tt.status_code == 200:
                    timetable_raw = r_tt.json().get("data", [])
                else:
                    logger.warning(f"[{telegram_id_str}] Could not fetch section timetable: {r_tt.status_code}")
                    
    except httpx.RequestError as re:
        raise ScrapingError(f"HTTP network error contacting MUDU portal: {re}")

    # Process Attendance Results
    courses = att_data.get("courses", [])
    attendance_results = []
    for c in courses:
        sub_name = c.get("courseName") or c.get("courseCode") or "Unknown Subject"
        cond = c.get("total", 0)
        att = c.get("present", 0)
        pct = float(c.get("percentage", 0.0))
        bunk_info = calculate_bunks_or_attendance_required(att, cond, target_percentage=75.0)
        attendance_results.append({
            "subject": sub_name,
            "code": c.get("courseCode", ""),
            "conducted": cond,
            "attended": att,
            "percentage": pct,
            "bunk_info": bunk_info
        })
        
    overall_pct = att_data.get("overallPercentage")
    if overall_pct is None and courses:
        total_c = sum(c.get("total", 0) for c in courses)
        total_p = sum(c.get("present", 0) for c in courses)
        overall_pct = (total_p / total_c * 100.0) if total_c > 0 else 0.0

    # Process Timetable for Today (in IST: UTC+5:30)
    ist_time = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    today_day = ist_time.strftime("%A").upper()  # MONDAY, TUESDAY, etc.
    
    today_classes = [item for item in timetable_raw if item.get("dayOfWeek", "").upper() == today_day]
    # Sort by timeSlot order or start time
    today_classes.sort(key=lambda x: (x.get("timeSlot", {}) or {}).get("order", 0))
    
    today_timetable = []
    for item in today_classes:
        ts = item.get("timeSlot", {}) or {}
        start = ts.get("startTime", "")[:5]
        end = ts.get("endTime", "")[:5]
        course_name = (item.get("course", {}) or {}).get("name", "Unknown Subject")
        faculty_name = (item.get("faculty", {}) or {}).get("name", "")
        room = item.get("room")
        
        info = f"🕒 {start} - {end} | {course_name}"
        if faculty_name:
            info += f" ({faculty_name})"
        if room:
            info += f" [Room: {room}]"
        today_timetable.append(info)

    return {
        "timetable": today_timetable,
        "attendance": attendance_results,
        "overall_percentage": overall_pct,
        "day_name": today_day,
        "student_name": user_info.get("fullName", ""),
        "roll_no": user_info.get("rollNo", ""),
    }

def fetch_assignments(cookies: dict) -> str:
    """
    Fetch active assignments from MUDU portal (/api/admin/assessment-management/student/my-assessments).
    """
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    now_str = ist_now.strftime("%d %b %Y, %I:%M %p IST")
    
    url = f"{MUDU_BASE_URL}/admin/assessment-management/student/my-assessments"
    try:
        with httpx.Client(cookies=cookies, headers=MUDU_HEADERS, timeout=20.0) as client:
            r = client.get(url)
            if r.status_code == 401:
                raise AuthenticationRequiredError("Session expired")
            if r.status_code != 200:
                return f"❌ Could not fetch assignments (status {r.status_code})"
            items = r.json().get("data", [])
    except httpx.RequestError as e:
        return f"❌ Network error fetching assignments: {e}"

    lines = [
        "📋 *MUDU ASSIGNMENTS DASHBOARD*",
        f"🕒 _{now_str}_",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    
    if not items:
        lines.append("_No assignments found._")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)
        
    pending = [a for a in items if not a.get("submission")]
    submitted = [a for a in items if a.get("submission")]
    
    lines.append(f"📊 Total: *{len(items)}* | ✅ Submitted: *{len(submitted)}* | ⏳ Pending: *{len(pending)}*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    if pending:
        lines.append("⏳ *PENDING ASSIGNMENTS*")
        for a in pending[:10]:
            title = a.get("title", "Untitled Assignment")
            course = a.get("courseName") or a.get("courseCode", "")
            faculty = a.get("facultyName", "")
            due = a.get("dueDate", "")
            max_m = a.get("maxMarks", "")
            
            if due:
                try:
                    due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
                    due_ist = due_dt + timedelta(hours=5, minutes=30)
                    due = due_ist.strftime("%d %b %Y, %I:%M %p")
                except Exception:
                    pass
            lines.append(f"\n🔴 *{title}*")
            if course:
                lines.append(f"   📖 Course: _{course}_")
            if faculty:
                lines.append(f"   👨‍🏫 Faculty: _{faculty}_")
            if due:
                lines.append(f"   📅 Due: `{due}`")
            if max_m:
                lines.append(f"   🎯 Max Marks: {max_m}")

    if submitted:
        lines.append(f"\n✅ *SUBMITTED ({len(submitted)})*")
        for a in submitted[:5]:
            title = a.get("title", "Untitled")
            course = a.get("courseName", "")
            lines.append(f"   • _{title}_ ({course})")
        if len(submitted) > 5:
            lines.append(f"   _...and {len(submitted)-5} more_")
            
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)

def fetch_subjects(cookies: dict, linked_student_id: str = None) -> str:
    """
    Fetch enrolled courses and subject details from MUDU portal.
    """
    if not linked_student_id:
        try:
            with httpx.Client(cookies=cookies, headers=MUDU_HEADERS, timeout=15.0) as client:
                rme = client.get(f"{MUDU_BASE_URL}/auth/me")
                if rme.status_code == 200:
                    linked_student_id = rme.json().get("data", {}).get("user", {}).get("linkedStudentId")
        except Exception:
            pass

    if not linked_student_id:
        return "❌ Could not determine student account. Please re-login."

    url = f"{MUDU_BASE_URL}/admin/attendance/student/{linked_student_id}/summary"
    try:
        with httpx.Client(cookies=cookies, headers=MUDU_HEADERS, timeout=20.0) as client:
            r = client.get(url)
            if r.status_code == 401:
                raise AuthenticationRequiredError("Session expired")
            if r.status_code != 200:
                return f"❌ Could not fetch subjects (status {r.status_code})"
            courses = r.json().get("data", {}).get("courses", [])
    except httpx.RequestError as e:
        return f"❌ Network error fetching subjects: {e}"

    if not courses:
        return "📚 *Your Subjects*\n\n_No enrolled courses found on MUDU portal._"

    lines = [
        "📚 *Your Enrolled Subjects (MUDU)*",
        f"_Total: {len(courses)} course(s)_",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    for i, c in enumerate(courses, 1):
        name = c.get("courseName", "Unknown")
        code = c.get("courseCode", "")
        credits = c.get("courseCredits", "")
        category = c.get("category", "")
        faculty = c.get("facultyName", "")
        section = c.get("sectionName", "")
        
        icon = "🔬" if "lab" in name.lower() or "explore" in name.lower() else "📖"
        lines.append(f"\n{icon} *{i}. {name}*")
        
        details = []
        if code:     details.append(f"`{code}`")
        if category: details.append(f"_{category}_")
        if credits:  details.append(f"*{credits} credits*")
        if details:
            lines.append("   " + " | ".join(details))
            
        if faculty:
            lines.append(f"   👨‍🏫 Faculty: {faculty}")
        if section:
            lines.append(f"   🏷️ Section: {section}")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)
def fetch_mru_results(email: str, headless: bool = True) -> Dict[str, Any]:
    """Scrape MRU exam results for the given email (roll number).
    Returns a dictionary mapping semester keys to result data.
    """
    # Derive roll number from input (accept either full email or plain roll number)
    if "@" in email:
        roll_no = email.split("@")[0].upper()  # part before @
    else:
        roll_no = email.upper()  # input is already a roll number
    password = roll_no  # Exams portal uses roll number (uppercase) as default password

    login_url = "https://mruexams.com/SBLogin.aspx"
    results_url = "https://mruexams.com/STUDENTLOGIN/Frm_SemwiseStudMarks.aspx"

    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), f"chrome_profile_results_{roll_no}"))
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir)
        except Exception as e:
            logger.warning(f"Could not clean profile directory {profile_dir}: {e}")
    os.makedirs(profile_dir, exist_ok=True)

    results_data: Dict[str, Any] = {}
    try:
        with sync_playwright() as p:
            # Use random user-agent to bypass basic bot detection
            import random
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ]
            ua = random.choice(user_agents)
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=headless,
                viewport={"width": 1280, "height": 900},
                args=["--no-sandbox", "--disable-setuid-sandbox", f"--user-agent={ua}"],
                ignore_default_args=["--enable-automation"]
            )
            page = context.pages[0] if context.pages else context.new_page()

            logger.info(f"[{roll_no}] Loading MRU Exams login page...")
            page.goto(login_url, timeout=40000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            logger.info(f"[{roll_no}] Submitting credentials to MRU Exams portal")
            # Fill username field (both name and id selectors) with uppercase roll number
            page.fill("input[name*='txtUserName']", roll_no)
            page.fill("input[id*='txtUserName']", roll_no)
            page.fill("input[type='password']", password)
            login_btn = page.query_selector("input[type='submit'], button[type='submit']")
            if login_btn:
                login_btn.click()
            else:
                page.keyboard.press("Enter")
            
            # Wait for navigation/load state with timeout
            try:
                page.wait_for_load_state('load', timeout=10000)
            except Exception:
                pass
            page.wait_for_timeout(4000)

            # Optional debug screenshot/html
            try:
                page.screenshot(path=f"login_debug_{roll_no}_after_login.png", timeout=5000)
                with open(f"login_debug_{roll_no}_after_login.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
            except Exception as se:
                logger.warning(f"Could not save post-login debug info: {se}")

            # After login, check if a password change is required (only if fields are visible)
            new_pass_input = page.query_selector("input[name='ctl00$txtNewPass']")
            if new_pass_input and new_pass_input.is_visible():
                logger.info(f"[{roll_no}] Detected password change prompt, updating password...")
                # Fill new password fields (use same password for simplicity)
                page.fill("input[name='ctl00$txtNewPass']", password)
                page.fill("input[name='ctl00$txtConPass']", password)
                # Click the change password button
                change_btn = page.query_selector("#btnstudentpassword")
                if change_btn:
                    change_btn.click()
                page.wait_for_timeout(3000)
                # After password change, some portals require confirming the update via an 'Update' button
                confirm_btn = page.query_selector("input[name='ctl00$imgYes'], #imgYes")
                if confirm_btn:
                    confirm_btn.click()
                    page.wait_for_timeout(3000)
                # Wait for any navigation after password change
                try:
                    page.wait_for_load_state('load', timeout=10000)
                except Exception:
                    pass

            # After login (and optional password change), navigate to the results page
            logger.info(f"[{roll_no}] Navigating to results page...")
            page.goto(results_url, timeout=40000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # Verify successful login by checking for a known element (logout button or roll number)
            try:
                page.wait_for_selector("#Stud_Logout, #lblHTNo", timeout=15000)
            except Exception:
                raise AuthenticationRequiredError("MRU Exams portal login failed. Please ensure your credentials are correct.")

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
                            subjects.append(dict(zip(headers, cells)))
                if subjects:
                    sgpa_elem = page.query_selector("#Stud_cpBody_lblSGPA")
                    cgpa_elem = page.query_selector("#Stud_cpBody_lblCGPA")
                    sgpa = sgpa_elem.inner_text().strip() if sgpa_elem else ""
                    cgpa = cgpa_elem.inner_text().strip() if cgpa_elem else ""
                    results_data[f"Semester {sem}"] = {
                        "tab_title": tab_title,
                        "subjects": subjects,
                        "sgpa": sgpa,
                        "cgpa": cgpa,
                    }
    finally:
        try:
            context.close()
        except Exception:
            pass
        try:
            shutil.rmtree(profile_dir)
        except Exception:
            pass
    return results_data

# ── MeritCurve Functions ────────────────────────────────────────────────────────

def _find_user_id_by_email(email: str) -> str:
    """Return the Telegram user ID for a given email, or raise if not found."""
    db = load_db()
    for uid, info in db.get("users", {}).items():
        if info.get("email") == email:
            return str(uid)
    raise AuthenticationRequiredError("User not found for given email.")

def _save_merit_cookie(uid: str, cookie: dict) -> None:
    db = load_db()
    if "users" not in db:
        db["users"] = {}
    db["users"].setdefault(uid, {})["merit_cookie"] = cookie
    save_db(db)

def _load_merit_cookie(uid: str) -> dict | None:
    db = load_db()
    return db.get("users", {}).get(uid, {}).get("merit_cookie")

def fetch_merit_data(email: str) -> Dict[str, Any]:
    """Log into MeritCurve and extract assignments, tests, quizzes.
    Uses a persisted cookie when available to avoid re‑login.
    """
    uid = _find_user_id_by_email(email)
    cookie = _load_merit_cookie(uid)
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), f"chrome_profile_merit_{uid}"))
    os.makedirs(profile_dir, exist_ok=True)
    data: Dict[str, Any] = {"assignments": [], "tests": [], "quizzes": []}
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=True,
                viewport={"width": 1280, "height": 800},
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            page = context.pages[0] if context.pages else context.new_page()
            if cookie:
                # Load saved cookie into context before navigation
                context.add_cookies([{"name": k, "value": v, "domain": "mru.meritcurve.com", "path": "/"} for k, v in cookie.items()])
                page.goto("https://mru.meritcurve.com/home/dashboard", wait_until="domcontentloaded", timeout=30000)
                # If still on login page, perform login
                if "login" in page.url.lower():
                    page.fill("input[type='email']", email)
                    page.fill("input[type='password']", "mru@123")
                    page.click("button[type='submit']")
                    page.wait_for_load_state("networkidle")
            else:
                # Fresh login
                page.goto("https://mru.meritcurve.com/home/dashboard", wait_until="domcontentloaded", timeout=30000)
                page.fill("input[type='email']", email)
                page.fill("input[type='password']", "mru@123")
                page.click("button[type='submit']")
                page.wait_for_load_state("networkidle")
            # After login, capture cookies for future use
            playwright_cookies = context.cookies()
            saved = {c["name"]: c["value"] for c in playwright_cookies if c.get("domain") == "mru.meritcurve.com"}
            _save_merit_cookie(uid, saved)
            # Wait for dashboard elements
            try:
                page.wait_for_selector(".dashboard, .assignments-count, .tests-count, .quizzes-count", timeout=30000)
            except Exception as e:
                logger.warning(f"[{uid}] Dashboard elements not found or timed out: {e}")
            # Extract counts – placeholder selectors (adjust as needed)
            assign_el = page.query_selector(".assignments-count")
            if assign_el:
                data["assignments"] = [{"title": el.inner_text().strip(), "due": el.get_attribute("data-due") or ""} for el in page.query_selector_all(".assignment-item")]
            test_el = page.query_selector(".tests-count")
            if test_el:
                data["tests"] = [{"title": el.inner_text().strip(), "due": el.get_attribute("data-due") or ""} for el in page.query_selector_all(".test-item")]
            quiz_el = page.query_selector(".quizzes-count")
            if quiz_el:
                data["quizzes"] = [{"title": el.inner_text().strip(), "due": el.get_attribute("data-due") or ""} for el in page.query_selector_all(".quiz-item")]

    finally:
        # Clean up context but keep profile for future sessions
        try:
            context.close()
        except Exception:
            pass
    return data

def format_merit_report(data: Dict[str, Any]) -> str:
    """Create a markdown report for MeritCurve dashboard data."""
    lines = ["🎓 *MeritCurve Dashboard*", "━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    total_assign = len(data.get("assignments", []))
    total_tests = len(data.get("tests", []))
    total_quiz = len(data.get("quizzes", []))
    lines.append(f"• Assignments: {total_assign}")
    lines.append(f"• Tests: {total_tests}")
    lines.append(f"• Quizzes: {total_quiz}\n")
    # Detailed listings
    def add_section(name: str, items: list):
        if items:
            lines.append(f"*{name}:*")
            for it in items:
                title = it.get("title", "Untitled")
                due = it.get("due")
                due_str = f" — due {due}" if due else ""
                lines.append(f"  • {title}{due_str}")
    add_section("Assignments", data.get("assignments", []))
    add_section("Tests", data.get("tests", []))
    add_section("Quizzes", data.get("quizzes", []))
    return "\n".join(lines)

# Backwards compatibility wrappers for legacy tests and scripts
def parse_attendance_row(row_text: str, cells: list = None) -> Tuple[str, int, int, float]:
    """Parse attendance row text and cells for subject, conducted, attended, percentage."""
    import re
    cells = cells or []
    sub = ""
    cond = 0
    att = 0
    pct = 0.0

    if cells:
        sub = re.sub(r"^(Subject:\s*)", "", cells[0], flags=re.IGNORECASE).strip()
    elif row_text:
        sub = row_text.split("|")[0].strip()

    nums = []
    for c in cells[1:]:
        m = re.search(r"(\d+(?:\.\d+)?)", c)
        if m:
            nums.append(float(m.group(1)))

    if not nums and row_text:
        found = re.findall(r"(\d+(?:\.\d+)?)", row_text)
        nums = [float(x) for x in found]

    if len(nums) >= 2:
        cond = int(nums[0])
        att = int(nums[1])
        if len(nums) >= 3:
            pct = float(nums[2])
        elif cond > 0:
            pct = round((att / cond) * 100, 2)

    return sub, cond, att, pct

def parse_attendance(page=None) -> list:
    """Legacy parse_attendance stub."""
    return []

def parse_timetable(page=None) -> list:
    """Legacy parse_timetable stub."""
    return []

def scrape_portal(headless: bool = True, telegram_id: str = "default") -> Dict[str, Any]:
    """Legacy scrape_portal stub pointing to fetch_portal_data."""
    return fetch_portal_data(telegram_id)




