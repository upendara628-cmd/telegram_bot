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
from telegram.request import HTTPXRequest

import httpx

from scraper import (
    fetch_portal_data, login_and_save_session,
    AuthenticationRequiredError, get_user_data, save_user_data,
    fetch_assignments, fetch_subjects,
    fetch_mru_results, fetch_merit_data, format_merit_report
)

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("MUDUBot")

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

# ── Auto-detect semNo from MUDU API ──────────────────────────────────────────
def detect_sem_no(cookies: dict) -> int:
    try:
        from scraper import MUDU_BASE_URL, MUDU_HEADERS
        with httpx.Client(cookies=cookies, headers=MUDU_HEADERS, timeout=15) as client:
            r = client.get(f"{MUDU_BASE_URL}/auth/me")
            if r.status_code == 200:
                linked_id = r.json().get("data", {}).get("user", {}).get("linkedStudentId")
                if linked_id:
                    sr = client.get(f"{MUDU_BASE_URL}/admin/students/{linked_id}")
                    if sr.status_code == 200:
                        return int(sr.json().get("data", {}).get("currentSemester", 2))
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
        name  = ud.get("fullName") or ud.get("rollNo") or ud.get("email", "Student")
        roll  = ud.get("rollNo", "")
        email = ud.get("email", "unknown")
        sem   = ud.get("semNo", ud.get("currentSemester", "Active"))
        status_line = (
            f"✅ *Logged in as:* `{name}`\n"
            f"🎓 *Roll No:* `{roll}`\n"
            f"📧 *Account:* `{email}`"
        )
        feature_lines = (
            f"⚙️ *What you can do:*\n"
            f"• `/timetable` — Today's schedule & attendance (with bunk calculator)\n"
            f"• `/assignments` — Active & submitted assignments\n"
            f"• `/subjects` — Enrolled subjects & credits\n"
            f"• `/results` — Semester results from MRU Exams portal\n"
            f"• `/merit` — MeritCurve dashboard\n"
            f"• `/whoami` — Your linked account details\n"
            f"• `/logout` — Remove your session\n"
        )
    else:
        status_line = "⚠️ *Not logged in yet*"
        feature_lines = (
            f"⚙️ *Get started by logging in:*\n"
            f"• `/setup_credentials` — Login with Roll No & Password *(instant)*\n"
            f"• `/set_cookies` — Paste MUDU session cookie\n\n"
            f"_After login you can use: `/timetable`, `/assignments`, `/subjects`, `/results`_"
        )

    await update.message.reply_text(
        f"👋 *Hello student!*\n\n"
        f"I'm your *MRU Student Companion Bot* (MUDU Portal).\n"
        f"Any MRU student can use me with their own account.\n\n"
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
    name    = ud.get("fullName", "Student")
    roll    = ud.get("rollNo", "unknown")
    email   = ud.get("email", "unknown")
    sem     = ud.get("semNo", ud.get("currentSemester", "?"))
    updated = ud.get("updated_at", "unknown")
    await update.message.reply_text(
        f"👤 *Your linked MUDU account:*\n\n"
        f"📛 Name: *{name}*\n"
        f"🎓 Roll No: `{roll}`\n"
        f"📧 Account: `{email}`\n"
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
            f"Use `/setup_credentials` or `/set_cookies` to log in again.",
            parse_mode=ParseMode.MARKDOWN
        )

# ═══════════════════════════════════════════════════════════════════════════════
#  /setup_credentials  (Roll No / Email + Password → Direct MUDU API login)
# ═══════════════════════════════════════════════════════════════════════════════
async def start_credentials_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "📝 *Login to MUDU Portal*\n\n"
        "Send your MRU *Roll Number* or *College Email*:\n"
        "_(e.g., `2511CS020116` or `2511cs020116@mallareddyuniversity.ac.in`)_\n\n"
        "Type `/cancel` to abort.",
        parse_mode=ParseMode.MARKDOWN
    )
    return EMAIL

