# MRUH CampX Timetable & Attendance Bot

A robust, production-ready Telegram Bot that scraps class timetables and attendance statistics from the MRUH (Malla Reddy University, Hyderabad) CampX student portal (`mruh.campx.in`), computes attendance calculations (safe bunks or required classes), and reports them directly to your Telegram chat.

Since the portal requires Google Sign-In, the script uses **Playwright's persistent browser context** so that you only have to log in manually once. Future checks run headlessly and automatically without needing re-authentication.

---

## Features

- **Automated Login Persistence**: Re-uses session cookies via persistent user profile directories (Google SSO compatible).
- **Attendance Math Calculator**:
  - **Above 75%**: Computes exactly how many classes can be skipped ("bunked") safely without falling below 75%.
  - **Below 75%**: Computes exactly how many consecutive upcoming classes must be attended to rise back to 75%.
- **Resilient Parsing Engine**: Matches column headers dynamically and falls back to text patterns/regular expressions, making it highly robust to portal layout updates.
- **Telegram Bot Interface**: Beautifully formatted reports with visual colored status indicators (🟢, 🟡, 🔴) and emojis, run asynchronously via background threads to keep the bot interface responsive.

---

## Project Structure

- `bot.py`: The entry-point for the Telegram bot interface.
- `scraper.py`: Core Playwright scraper engine containing DOM parsing, regex fallbacks, and authentication detectors.
- `attendance.py`: Modules containing attendance math and self-contained unit tests.
- `login.py`: Standalone setup utility for performing the initial login.
- `test_scraper.py`: A local test CLI tool to check scraper parsing offline or online.
- `config.json`: Configuration file for URLs, paths, and selectors.
- `requirements.txt`: Python package dependencies.
- `.env.example`: Template for credentials.

---

## Installation & Setup

### 1. Prerequisites
- **Python 3.8+** (Tested on Python 3.12+)
- **Google Chrome** or **Chromium** (Managed automatically by Playwright)

### 2. Install Dependencies
Clone or copy this project folder, open your terminal, and install the requirements:
```bash
pip install -r requirements.txt
```

Initialize Playwright browser binaries:
```bash
playwright install chromium
```

### 3. Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env
   ```
2. Open `.env` and set your `TELEGRAM_BOT_TOKEN`. (You can get a token from [@BotFather](https://t.me/BotFather) on Telegram).
3. (Optional) Open `config.json` and adjust configurations:
   - `target_attendance_percentage`: If your target threshold is different from `75.0`%.
   - `chrome_profile_dir`: Where the browser session profile is saved (defaults to a directory named `chrome_profile` inside the project folder).

---

## How to Run

### Step 1: Initial Login Setup (Mandatory)
Because the portal uses Google SSO, you must perform the login manually *once* to save the session context.

Run the login script:
```bash
python login.py
```

- A headful (visible) Chrome window will open.
- Navigate to the page, complete the Google Sign-In, and wait until you are redirected to the workspace dashboard/timetable.
- Return to your console/terminal and press **ENTER**. The browser session will close, and cookies/cache will be saved to your local `chrome_profile` folder.

### Step 2: Test the Scraper (Optional)
To verify everything works before starting the bot, run the test utility:
```bash
python test_scraper.py --live
```
This runs the scraper headlessly and prints the extracted schedule and calculated attendance metrics in the console.

### Step 3: Run the Bot
Start the Telegram Bot:
```bash
python bot.py
```
Open Telegram, search for your bot, and send `/start` or `/timetable`!

---

## Customize Selectors

If the university updates the student portal UI and parsing starts returning errors:
1. Run `python test_scraper.py --live --headful` to watch the browser process.
2. Inspect the table elements in Chrome Developer Tools (`F12`).
3. Update the selectors in `config.json`:
   - `timetable_selectors`:
     - `table`: CSS selector for the timetable table.
     - `row`: CSS selector for timetable rows.
     - `cell`: CSS selector for column cells.
   - `attendance_selectors`:
     - `table`: CSS selector for the attendance table.
     - `row`: CSS selector for attendance table rows.
     - `header`: CSS selector for header cells (e.g. `th`).
