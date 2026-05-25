import os
import json
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler

from scraper import fetch_portal_data, login_and_save_session, AuthenticationRequiredError, get_user_data

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("CampXTelegramBot")

def get_token() -> str:
    # First check environment variable, then check config.json
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token:
        return token
        
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                return config.get("telegram_bot_token", "")
        except Exception as e:
            logger.error(f"Error loading config.json for token: {e}")
            
    return ""

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greets the user and lists available commands."""
    user = update.effective_user
    greeting = (
        f"👋 **Hello {user.first_name}!**\n\n"
        f"I am your **MRUH Portal Companion Bot**.\n"
        f"I can fetch your timetable and attendance from CampX using a direct API integration (saving RAM and cloud resources) "
        f"and calculate safe bunks or required classes.\n\n"
        f"⚙️ **Available Commands:**\n"
        f"• `/timetable` - Fetch your schedule & attendance details.\n"
        f"• `/setup_credentials` - Configure your portal credentials via Telegram.\n"
        f"• `/start` - Show this message again."
    )
    await update.message.reply_text(greeting, parse_mode=ParseMode.MARKDOWN)

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles standard text messages like 'hi', 'hello', or keywords."""
    text = update.message.text.lower().strip()
    
    if any(greet in text for greet in ["hi", "hello", "hey", "yo"]):
        user = update.effective_user
        greeting = (
            f"👋 **Hello {user.first_name}!**\n\n"
            f"I am your **MRUH Portal Companion Bot**.\n"
            f"To get started, please use one of these commands:\n"
            f"• `/timetable` - Fetch today's timetable & attendance breakdown\n"
            f"• `/setup_credentials` - Configure portal login directly via Telegram\n"
            f"• `/start` - Show main welcome instructions"
        )
        await update.message.reply_text(greeting, parse_mode=ParseMode.MARKDOWN)
    elif "timetable" in text:
        await timetable_handler(update, context)
    elif "setup_credentials" in text or "credentials" in text:
        await start_credentials_setup(update, context)
    else:
        info_msg = (
            f"🤖 I didn't quite catch that. Here's what I can do:\n\n"
            f"• `/timetable` - Get your current schedule & attendance details\n"
            f"• `/setup_credentials` - Configure portal login details directly"
        )
        await update.message.reply_text(info_msg, parse_mode=ParseMode.MARKDOWN)

# State definitions for credentials setup
EMAIL, PASSWORD = range(2)

async def start_credentials_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begins the credentials login setup conversation."""
    await update.message.reply_text(
        "📝 **Setup Portal Credentials via Telegram**\n\n"
        "Please send your portal login email or roll number:\n"
        "*(e.g., `2511cs020116@mallareddyuniversity.ac.in`)*\n\n"
        "*(You can type `/cancel` at any time to abort)*",
        parse_mode=ParseMode.MARKDOWN
    )
    return EMAIL

async def email_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the username/email and asks for the password."""
    context.user_data["temp_email"] = update.message.text.strip()
    await update.message.reply_text(
        "🔑 **Please send your portal password:**\n"
        "*(Note: Your password is only kept in temporary memory during login authentication)*",
        parse_mode=ParseMode.MARKDOWN
    )
    return PASSWORD

async def password_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Performs the browser login check using the provided credentials."""
    password = update.message.text
    email = context.user_data.get("temp_email")
    telegram_id = str(update.effective_user.id)
    
    # Try to delete password message for privacy
    try:
        await update.message.delete()
    except Exception as e:
        logger.debug(f"Failed to delete password message: {e}")
        
    status_msg = await update.message.reply_text(
        "⏳ **Authenticating with CampX...**\n"
        "Launching automated headless login context to acquire session cookies. Please wait 15-20 seconds...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # Run Playwright login in executor thread to prevent blocking
        loop = asyncio.get_running_loop()
        success = await loop.run_in_executor(None, login_and_save_session, telegram_id, email, password)
        
        if success:
            await status_msg.edit_text(
                "✅ **Login Successful!**\n"
                "Your session profile has been securely saved to the database.\n\n"
                "You can now retrieve details anytime with `/timetable`!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await status_msg.edit_text(
                "❌ **Login Failed!**\n"
                "The portal rejected the credentials. Verify email/password and try again.",
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logger.error(f"Credentials login failed: {e}")
        await status_msg.edit_text(
            f"❌ **Login Failed!**\n\n"
            f"**Error Details:**\n`{str(e)[:200]}`\n\n"
            f"Please verify your credentials and try again.",
            parse_mode=ParseMode.MARKDOWN
        )
        
    # Clean up username from memory
    context.user_data.pop("temp_email", None)
    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the conversation and cleans up memory."""
    await update.message.reply_text("❌ Credentials configuration cancelled.")
    context.user_data.pop("temp_email", None)
    return ConversationHandler.END