async def email_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    identifier = update.message.text.strip()
    if len(identifier) < 4:
        await update.message.reply_text(
            "❌ That looks too short to be a valid roll number or email.\n"
            "Please send your full roll number or email address."
        )
        return EMAIL
    context.user_data["temp_email"] = identifier
    await update.message.reply_text(
        f"✅ Account: `{identifier}`\n\n"
        "🔑 Now send your MUDU portal *password:*\n"
        "_(it's verified immediately and deleted from chat)_",
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
        "⏳ *Logging in to MUDU Portal...*\n"
        "Verifying credentials directly with MUDU API...",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        loop = asyncio.get_running_loop()
        success = await loop.run_in_executor(
            None, login_and_save_session, telegram_id, email, password
        )
        if success:
            ud   = get_user_data(telegram_id)
            name = ud.get("fullName", "")
            roll = ud.get("rollNo", email)
            sem  = ud.get("semNo", ud.get("currentSemester", "Active"))
            name_str = f"👤 *Name:* {name}\n" if name else ""
            await status_msg.edit_text(
                f"✅ *Login Successful!*\n\n"
                f"{name_str}"
                f"🎓 *Roll No:* `{roll}`\n"
                f"📚 *Semester:* `{sem}`\n\n"
                f"You can now use `/timetable`, `/assignments`, `/subjects`!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await status_msg.edit_text(
                "❌ *Login Failed!*\n"
                "Wrong roll number or password.\n\n"
                "💡 Try `/set_cookies` instead.",
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logger.error(f"Credentials login failed for {email}: {e}")
        await status_msg.edit_text(
            f"❌ *Login Failed!*\n\n"
            f"`{str(e)[:250]}`\n\n"
            f"💡 Try `/setup_credentials` again with your correct password, or use `/set_cookies`.",
            parse_mode=ParseMode.MARKDOWN
        )
    context.user_data.pop("temp_email", None)
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════════
#  /set_cookies  (Paste session cookie / access_token — no browser needed)
# ═══════════════════════════════════════════════════════════════════════════════
async def start_set_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🍪 *Manual Cookie Login (MUDU Portal)*\n"
        "_Works on any cloud server — no browser needed!_\n\n"
        "📋 *How to get your cookie:*\n"
        "1️⃣ Open browser on your PC/phone → go to `https://mru.mudu.in`\n"
        "2️⃣ Log in with your Roll Number & Password\n"
        "3️⃣ Press `F12` (DevTools) → go to *Application* tab\n"
        "4️⃣ Click *Cookies* on the left → click `https://mru.mudu.in`\n"
        "5️⃣ Copy the value in the `access_token` row (or `refresh_token`)\n\n"
        "📩 *Paste the token/cookie value here now:*\n"
        "_(Type `/cancel` to abort)_",
        parse_mode=ParseMode.MARKDOWN
    )
    return COOKIE_KEY

async def cookie_key_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw_token = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass

    if len(raw_token) < 20:
        await update.message.reply_text(
            "❌ That value is too short to be a valid token.\n"
            "Please try `/set_cookies` again and copy the full value.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    context.user_data["temp_session_key"] = raw_token
    await update.message.reply_text(
        "✅ Token received!\n\n"
        "📧 Now send your *Roll Number* or *College Email*:\n"
        "_(e.g., `2511CS020116`)_\n\n"
        "_(Type `/cancel` to abort)_",
        parse_mode=ParseMode.MARKDOWN
    )
    return COOKIE_EMAIL

def _validate_mudu_cookie(token_or_cookies: str, identifier: str) -> dict:
    from scraper import MUDU_BASE_URL, MUDU_HEADERS
    # Parse cookie string or raw token
    cookies = {}
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

async def cookie_email_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    identifier  = update.message.text.strip()
    session_key = context.user_data.pop("temp_session_key", "")
    telegram_id = str(update.effective_user.id)

    status_msg = await update.message.reply_text(
        "⏳ Verifying MUDU session token...",
        parse_mode=ParseMode.MARKDOWN
    )

    loop = asyncio.get_running_loop()
    user_info = await loop.run_in_executor(None, _validate_mudu_cookie, session_key, identifier)
    save_user_data(telegram_id, user_info)

    name_str = f"👤 *Name:* `{user_info.get('fullName')}`\n" if user_info.get('fullName') else ""
    roll_str = f"🎓 *Roll No:* `{user_info.get('rollNo')}`\n" if user_info.get('rollNo') else ""

    await status_msg.edit_text(
        f"✅ *Session saved!*\n\n"
        f"{name_str}"
        f"{roll_str}"
        f"📧 Account: `{identifier}`\n\n"
        f"You can now use:\n"
        f"• `/timetable` — Schedule & attendance\n"
        f"• `/assignments` — Your assignments\n"
        f"• `/subjects` — Your subjects\n\n"
        f"⚠️ _Tokens expire periodically. Use `/setup_credentials` for automated re-login or run `/set_cookies` if it expires._",
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
        "Connecting to MUDU portal...",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        loop    = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, fetch_portal_data, telegram_id)
        await status_msg.edit_text(format_timetable_report(results), parse_mode=ParseMode.MARKDOWN)

    except AuthenticationRequiredError:
        await status_msg.edit_text(
            "❌ *Session Expired!*\n\n"
            "Your session has expired. Please log in again:\n"
            "• `/setup_credentials` — Roll number/email & password *(fastest)*\n"
            "• `/set_cookies` — Paste fresh session token",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Timetable fetch failed: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ *Failed to fetch data from MUDU portal.*\n\n`{str(e)[:300]}`\n\n"
            f"Try `/setup_credentials` to refresh your session.",
            parse_mode=ParseMode.MARKDOWN
        )

# ═══════════════════════════════════════════════════════════════════════════════
#  /assignments  🔒 Login required
# ═══════════════════════════════════════════════════════════════════════════════
async def assignments_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_login(update):
        return

    telegram_id = str(update.effective_user.id)
    ud          = get_user_data(telegram_id)
    cookies     = ud.get("cookies", {})

    status_msg = await update.message.reply_text(
        "⏳ *Fetching your assignments from MUDU portal...*",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        loop   = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, fetch_assignments, cookies)
        await status_msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)
    except AuthenticationRequiredError:
        await status_msg.edit_text(
            "❌ *Session Expired!*\n\nPlease run `/setup_credentials` or `/set_cookies` to log in again.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Assignments fetch failed: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ *Failed to fetch assignments.*\n\n`{str(e)[:300]}`",
            parse_mode=ParseMode.MARKDOWN
        )

# ═══════════════════════════════════════════════════════════════════════════════
#  /subjects  🔒 Login required
# ═══════════════════════════════════════════════════════════════════════════════
async def subjects_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_login(update):
        return

    telegram_id = str(update.effective_user.id)
    ud          = get_user_data(telegram_id)
    cookies     = ud.get("cookies", {})
    linked_sid  = ud.get("linkedStudentId")

    status_msg = await update.message.reply_text(
        "⏳ *Fetching your enrolled subjects from MUDU portal...*",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        loop   = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, fetch_subjects, cookies, linked_sid)
        await status_msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)
    except AuthenticationRequiredError:
        await status_msg.edit_text(
            "❌ *Session Expired!*\n\nPlease run `/setup_credentials` or `/set_cookies` to log in again.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Subjects fetch failed: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ *Failed to fetch subjects.*\n\n`{str(e)[:300]}`",
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
def format_timetable_report(results: dict) -> str:
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    now_str = ist_now.strftime("%d %b %Y, %I:%M %p IST")
    day_name = results.get("day_name", ist_now.strftime("%A").upper())
    student_name = results.get("student_name", "")
    roll_no = results.get("roll_no", "")
    overall_pct = results.get("overall_percentage")

    msg = [
        "🎓 *MRU STUDENT DASHBOARD (MUDU)*",
        f"🕒 _{now_str}_",
    ]
    if student_name or roll_no:
        ident = f"👤 *{student_name}*" if student_name else ""
        if roll_no:
            ident += f" (`{roll_no}`)" if ident else f"🎓 Roll: `{roll_no}`"
        msg.append(ident)

    if overall_pct is not None:
        ov_emoji = "🟢" if overall_pct >= 75 else ("🟡" if overall_pct >= 65 else "🔴")
        msg.append(f"{ov_emoji} Overall Attendance: *{overall_pct:.2f}%*")

    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append(f"🗓️ *TODAY'S TIMETABLE ({day_name})*")
    tt = results.get("timetable", [])
    if tt:
        for entry in tt:
            msg.append(f"• {entry}")
    else:
        msg.append(f"🏖️ _No classes scheduled for {day_name.title()}._")

    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("📊 *ATTENDANCE & BUNK CALCULATOR*")
    msg.append("_(Target threshold: 75.0%)_")

    att_data = results.get("attendance", [])
    if att_data:
        for item in sorted(att_data, key=lambda x: x["percentage"]):
            sub   = item["subject"]
            cond  = item["conducted"]
            att   = item["attended"]
            pct   = item["percentage"]
            bi    = item["bunk_info"]
            emoji = "🟢" if pct >= 75 else ("🟡" if pct >= 65 else "🔴")
            msg.append(f"\n{emoji} *{sub}*")
            msg.append(f"   Attendance: *{pct:.1f}%* ({att}/{cond} classes)")
            msg.append(f"   {bi['message']}")
    else:
        msg.append("_No attendance data recorded yet._")

    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(msg)

format_report = format_timetable_report

# ═══════════════════════════════════════════════════════════════════════════════
#  Generic text handler
# ═══════════════════════════════════════════════════════════════════════════════
async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    text = update.message.text.lower().strip()
    user = update.effective_user
    logger.info(f"Incoming message from {user.id} (@{user.username}): '{text}'")

    if any(g in text for g in ["hi", "hello", "hey", "yo", "start"]):
        await start_handler(update, context)
    elif any(k in text for k in ["timetable", "schedule", "attendance"]):
        await timetable_handler(update, context)
    elif "assignment" in text:
        await assignments_handler(update, context)
    elif any(k in text for k in ["subject", "course"]):
        await subjects_handler(update, context)
    elif any(k in text for k in ["result", "marks", "sgpa"]):
        await results_handler(update, context)
    elif any(k in text for k in ["merit", "quiz"]):
        await merit_handler(update, context)
    elif any(k in text for k in ["whoami", "profile", "account"]):
        await whoami_handler(update, context)
    else:
        uid = str(update.effective_user.id)
        ud  = get_user_data(uid)
        if ud:
            name = ud.get("fullName") or ud.get("rollNo") or "Student"
            await update.message.reply_text(
                f"👋 Hello *{name}*! Choose an option:\n\n"
                "• `/timetable` — Schedule & attendance (with bunk calculator)\n"
                "• `/assignments` — Assignments & submissions\n"
                "• `/subjects` — Enrolled subjects & faculty\n"
                "• `/results` — Semester exam results\n"
                "• `/merit` — MeritCurve dashboard\n"
                "• `/whoami` — Account info\n"
                "• `/logout` — Remove session",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "🔒 *Please log in first!*\n\n"
                "• `/setup_credentials` — Login with roll number & password *(fastest)*\n"
                "• `/set_cookies` — Login via session cookie",
                parse_mode=ParseMode.MARKDOWN
            )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.warning(f"Handled Telegram exception: {context.error}")

# ═══════════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    token = get_token()
    if not token:
        print("CRITICAL: TELEGRAM_BOT_TOKEN is missing!")
        sys.exit(1)

    logger.info("Starting MUDU Telegram Bot...")
    req = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )
    app = ApplicationBuilder().token(token).request(req).build()

    # Error handler
    app.add_error_handler(error_handler)

    # Basic commands
    app.add_handler(CommandHandler("start",       start_handler))
    app.add_handler(CommandHandler("timetable",   timetable_handler))
    app.add_handler(CommandHandler("assignments",  assignments_handler))
    app.add_handler(CommandHandler("subjects",     subjects_handler))
    app.add_handler(CommandHandler(["results", "result"], results_handler))
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
    app.run_polling(bootstrap_retries=-1, timeout=20)

if __name__ == "__main__":
    main()
