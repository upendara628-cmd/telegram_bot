import os
import sys
import json
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters, ConversationHandler
)

import httpx
from scraper import (
    fetch_portal_data, login_and_save_session,
    AuthenticationRequiredError, get_user_data, save_user_data
)

# Load .env
load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("CampXBot")

# ── Conversation states ────────────────────────────────────────────────────────
EMAIL, PASSWORD = range(2)
COOKIE_KEY, COOKIE_SEM = range(10, 12)

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

# ── Auto-detect semNo from the CampX workspaces API ───────────────────────────
def detect_sem_no(cookies: dict) -> int:
    """Calls the CampX workspaces API to figure out the student's current semester."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://mruh.campx.in/",
            "Origin": "https://mruh.campx.in",
        }
        with httpx.Client(cookies=cookies, headers=headers, timeout=15) as client:
            r = client.get("https://api.campx.in/auth-server/auth-v2/workspaces")
            if r.status_code == 200:
                data = r.json()
                sem = data.get("user", {}).get("semNo")
                if sem:
                    return int(sem)
    except Exception as e:
        logger.warning(f"Could not detect semNo: {e}")
    return 2  # fallback

# ═══════════════════════════════════════════════════════════════════════════════
#  /start
# ═══════════════════════════════════════════════════════════════════════════════
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    ud = get_user_data(str(update.effective_user.id))
    status = f"✅ *Logged in as:* `{ud.get('email', 'unknown')}`" if ud else "⚠️ *Not logged in yet*"

    msg = (
        f"👋 **Hello {user.first_name}!**\n\n"
        f"I'm your **MRUH CampX Companion Bot**.\n"
        f"I fetch timetables & attendance for *any* MRUH student.\n\n"
        f"{status}\n\n"
        f"⚙️ **Commands:**\n"
        f"• `/setup_credentials` — Login with your email & password\n"
        f"• `/set_cookies` — Login by pasting your session cookie *(works on cloud)*\n"
        f"• `/timetable` — Get today's schedule & attendance\n"
        f"• `/whoami` — See which account is linked to you\n"
        f"• `/logout` — Remove your saved session\n"
        f"• `/start` — Show this message"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════════════════════════════
#  /whoami
# ═══════════════════════════════════════════════════════════════════════════════
async def whoami_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = str(update.effective_user.id)
    ud = get_user_data(uid)
    if not ud:
        await update.message.reply_text(
            "❌ You have no session saved.\n"
            "Use `/setup_credentials` or `/set_cookies` to log in.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    email = ud.get("email", "unknown")
    sem = ud.get("semNo", "?")
    updated = ud.get("updated_at", "unknown")
    await update.message.reply_text(
        f"👤 **Your linked account:**\n\n"
        f"📧 Email: `{email}`\n"
        f"📚 Semester: `{sem}`\n"
        f"🕒 Last updated: `{updated}`",
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════════════════════════════
#  /logout
# ═══════════════════════════════════════════════════════════════════════════════
async def logout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from scraper import load_db, save_db
    uid = str(update.effective_user.id)
    db = load_db()
    if uid in db.get("users", {}):
        del db["users"][uid]
        save_db(db)
        await update.message.reply_text(
            "✅ Your session has been removed.\n"
            "Use `/setup_credentials` or `/set_cookies` to log in again.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text("ℹ️ You had no saved session.")

# ═══════════════════════════════════════════════════════════════════════════════
#  /setup_credentials  (Email + Password → Playwright login)
# ═══════════════════════════════════════════════════════════════════════════════
async def start_credentials_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "📝 **Login with Email & Password**\n\n"
        "Send your MRUH portal email:\n"
        "*(e.g., `2511cs020116@mallareddyuniversity.ac.in`)*\n\n"
        "Type `/cancel` to abort.",
        parse_mode=ParseMode.MARKDOWN
    )
    return EMAIL

async def email_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip()
    if "@" not in email:
        await update.message.reply_text(
            "❌ That doesn't look like a valid email. Please send your full email address."
        )
        return EMAIL
    context.user_data["temp_email"] = email
    await update.message.reply_text(
        f"✅ Email saved: `{email}`\n\n"
        "🔑 Now send your portal password:\n"
        "*(it will be deleted immediately after login for privacy)*",
        parse_mode=ParseMode.MARKDOWN
    )
    return PASSWORD

async def password_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = update.message.text
    email = context.user_data.get("temp_email")
    telegram_id = str(update.effective_user.id)

    try:
        await update.message.delete()
    except Exception:
        pass

    status_msg = await update.message.reply_text(
        "⏳ **Logging in to CampX...**\n"
        "This uses a headless browser — please wait up to 30 seconds...",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        loop = asyncio.get_running_loop()
        success = await loop.run_in_executor(
            None, login_and_save_session, telegram_id, email, password
        )
        if success:
            ud = get_user_data(telegram_id)
            sem = ud.get("semNo", "?")
            await status_msg.edit_text(
                f"✅ **Login Successful!**\n\n"
                f"📧 Account: `{email}`\n"
                f"📚 Semester detected: `{sem}`\n\n"
                f"Use `/timetable` to fetch your data!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await status_msg.edit_text(
                "❌ **Login Failed!**\n"
                "The portal rejected your credentials.\n"
                "Double-check your email & password and try again.\n\n"
                "💡 *Tip: Try `/set_cookies` instead — it always works!*",
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logger.error(f"Credentials login failed for {email}: {e}")
        await status_msg.edit_text(
            f"❌ **Login Failed!**\n\n"
            f"`{str(e)[:250]}`\n\n"
            f"💡 *Try `/set_cookies` instead — it works without a browser.*",
            parse_mode=ParseMode.MARKDOWN
        )

    context.user_data.pop("temp_email", None)
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════════
#  /set_cookies  (Paste session cookie — no browser needed)
# ═══════════════════════════════════════════════════════════════════════════════
async def start_set_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🍪 **Manual Cookie Login**\n"
        "_Works on any cloud server — no browser needed!_\n\n"
        "📋 **Steps to get your cookie:**\n"
        "1️⃣ Open Chrome on your PC → go to `mruh.campx.in`\n"
        "2️⃣ Log in with your email & password\n"
        "3️⃣ Press `F12` → go to **Application** tab\n"
        "4️⃣ Click **Cookies** on the left → click `mruh.campx.in`\n"
        "5️⃣ Find the row named `campx_session_key`\n"
        "6️⃣ Copy the long value in the **Value** column\n\n"
        "📩 **Paste the value here now:**\n"
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
            "❌ That value looks too short to be a valid cookie.\n"
            "Please try `/set_cookies` again and copy the full value.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    context.user_data["temp_session_key"] = session_key

    # Also ask for email so we can label this session
    await update.message.reply_text(
        "✅ Cookie received!\n\n"
        "📧 Now send your **college email** so I can label your account:\n"
        "*(e.g., `2511cs020116@mallareddyuniversity.ac.in`)*\n\n"
        "_(Type `/cancel` to abort)_",
        parse_mode=ParseMode.MARKDOWN
    )
    return COOKIE_SEM

async def cookie_sem_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives email, auto-detects semNo from API, saves the full profile."""
    email = update.message.text.strip()
    session_key = context.user_data.pop("temp_session_key", "")
    telegram_id = str(update.effective_user.id)

    status_msg = await update.message.reply_text(
        "⏳ Verifying cookie & detecting your semester...",
        parse_mode=ParseMode.MARKDOWN
    )

    # Build cookies dict
    cookies = {
        "campx_session_key": session_key,
        "campx_tenant": "mruh",
        "campx_institution": "mruh",
    }

    # Auto-detect semNo from API
    loop = asyncio.get_running_loop()
    sem_no = await loop.run_in_executor(None, detect_sem_no, cookies)

    # Save to database under this user's telegram_id
    user_info = {
        "email": email if "@" in email else "unknown",
        "semNo": sem_no,
        "cookies": cookies,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_user_data(telegram_id, user_info)

    await status_msg.edit_text(
        f"✅ **Session saved successfully!**\n\n"
        f"📧 Account: `{email}`\n"
        f"📚 Semester detected: `{sem_no}`\n\n"
        f"Use `/timetable` to fetch your data now!\n\n"
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
#  /timetable
# ═══════════════════════════════════════════════════════════════════════════════
async def timetable_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)

    # Use this user's session; fall back to "default" if not registered
    user_data = get_user_data(telegram_id)
    target_id = telegram_id if user_data else "default"

    if not get_user_data(target_id):
        await update.message.reply_text(
            "❌ **No session found!**\n\n"
            "Please log in first using one of:\n"
            "• `/setup_credentials` — email & password login\n"
            "• `/set_cookies` — paste your session cookie *(recommended)*",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    status_msg = await update.message.reply_text(
        "⏳ **Fetching your data from CampX...**\n"
        "Making direct API request. This takes 2-5 seconds...",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, fetch_portal_data, target_id)
        await status_msg.edit_text(format_report(results), parse_mode=ParseMode.MARKDOWN)

    except AuthenticationRequiredError:
        await status_msg.edit_text(
            "❌ **Session Expired!**\n\n"
            "Your session cookie has expired.\n"
            "Please log in again:\n"
            "• `/set_cookies` — paste a fresh cookie *(fastest)*\n"
            "• `/setup_credentials` — email & password",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Timetable fetch failed for {telegram_id}: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ **Failed to fetch data.**\n\n"
            f"`{str(e)[:300]}`\n\n"
            f"Try `/set_cookies` to refresh your session.",
            parse_mode=ParseMode.MARKDOWN
        )

# ═══════════════════════════════════════════════════════════════════════════════
#  Format report
# ═══════════════════════════════════════════════════════════════════════════════
def format_report(results: dict) -> str:
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    now_str = ist_now.strftime("%d %b %Y, %I:%M %p IST")

    msg = [
        "🎓 **MRUH STUDENT DASHBOARD**",
        f"🕒 _{now_str}_",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    # Timetable
    msg.append("🗓️ **TODAY'S TIMETABLE**")
    tt = results.get("timetable", [])
    if tt:
        for entry in tt:
            msg.append(f"• {entry}")
    else:
        msg.append("_No classes scheduled today._")

    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Attendance
    msg.append("📊 **ATTENDANCE & BUNK CALCULATOR**")
    att_data = results.get("attendance", [])
    if att_data:
        # Sort by percentage ascending so low-attendance subjects appear first
        for item in sorted(att_data, key=lambda x: x["percentage"]):
            sub  = item["subject"]
            cond = item["conducted"]
            att  = item["attended"]
            pct  = item["percentage"]
            bi   = item["bunk_info"]

            emoji = "🟢" if pct >= 75 else ("🟡" if pct >= 65 else "🔴")
            msg.append(f"\n{emoji} **{sub}**")
            msg.append(f"   Attendance: **{pct:.1f}%** ({att}/{cond} classes)")
            msg.append(f"   {bi['message']}")
    else:
        msg.append("_No attendance data found._")

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
    else:
        await update.message.reply_text(
            "🤖 Use one of these commands:\n"
            "• `/timetable` — fetch schedule & attendance\n"
            "• `/set_cookies` — login via cookie\n"
            "• `/setup_credentials` — login via email/password\n"
            "• `/start` — help",
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

    # /start, /timetable, /whoami, /logout
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("timetable", timetable_handler))
    app.add_handler(CommandHandler("whoami", whoami_handler))
    app.add_handler(CommandHandler("logout", logout_handler))

    # /setup_credentials (Playwright browser login)
    creds_conv = ConversationHandler(
        entry_points=[CommandHandler("setup_credentials", start_credentials_setup)],
        states={
            EMAIL:    [MessageHandler(filters.TEXT & ~filters.COMMAND, email_received)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )
    app.add_handler(creds_conv)

    # /set_cookies (paste cookie — no browser needed)
    cookies_conv = ConversationHandler(
        entry_points=[CommandHandler("set_cookies", start_set_cookies)],
        states={
            COOKIE_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, cookie_key_received)],
            COOKIE_SEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, cookie_sem_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )
    app.add_handler(cookies_conv)

    # Text fallback
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))

    print("Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
