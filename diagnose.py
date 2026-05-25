"""
Diagnose: check real subject field names and today's timetable data.
"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import httpx
from datetime import datetime, timedelta, timezone

with open("database.json", "r") as f:
    db = json.load(f)
cookies = db["users"]["default"]["cookies"]
sem_no  = db["users"]["default"].get("semNo", 2)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://mruh.campx.in/",
    "Origin": "https://mruh.campx.in",
    "accept": "application/json, text/plain, */*",
    "x-institution-code": "mruh",
    "x-platform-id": "campx",
    "x-tenant-id": "mruh",
    "x-campx-client": "student-web",
}

ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
today_str = ist.strftime("%Y-%m-%d")
print(f"Today (IST): {today_str}")
print(f"Semester: {sem_no}")

with httpx.Client(cookies=cookies, headers=HEADERS, timeout=20) as client:

    # ── 1. SUBJECTS ──────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("SUBJECTS API")
    print("="*60)
    r = client.get(f"https://api.campx.in/student-api/subjects?semNo={sem_no}")
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        subs = r.json()
        print(f"Count: {len(subs)}")
        if subs:
            print(f"\nFirst subject ALL keys:")
            print(json.dumps(subs[0], indent=2))
            print(f"\nAll subjects (name field scan):")
            for s in subs:
                # Print every string field to find the name
                for k, v in s.items():
                    if isinstance(v, str) and len(v) > 3:
                        print(f"  [{k}] = {v}")
                print("  ---")

    # ── 2. TIMETABLE (today) ─────────────────────────────────────────────────
    print("\n" + "="*60)
    print(f"TIMETABLE FOR TODAY: {today_str}")
    print("="*60)
    r2 = client.get("https://api.campx.in/student-api/classroom-timetables")
    if r2.status_code == 200:
        all_entries = r2.json()
        today_entries = [e for e in all_entries if e.get("sessionDate") == today_str]
        print(f"Total entries in API: {len(all_entries)}")
        print(f"Entries for today:    {len(today_entries)}")
        if today_entries:
            print("\nFirst today entry:")
            print(json.dumps(today_entries[0], indent=2))
        else:
            print("\nNo entries for today. Checking nearby dates...")
            dates = sorted(set(e.get("sessionDate","") for e in all_entries if e.get("sessionDate","")))
            print(f"Latest 5 dates with data: {dates[-5:]}")
