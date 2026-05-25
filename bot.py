import os
import sys
import json
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters, ConversationHandler
)

import httpx

from scraper import (
    fetch_portal_data, login_and_save_session,
    AuthenticationRequiredError, get_user_data, save_user_data,
    fetch_mru_results, fetch_merit_data, format_merit_report
)

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("CampXBot")

# ── Conversation states ────────────────────────────────────────────────────────
EMAIL, PASSWORD = range(2)
COOKIE_KEY, COOKIE_EMAIL = range(10, 12)

# ── Token helper ───────────────────────────────────────────────────────────────
def get_token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token:
        return token
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                return json.load(f).get("telegram_bot_token", "")
        except Exception as e:
            logger.error(f"Error loading config.json: {e}")
    return ""

# ═══════════════════════════════════════════════════════════════════════════════
#  🔒 LOGIN GUARD — Used by ALL feature handlers
# ═══════════════════════════════════════════════════════════════════════════════
async def require_login(update: Update) -> bool:
    """
    Returns True if the user is logged in.
    If not, sends a friendly prompt and returns False.
    All feature handlers call this first.
    """
    uid = str(update.effective_user.id)
    ud = get_user_data(uid)
    if ud:
        return True

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍪 Login via Cookie (Recommended)", callback_data="login_cookie")],
        [InlineKeyboardButton("📧 Login via Email & Password", callback_data="login_creds")],
    ])
    await update.message.reply_text(
        "🔒 *You need to log in first!*\n\n"
        "I don't have your session saved yet.\n"
        "Please choose a login method to continue:\n\n"
        "• `/set_cookies` — Paste your session cookie from the browser *(fastest, always works)*\n"
        "• `/setup_credentials` — Enter your email & password\n\n"
        "_Run one of those commands and then try again._",
        parse_mode=ParseMode.MARKDOWN
    )
    return False

# ── Auto-detect semNo from the workspaces API ─────────────────────────────────
def detect_sem_no(cookies: dict) -> int:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://mruh.campx.in/",
            "Origin": "https://mruh.campx.in",
        }
        with httpx.Client(cookies=cookies, headers=headers, timeout=15) as client:
            r = client.get("https://api.campx.in/auth-server/auth-v2/workspaces")
            if r.status_code == 200:
                sem = r.json().get("user", {}).get("semNo")
                if sem:
                    return int(sem)
    except Exception as e:
        logger.warning(f"Could not detect semNo: {e}")
    return 2