async def timetable_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Triggers the scraper and replies with the formatted data."""
    telegram_id = str(update.effective_user.id)
    
    # Check if this user has credentials in db. If not, check if we have a default session.
    user_data = get_user_data(telegram_id)
    target_id = telegram_id if user_data else "default"
    
    status_msg = await update.message.reply_text(
        "⏳ **Fetching details from MRUH portal...**\n"
        "Making direct API request to CampX. Please wait...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # Run the synchronous API scraper in a separate executor thread
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, fetch_portal_data, target_id)
        
        # Format the scraped results
        formatted_message = format_report(results)
        
        # Edit the status message with final report
        await status_msg.edit_text(formatted_message, parse_mode=ParseMode.MARKDOWN)
        
    except AuthenticationRequiredError:
        logger.warning("API Scraper failed: Authentication required.")
        await status_msg.edit_text(
            "❌ **Session Expired or Missing!**\n\n"
            "The bot could not authenticate automatically.\n"
            "Please configure your portal login details on Telegram:\n"
            "Run: `/setup_credentials`",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"API Scraper failed with error: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ **Failed to extract portal data.**\n\n"
            f"**Error Details:**\n`{str(e)[:200]}`\n\n"
            f"Please verify your credentials or network status and try again.",
            parse_mode=ParseMode.MARKDOWN
        )

def format_report(results: dict) -> str:
    """Formats the raw scraped results into a premium markdown report."""
    # Convert UTC to IST (+5:30) for current timestamp print
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    now_str = ist_now.strftime("%Y-%m-%d %I:%M %p")
    
    msg = [
        "🎓 **MRUH STUDENT DASHBOARD REPORT**",
        f"🕒 *Generated on: {now_str}*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    # 1. Timetable Section
    msg.append("🗓️ **TODAY'S TIMETABLE**")
    if results.get("timetable"):
        for entry in results["timetable"]:
            msg.append(f"• {entry}")
    else:
        msg.append("_No classes scheduled today or timetable unavailable._")
        
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # 2. Attendance & Bunk Section
    msg.append("📊 **ATTENDANCE & BUNK CALCULATOR**")
    
    attendance_data = results.get("attendance", [])
    if attendance_data:
        for item in attendance_data:
            sub = item["subject"]
            cond = item["conducted"]
            att = item["attended"]
            pct = item["percentage"]
            bi = item["bunk_info"]
            
            # Determine color prefix emoji based on attendance percentage
            if pct >= 75.0:
                color_emoji = "🟢"
            elif pct >= 65.0:
                color_emoji = "🟡"
            else:
                color_emoji = "🔴"
                
            msg.append(f"\n{color_emoji} **{sub}**")
            msg.append(f"   • Attendance: **{pct:.2f}%** ({att}/{cond} classes)")
            msg.append(f"   • **Status:** {bi['message']}")
    else:
        msg.append("_No attendance statistics found._")
        
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    return "\n".join(msg)

def main() -> None:
    token = get_token()
    if not token:
        print("CRITICAL ERROR: Telegram Bot Token is missing.")
        sys.exit(1)
        
    logger.info("Starting Telegram Bot Application...")
    
    # Initialize the Application
    app = ApplicationBuilder().token(token).build()
    
    # Add Command Handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("timetable", timetable_handler))
    
    # Add Conversation Handler for credential configuration
    credentials_conv = ConversationHandler(
        entry_points=[CommandHandler("setup_credentials", start_credentials_setup)],
        states={
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, email_received)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )
    app.add_handler(credentials_conv)
    
    # Add Message Handler for non-command text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    
    # Run the bot
    print("Telegram bot is running. Send /start in Telegram to interact.")
    app.run_polling()

if __name__ == "__main__":
    import sys
    main()
