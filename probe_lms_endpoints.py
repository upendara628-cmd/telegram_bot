"""
Probe likely CampX API endpoints for subjects/LMS data directly using saved cookies.
"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')

import httpx

# Load cookies from database.json
with open("database.json", "r") as f:
    db = json.load(f)
cookies = db["users"]["default"]["cookies"]
sem_no = db["users"]["default"].get("semNo", 2)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://mruh.campx.in/",
    "Origin": "https://mruh.campx.in",
    "accept": "application/json, text/plain, */*",
    "x-institution-code": "mruh",
    "x-platform-id": "campx",
    "x-tenant-id": "mruh",
    "x-campx-client": "student-web",
}

# List of candidate endpoints to probe
CANDIDATES = [
    "https://api.campx.in/student-api/subjects",
    "https://api.campx.in/student-api/lms-subjects",
    "https://api.campx.in/student-api/lms",
    "https://api.campx.in/student-api/courses",
    "https://api.campx.in/student-api/learning-contents",
    "https://api.campx.in/student-api/learning-contents?semNo=2",
    f"https://api.campx.in/student-api/learning-contents?semNo={sem_no}",
    "https://api.campx.in/lms/student/subjects",
    "https://api.campx.in/lms/subjects",
    "https://api.campx.in/lms/courses",
    "https://api.campx.in/student-api/classroom-timetables?distinct=subject",
    "https://api.campx.in/student-api/syllabus",
    "https://api.campx.in/student-api/enrolled-subjects",
    "https://api.campx.in/student-api/student-subjects",
    "https://api.campx.in/admin/subjects",
    f"https://api.campx.in/student-api/subjects?semNo={sem_no}",
    f"https://api.campx.in/student-api/courses?semNo={sem_no}",
    "https://api.campx.in/student-api/lms/contents",
    "https://api.campx.in/student-api/lms/subjects",
    "https://api.campx.in/student-api/learning-management",
    "https://api.campx.in/student-api/my-subjects",
    "https://api.campx.in/student-api/subject-list",
]

print(f"[*] Probing {len(CANDIDATES)} endpoints...\n")

results = []
with httpx.Client(cookies=cookies, headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
    for url in CANDIDATES:
        try:
            r = client.get(url)
            status = r.status_code
            try:
                body = r.json()
                if isinstance(body, list):
                    size = f"LIST({len(body)})"
                    preview = str(body[0])[:120] if body else "empty"
                elif isinstance(body, dict):
                    size = f"DICT{list(body.keys())[:4]}"
                    preview = ""
                else:
                    size = str(type(body))
                    preview = ""
            except:
                size = f"non-JSON ({len(r.text)} chars)"
                preview = r.text[:80]

            marker = "<<<< HIT!" if status == 200 else f"[{status}]"
            print(f"{marker} {size}")
            print(f"       {url}")
            if preview:
                print(f"       Preview: {preview[:120]}")
            print()

            if status == 200:
                results.append({"url": url, "size": size, "body": body if status == 200 else None})
        except Exception as e:
            print(f"[ERR] {url}: {e}\n")

# Save hits
if results:
    with open("lms_subjects_hits.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n[+] Saved {len(results)} successful responses to lms_subjects_hits.json")
else:
    print("\n[!] No endpoints returned 200. Need to intercept browser traffic.")
