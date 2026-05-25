# Project Overview

This repository contains a **Telegram bot** that automates the retrieval and reporting of class timetables, attendance statistics, and MeritCurve assignment information for students of **Malla Reddy University (MRU)**.

## What the Bot Does
- **Telegram Interface** – Users interact via simple commands (`/start`, `/timetable`, `/attendance`, `/merit`, `/results`).
- **Playwright Scraper** – Uses a persistent browser context to log into the university portal (Google SSO) and the MeritCurve dashboard, extracting data without needing to re‑authenticate on every request.
- **Attendance Calculations** – Calculates safe bunk counts or required attendances to stay above the target percentage (default 75%).
- **MeritCurve Integration** – Retrieves the number of assignments, tests, and their titles/due dates from the MeritCurve portal (single shared password `mru@123`).
- **Dockerised Deployment** – Ready to run on Railway (or any container platform) using the provided `Dockerfile`.

## Core Components
| File | Purpose |
|------|---------|
| `bot.py` | Main Telegram bot, command handlers, and background execution. |
| `scraper.py` | Playwright‑based scraper for both the university portal and MeritCurve. |
| `attendance.py` | Helper functions for attendance math. |
| `login.py` | One‑time manual login script that stores the persistent Chrome profile. |
| `requirements.txt` | Python dependencies. |
| `Dockerfile` | Container definition used by Railway. |
| `config.json` | Customisable URLs, CSS selectors, and target attendance percentage. |

## Setup & Installation
1. **Clone the repo**
   ```bash
   git clone https://github.com/upendara628-cmd/telegram_bot.git
   cd telegram_bot
   ```
2. **Create an environment file**
   ```bash
   cp .env.example .env
   ```
   Fill in `TELEGRAM_BOT_TOKEN` (obtain from @BotFather).  Add any additional variables required for your setup.
3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```
5. **Initial login** – Run once to store the Google session:
   ```bash
   python login.py
   ```
   Follow the browser prompts, complete Google Sign‑In, then press **Enter**.
6. **(Optional) Test the scraper**
   ```bash
   python test_scraper.py --live
   ```
7. **Run the bot**
   ```bash
   python bot.py
   ```
   Interact via Telegram using the commands listed above.

## Deployment on Railway
The project is ready for Railway with a single‑step deployment:
1. Connect the GitHub repository to a Railway project.
2. Add the environment variables (`TELEGRAM_BOT_TOKEN`, `CAMPX_SESSION_KEY` if using cookie login, etc.) in Railway → Settings → Variables.
3. Railway automatically builds the Docker image defined in `Dockerfile` and runs `python bot.py`.
4. If you need to trigger a manual redeploy after code changes, use the Railway UI “Redeploy” button or run `railway up` from a local clone.

## Adding New Features
- **New Telegram Commands** – Add a handler in `bot.py` and register it with the `ApplicationBuilder`. Use the existing async pattern.
- **Additional Scraper Targets** – Extend `scraper.py` with new Playwright page interactions and return structured JSON for the bot.
- **Persisting Data** – Store user preferences in `database.json` or migrate to a proper DB if needed.

## License
This project is licensed under the MIT License – see the `LICENSE` file.

---
*Created by the Antigravity assistant to give an at‑a‑glance project summary.*
