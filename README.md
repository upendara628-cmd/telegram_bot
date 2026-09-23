# MRU MUDU Timetable & Attendance Telegram Bot

A production-ready Telegram Bot that fetches class timetables, attendance statistics, assignments, enrolled subjects, exam results, and MeritCurve updates from the **Malla Reddy University (MRU)** student portals:
- **Primary Portal (MUDU):** [https://mru.mudu.in/](https://mru.mudu.in/)
- **Exam Results Portal:** [https://mruexams.com/](https://mruexams.com/)
- **MeritCurve Portal:** [https://mru.meritcurve.com/](https://mru.meritcurve.com/)

Migrated from the decommissioned CampX portal to MUDU's high-speed REST API backend, providing responses in milliseconds without requiring heavy browser rendering for every request.

---

## Features

- **Direct MUDU REST API Integration**:
  - Instant authentication (`POST /api/auth/login`) with JWT cookie management and automatic token refresh (`POST /api/auth/refresh`).
  - Section-based weekly and daily timetable extraction (`GET /api/admin/timetable/section/{sectionId}`).
  - Full course attendance summary with conducted, attended, and percentage calculations (`GET /api/admin/attendance/student/{linkedStudentId}/summary`).
  - Course assignment tracking with submission and pending status (`GET /api/admin/assessment-management/student/my-assessments`).
  - Enrolled subjects and faculty listing.
- **Attendance & Bunk Calculator**:
  - **Above 75%**: Computes exactly how many classes you can skip ("bunk") safely while staying at or above 75%.
  - **Below 75%**: Computes exactly how many consecutive upcoming classes you must attend to recover your attendance to 75%.
- **Multi-Portal Support**:
  - `/results` command extracts semester SGPA and subject grades from `mruexams.com`.
  - `/merit` command tracks upcoming quizzes, tests, and assignments from `mru.meritcurve.com`.
- **Flexible User Authentication**:
  - Direct in-chat credential setup (`/setup_credentials`).
  - Direct session cookie pasting (`/set_cookies`) with zero credential storage required.
  - Multi-user isolation backed by persistent JSON storage (`database.json`), cloud/Docker `/data` persistent volume support.
- **Playwright Fallback**: Retains headless Chromium automation fallback if API structure changes.

---

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Welcome message, user profile status, and command list |
| `/timetable` | Today's timetable and course-by-course attendance with bunk calculator |
| `/assignments` | List all active, submitted, and pending MUDU assignments |
| `/subjects` | List all enrolled subjects, course codes, credits, and faculty |
| `/results` | Fetch university exam results and SGPA from `mruexams.com` |
| `/merit` | Fetch dashboard status, tests, and quizzes from `mru.meritcurve.com` |
| `/whoami` | Show current active session, student name, roll number, and section |
| `/setup_credentials` | Interactive login with roll number / email and password |
| `/set_cookies` | Paste MUDU cookies / JWT token directly |
| `/logout` | Remove saved session and credentials |

---

## Project Structure

- `bot.py`: Main Telegram Bot application handling commands, conversation flows, and markdown formatting.
- `scraper.py`: Core MUDU API client, session management, Playwright fallback, mruexams scraper, and MeritCurve scraper.
- `attendance.py`: Pure math functions computing bunk allowance and attendance targets with built-in unit tests.
- `login.py`: Standalone CLI utility for initial session setup (direct API or browser login).
- `test_scraper.py`: Test suite for offline parsing heuristics (`--mock`) and live MUDU API scraping (`--live`).
- `test_direct_scraper.py`: Quick verification script testing end-to-end timetable, attendance, and bot report formatting.
- `config.json`: Configuration file with portal URLs and target percentage thresholds.
- `requirements.txt`: Python package dependencies.
- `Dockerfile`: Production Docker image based on Microsoft Playwright.

---

## Installation & Setup

### 1. Prerequisites
- **Python 3.10+** (Tested on Python 3.12 and 3.14)
- Google Chrome or Playwright Chromium binaries

### 2. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Environment Configuration
Create a `.env` file in the root directory (or copy from `.env.example`):
```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```
> Get your bot token from [@BotFather](https://t.me/BotFather) on Telegram.

---

## How to Run

### Option A: Direct Local Setup
1. **Log in once via CLI (Optional for testing):**
   ```bash
   python login.py
   ```
   Enter your roll number (e.g., `2511CS020116`) and password.

2. **Verify Scraper & Math:**
   ```bash
   python attendance.py
   python test_scraper.py --mock
   python test_scraper.py --live
   ```

3. **Start the Telegram Bot:**
   ```bash
   python bot.py
   ```

### Option B: Docker Deployment
Build and run the container with a persistent volume for session storage:
```bash
docker build -t mru-telegram-bot .
docker run -d --name mru-bot --restart unless-stopped -v mru_bot_data:/data --env-file .env mru-telegram-bot
```

---

## Testing & Verification

Run the test suite locally:
- **Attendance calculations:**
  ```bash
  python attendance.py
  ```
- **Scraper mock parser:**
  ```bash
  python test_scraper.py --mock
  ```
- **End-to-End Live API test:**
  ```bash
  python test_direct_scraper.py
  ```