# ═══════════════════════════════════════════════════════════════════════════════
#  /start
# ═══════════════════════════════════════════════════════════════════════════════
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    ud = get_user_data(str(user.id))

    if ud:
        email = ud.get("email", "unknown")
        sem   = ud.get("semNo", "?")
        status_line = (
            f"✅ *Logged in as:* `{email}`\n"
            f"📚 *Semester:* `{sem}`"
        )
        feature_lines = (
            f"⚙️ *What you can do:*\n"
            f"• `/timetable` — Today's schedule & attendance\n"
            f"• `/assignments` — Pending & submitted assignments\n"
            f"• `/subjects` — Your enrolled subjects\n"
            f"• `/results` — Semester results from MRU Exams portal\n"
            f"• `/whoami` — Your linked account details\n"
            f"• `/logout` — Remove your session\n"
        )
    else:
        status_line = "⚠️ *Not logged in yet*"
        feature_lines = (
            f"⚙️ *Get started by logging in:*\n"
            f"• `/set_cookies` — Paste session cookie *(recommended for cloud)*\n"
            f"• `/setup_credentials` — Login with email & password\n\n"
            f"_After login you can use: `/timetable`, `/assignments`, `/subjects`, `/results`_"
        )

    await update.message.reply_text(
        f"👋 *Hello {user.first_name}!*\n\n"
        f"I'm your *MRUH CampX Companion Bot*.\n"
        f"Any MRUH student can use me with their own account.\n\n"
        f"{status_line}\n\n"
        f"{feature_lines}",
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════════════════════════════
#  /whoami
# ═══════════════════════════════════════════════════════════════════════════════
async def whoami_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_login(update):
        return
    uid = str(update.effective_user.id)
    ud  = get_user_data(uid)
    email   = ud.get("email", "unknown")
    sem     = ud.get("semNo", "?")
    updated = ud.get("updated_at", "unknown")
    await update.message.reply_text(
        f"👤 *Your linked account:*\n\n"
        f"📧 Email: `{email}`\n"
        f"📚 Semester: `{sem}`\n"
        f"🕒 Last updated: `{updated}`\n\n"
        f"_Use `/logout` to remove this session._",
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════════════════════════════
#  /logout
# ═══════════════════════════════════════════════════════════════════════════════
async def logout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_login(update):
        return
    from scraper import load_db, save_db
    uid = str(update.effective_user.id)
    db = load_db()
    if uid in db.get("users", {}):
        email = db["users"][uid].get("email", "unknown")
        del db["users"][uid]
        save_db(db)
        await update.message.reply_text(
            f"✅ *Session removed.*\n\n"
            f"Account `{email}` has been unlinked from your Telegram.\n"
            f"Use `/set_cookies` or `/setup_credentials` to log in again.",
            parse_mode=ParseMode.MARKDOWN
        )

# ═══════════════════════════════════════════════════════════════════════════════
#  /setup_credentials  (Email + Password → Playwright login)
# ═══════════════════════════════════════════════════════════════════════════════
async def start_credentials_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "📝 *Login with Email & Password*\n\n"
        "Send your MRUH portal email:\n"
        "_(e.g., `2511cs020116@mallareddyuniversity.ac.in`)_\n\n"
        "Type `/cancel` to abort.",
        parse_mode=ParseMode.MARKDOWN
    )
    return EMAIL

async def email_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip()
    if "@" not in email:
        await update.message.reply_text(
            "❌ That doesn't look like a valid email.\n"
            "Please send your full email address."
        )
        return EMAIL
    context.user_data["temp_email"] = email
    await update.message.reply_text(
        f"✅ Email: `{email}`\n\n"
        "🔑 Now send your portal *password:*\n"
        "_(it's deleted immediately after login)_",
        parse_mode=ParseMode.MARKDOWN
    )
    return PASSWORD

async def password_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password    = update.message.text
    email       = context.user_data.get("temp_email")
    telegram_id = str(update.effective_user.id)
    try:
        await update.message.delete()
    except Exception:
        pass

    status_msg = await update.message.reply_text(
        "⏳ *Logging in to CampX...*\n"
        "Using a headless browser — please wait up to 30 seconds...",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        loop = asyncio.get_running_loop()
        success = await loop.run_in_executor(
            None, login_and_save_session, telegram_id, email, password
        )
        if success:
            ud  = get_user_data(telegram_id)
            sem = ud.get("semNo", "?")
            await status_msg.edit_text(
                f"✅ *Login Successful!*\n\n"
                f"📧 Account: `{email}`\n"
                f"📚 Semester detected: `{sem}`\n\n"
                f"You can now use `/timetable`, `/assignments`, `/subjects`!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await status_msg.edit_text(
                "❌ *Login Failed!*\n"
                "Wrong email or password.\n\n"
                "💡 Try `/set_cookies` instead — it always works!",
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logger.error(f"Credentials login failed for {email}: {e}")
        await status_msg.edit_text(
            f"❌ *Login Failed!*\n\n"
            f"`{str(e)[:250]}`\n\n"
            f"💡 Try `/set_cookies` instead.",
            parse_mode=ParseMode.MARKDOWN
        )
    context.user_data.pop("temp_email", None)
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════════
#  /set_cookies  (Paste session cookie — no browser needed)
# ═══════════════════════════════════════════════════════════════════════════════
async def start_set_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🍪 *Manual Cookie Login*\n"
        "_Works on any cloud server — no browser needed!_\n\n"
        "📋 *How to get your cookie:*\n"
        "1️⃣ Open Chrome on your PC → go to `mruh.campx.in`\n"
        "2️⃣ Log in with your email & password\n"
        "3️⃣ Press `F12` → go to *Application* tab\n"
        "4️⃣ Click *Cookies* on the left → click `mruh.campx.in`\n"
        "5️⃣ Find the row named `campx_session_key`\n"
        "6️⃣ Copy the long value in the *Value* column\n\n"
        "📩 *Paste the value here now:*\n"
        "_(Type `/cancel` to abort)_",
        parse_mode=ParseMode.MARKDOWN
    )
    return COOKIE_KEY

async def cookie_key_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    session_key = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass

    if len(session_key) < 20:
        await update.message.reply_text(
            "❌ That value is too short to be a valid cookie.\n"
            "Please try `/set_cookies` again and copy the full value.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    context.user_data["temp_session_key"] = session_key
    await update.message.reply_text(
        "✅ Cookie received!\n\n"
        "📧 Now send your *college email* so I can label your account:\n"
        "_(e.g., `2511cs020116@mallareddyuniversity.ac.in`)_\n\n"
        "_(Type `/cancel` to abort)_",
        parse_mode=ParseMode.MARKDOWN
    )
    return COOKIE_EMAIL

async def cookie_email_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email       = update.message.text.strip()
    session_key = context.user_data.pop("temp_session_key", "")
    telegram_id = str(update.effective_user.id)

    status_msg = await update.message.reply_text(
        "⏳ Verifying cookie & detecting your semester...",
        parse_mode=ParseMode.MARKDOWN
    )

    cookies = {
        "campx_session_key": session_key,
        "campx_tenant":      "mruh",
        "campx_institution": "mruh",
    }

    loop   = asyncio.get_running_loop()
    sem_no = await loop.run_in_executor(None, detect_sem_no, cookies)

    user_info = {
        "email":      email if "@" in email else "unknown",
        "semNo":      sem_no,
        "cookies":    cookies,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_user_data(telegram_id, user_info)

    await status_msg.edit_text(
        f"✅ *Session saved!*\n\n"
        f"📧 Account: `{email}`\n"
        f"📚 Semester detected: `{sem_no}`\n\n"
        f"You can now use:\n"
        f"• `/timetable` — Schedule & attendance\n"
        f"• `/assignments` — Your assignments\n"
        f"• `/subjects` — Your subjects\n\n"
        f"⚠️ _Cookies expire in ~7 days. Run `/set_cookies` again if it stops working._",
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════════
#  /cancel
# ═══════════════════════════════════════════════════════════════════════════════
async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════════
#  /timetable  🔒 Login required
# ═══════════════════════════════════════════════════════════════════════════════
async def timetable_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_login(update):
        return

    telegram_id = str(update.effective_user.id)
    status_msg  = await update.message.reply_text(
        "⏳ *Fetching your schedule & attendance...*\n"
        "Making direct API request to CampX...",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        loop    = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, fetch_portal_data, telegram_id)
        await status_msg.edit_text(format_timetable_report(results), parse_mode=ParseMode.MARKDOWN)

    except AuthenticationRequiredError:
        await status_msg.edit_text(
            "❌ *Session Expired!*\n\n"
            "Your cookie has expired. Please log in again:\n"
            "• `/set_cookies` — paste a fresh cookie *(fastest)*\n"
            "• `/setup_credentials` — email & password",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Timetable fetch failed: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ *Failed to fetch data.*\n\n`{str(e)[:300]}`\n\n"
            f"Try `/set_cookies` to refresh your session.",
            parse_mode=ParseMode.MARKDOWN
        )

# ═══════════════════════════════════════════════════════════════════════════════
#  /assignments  🔒 Login required  (placeholder until API found)
# ═══════════════════════════════════════════════════════════════════════════════
async def assignments_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_login(update):
        return

    telegram_id = str(update.effective_user.id)
    ud          = get_user_data(telegram_id)
    cookies     = ud.get("cookies", {})

    status_msg = await update.message.reply_text(
        "⏳ *Fetching your assignments...*",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        loop   = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, fetch_assignments, cookies)
        await status_msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)
    except AuthenticationRequiredError:
        await status_msg.edit_text(
            "❌ *Session Expired!*\n\nPlease run `/set_cookies` to log in again.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Assignments fetch failed: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ *Failed to fetch assignments.*\n\n`{str(e)[:300]}`",
            parse_mode=ParseMode.MARKDOWN
        )

# ═══════════════════════════════════════════════════════════════════════════════
#  /subjects  🔒 Login required  (placeholder until API found)
# ═══════════════════════════════════════════════════════════════════════════════
async def subjects_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_login(update):
        return

    telegram_id = str(update.effective_user.id)
    ud          = get_user_data(telegram_id)
    cookies     = ud.get("cookies", {})
    sem_no      = ud.get("semNo", 2)

    status_msg = await update.message.reply_text(
        "⏳ *Fetching your subjects...*",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        loop   = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, fetch_subjects, cookies, sem_no)
        await status_msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)
    except AuthenticationRequiredError:
        await status_msg.edit_text(
            "❌ *Session Expired!*\n\nPlease run `/set_cookies` to log in again.",
            parse_mode=ParseMode.MARKDOWN
        )
# ═══════════════════════════════════════════════════════════════════════════════
#  /results  🔒 Login required
# ═══════════════════════════════════════════════════════════════════════════════
async def results_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_login(update):
        return

    telegram_id = str(update.effective_user.id)
    ud = get_user_data(telegram_id)
    email = ud.get("email", "")

    status_msg = await update.message.reply_text(
        "⏳ *Fetching your semester results from MRU Exams portal...*\n"
        "This uses Playwright headless browser — please wait up to 30 seconds...",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, fetch_mru_results, email)
        await status_msg.edit_text(format_results_report(results), parse_mode=ParseMode.MARKDOWN)
    except AuthenticationRequiredError:
        await status_msg.edit_text(
            "❌ *Login Failed on Exam Portal!*\n\n"
            "Your email does not seem to have a matching active account or the default roll number password has been changed on the MRU Exams portal.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Results fetch failed: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ *Failed to fetch results.*\n\n`{str(e)[:300]}`",
            parse_mode=ParseMode.MARKDOWN
        )

# ── MeritCurve command handler ────────────────────────────────────────────────────────
async def merit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /merit command: fetch MeritCurve dashboard and report."""
    if not await require_login(update):
        return
    telegram_id = str(update.effective_user.id)
    ud = get_user_data(telegram_id)
    email = ud.get("email", "")
    status_msg = await update.message.reply_text(
        "⏳ *Fetching your MeritCurve dashboard...*\n"
        "This uses Playwright headless browser — please wait up to 30 seconds...",
        parse_mode=ParseMode.MARKDOWN,
    )
    try:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, fetch_merit_data, email)
        await status_msg.edit_text(format_merit_report(data), parse_mode=ParseMode.MARKDOWN)
    except AuthenticationRequiredError:
        await status_msg.edit_text(
            "❌ *Login Failed on MeritCurve!*\n\n"
            "Your session may have expired. Please run `/set_cookies` or `/setup_credentials` again.",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error(f"Merit fetch failed: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ *Failed to fetch MeritCurve data.*\n\n`{str(e)[:300]}`",
            parse_mode=ParseMode.MARKDOWN,
        )

def format_results_report(results: dict) -> str:
    """Format mruexams.com results into a readable markdown message."""
    if not results:
        return "📭 *No results found or released yet on MRU Exams portal.*"
        
    lines = [
        "🎓 *MRU EXAMS SEMESTER RESULTS*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    # Sort semesters
    for sem_key in sorted(results.keys()):
        sem_data = results[sem_key]
        tab_title = sem_data.get("tab_title", sem_key)
        subjects = sem_data.get("subjects", [])
        sgpa = sem_data.get("sgpa", "")
        cgpa = sem_data.get("cgpa", "")
        
        lines.append(f"\n📂 *{tab_title}*")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        for i, sub in enumerate(subjects, 1):
            sub_name = sub.get("Subject Name", sub.get("subjectName", "Unknown"))
            code = sub.get("SubCode", sub.get("subjectCode", ""))
            grade = sub.get("Final Grade", sub.get("grade", ""))
            status = sub.get("Status", sub.get("status", ""))
            credits = sub.get("Credits", sub.get("credits", ""))
            
            status_emoji = "✅" if "pass" in status.lower() else "❌"
            lines.append(f"*{i}. {sub_name}*")
            lines.append(f"   Code: `{code}` | Grade: *{grade}* | Status: {status_emoji} *{status}* | Credits: {credits}")
            
        lines.append("──────────────────────────")
        if sgpa or cgpa:
            lines.append(f"📊 SGPA: *{sgpa}* | CGPA: *{cgpa}*")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════════════════════
#  API fetchers  (filled in once we discover the endpoints)
# ═══════════════════════════════════════════════════════════════════════════════
CAMPX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://mruh.campx.in/",
    "Origin":     "https://mruh.campx.in",
    "accept":     "application/json, text/plain, */*",
    "x-institution-code": "mruh",
    "x-platform-id":      "campx",
    "x-tenant-id":        "mruh",
    "x-campx-client":     "student-web",
}

def fetch_assignments(cookies: dict) -> str:
    """Fetch assignments from CampX API — endpoint discovered via network scan."""
    url = "https://api.campx.in/student-api/student-assignments/active-assignments?assignmentType=Integrated"
    with httpx.Client(cookies=cookies, headers=CAMPX_HEADERS, timeout=20.0) as client:
        r = client.get(url)
        if r.status_code == 401:
            raise AuthenticationRequiredError("Session expired")
        if r.status_code != 200:
            return f"❌ Could not fetch assignments (status {r.status_code})"
        data = r.json()
        assignments = data.get("assignments", [])
        return format_assignments(assignments)

def fetch_subjects(cookies: dict, sem_no: int) -> str:
    """Fetch subjects from CampX LMS API — endpoint discovered via network scan."""
    url = f"https://api.campx.in/student-api/subjects?semNo={sem_no}"
    with httpx.Client(cookies=cookies, headers=CAMPX_HEADERS, timeout=20.0) as client:
        r = client.get(url)
        if r.status_code == 401:
            raise AuthenticationRequiredError("Session expired")
        if r.status_code != 200:
            return f"❌ Could not fetch subjects (status {r.status_code})"

        subjects = r.json()  # List of subject objects
        if not subjects:
            return (
                f"📚 *Subjects — Semester {sem_no}*\n\n"
                "_No subjects found for this semester._"
            )

        lines = [
            f"📚 *Your Subjects — Semester {sem_no}*",
            f"_Total: {len(subjects)} subject(s)_",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]
        for i, sub in enumerate(subjects, 1):
            name    = sub.get("name", "Unknown")
            code    = sub.get("subjectCode", "")
            credits = sub.get("credits", "")

            # subjectType is a nested object: {"type": "Theory", ...}
            stype_obj = sub.get("subjectType") or {}
            stype = stype_obj.get("type", "Theory") if isinstance(stype_obj, dict) else str(stype_obj)

            # Faculty name (first faculty in list)
            faculties = sub.get("faculties", [])
            faculty   = faculties[0].get("fullName", "") if faculties else ""

            # Syllabus link
            syllabus_url = sub.get("syllabusUrl", "")

            icon = "🔬" if "lab" in stype.lower() else "📖"
            lines.append(f"\n{icon} *{i}. {name}*")

            detail_parts = []
            if code:    detail_parts.append(f"`{code}`")
            if stype:   detail_parts.append(f"_{stype}_")
            if credits: detail_parts.append(f"*{credits} credits*")
            if detail_parts:
                lines.append("   " + " | ".join(detail_parts))

            if faculty:
                lines.append(f"   👨‍🏫 {faculty}")
            if syllabus_url:
                lines.append(f"   📄 [Syllabus PDF]({syllabus_url})")

        lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)


def format_assignments(data) -> str:
    """Format assignments API response into a readable message."""
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    now_str = ist_now.strftime("%d %b %Y, %I:%M %p IST")

    lines = [
        "📋 *ASSIGNMENTS DASHBOARD*",
        f"🕒 _{now_str}_",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    # Handle both list and dict responses
    items = data if isinstance(data, list) else data.get("result", data.get("data", []))

    if not items:
        lines.append("_No assignments found._")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)

    pending   = [a for a in items if not a.get("submitted", False) and not a.get("isSubmitted", False)]
    submitted = [a for a in items if a.get("submitted", False) or a.get("isSubmitted", False)]

    lines.append(f"📊 Total: *{len(items)}* | ✅ Submitted: *{len(submitted)}* | ⏳ Pending: *{len(pending)}*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    if pending:
        lines.append("⏳ *PENDING ASSIGNMENTS*")
        for a in pending[:10]:
            title   = a.get("title", a.get("assignmentTitle", "Untitled"))
            subject = a.get("subjectName", a.get("subject", {}).get("name", ""))
            due     = a.get("dueDate", a.get("lastDate", ""))
            if due:
                try:
                    due_dt  = datetime.fromisoformat(due.replace("Z", "+00:00"))
                    due_ist = due_dt + timedelta(hours=5, minutes=30)
                    due     = due_ist.strftime("%d %b %Y")
                except:
                    pass
            lines.append(f"\n🔴 *{title}*")
            if subject:
                lines.append(f"   📖 Subject: _{subject}_")
            if due:
                lines.append(f"   📅 Due: `{due}`")

    if submitted:
        lines.append(f"\n✅ *SUBMITTED ({len(submitted)})*")
        for a in submitted[:5]:
            title = a.get("title", a.get("assignmentTitle", "Untitled"))
            lines.append(f"   • _{title}_")
        if len(submitted) > 5:
            lines.append(f"   _...and {len(submitted)-5} more_")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════════════════════
#  Timetable report formatter
# ═══════════════════════════════════════════════════════════════════════════════
def format_timetable_report(results: dict) -> str:
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    now_str = ist_now.strftime("%d %b %Y, %I:%M %p IST")

    msg = [
        "🎓 *MRUH STUDENT DASHBOARD*",
        f"🕒 _{now_str}_",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    msg.append("🗓️ *TODAY'S TIMETABLE*")
    tt       = results.get("timetable", [])
    last_day = results.get("last_class_date", "")
    if tt:
        for entry in tt:
            msg.append(f"• {entry}")
    else:
        if last_day:
            msg.append(f"🏖️ _No classes today — you're on a break!_")
            msg.append(f"📅 _Last class was on: *{last_day}*_")
        else:
            msg.append("_No classes scheduled today._")

    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("📊 *ATTENDANCE & BUNK CALCULATOR*")
    msg.append("_(Based on completed classes this semester)_")

    att_data = results.get("attendance", [])
    if att_data:
        for item in sorted(att_data, key=lambda x: x["percentage"]):
            sub  = item["subject"]
            cond = item["conducted"]
            att  = item["attended"]
            pct  = item["percentage"]
            bi   = item["bunk_info"]
            emoji = "🟢" if pct >= 75 else ("🟡" if pct >= 65 else "🔴")
            msg.append(f"\n{emoji} *{sub}*")
            msg.append(f"   Attendance: *{pct:.1f}%* ({att}/{cond} classes)")
            msg.append(f"   {bi['message']}")
    else:
        msg.append("_No attendance data recorded yet._")

    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(msg)

# ═══════════════════════════════════════════════════════════════════════════════
#  Generic text handler
# ═══════════════════════════════════════════════════════════════════════════════
async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.lower().strip()
    if any(g in text for g in ["hi", "hello", "hey", "yo"]):
        await start_handler(update, context)
    elif "timetable" in text:
        await timetable_handler(update, context)
    elif "assignment" in text:
        await assignments_handler(update, context)
    elif "subject" in text:
        await subjects_handler(update, context)
    elif "result" in text:
        await results_handler(update, context)
    else:
        uid = str(update.effective_user.id)
        ud  = get_user_data(uid)
        if ud:
            await update.message.reply_text(
                "🤖 Use one of these commands:\n"
                "• `/timetable` — Schedule & attendance\n"
                "• `/assignments` — Your assignments\n"
                "• `/subjects` — Your subjects\n"
                "• `/results` — Semester results\n"
                "• `/whoami` — Account info\n"
                "• `/logout` — Remove session",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "🔒 *Please log in first!*\n\n"
                "• `/set_cookies` — Login via cookie *(recommended)*\n"
                "• `/setup_credentials` — Login via email & password",
                parse_mode=ParseMode.MARKDOWN
            )

# ═══════════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    token = get_token()
    if not token:
        print("CRITICAL: TELEGRAM_BOT_TOKEN is missing!")
        sys.exit(1)

    logger.info("Starting CampX Telegram Bot...")
    app = ApplicationBuilder().token(token).build()

    # Basic commands
    app.add_handler(CommandHandler("start",       start_handler))
    app.add_handler(CommandHandler("timetable",   timetable_handler))
    app.add_handler(CommandHandler("assignments",  assignments_handler))
    app.add_handler(CommandHandler("subjects",     subjects_handler))
    app.add_handler(CommandHandler("merit", merit_handler))
    app.add_handler(CommandHandler("whoami",       whoami_handler))
    app.add_handler(CommandHandler("logout",       logout_handler))

    # Login via email+password (uses Playwright)
    creds_conv = ConversationHandler(
        entry_points=[CommandHandler("setup_credentials", start_credentials_setup)],
        states={
            EMAIL:    [MessageHandler(filters.TEXT & ~filters.COMMAND, email_received)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )
    app.add_handler(creds_conv)

    # Login via cookie paste (no browser needed)
    cookies_conv = ConversationHandler(
        entry_points=[CommandHandler("set_cookies", start_set_cookies)],
        states={
            COOKIE_KEY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, cookie_key_received)],
            COOKIE_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, cookie_email_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )
    app.add_handler(cookies_conv)

    # Catch-all text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))

    print("Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
