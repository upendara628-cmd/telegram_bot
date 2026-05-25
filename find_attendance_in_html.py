import os
import re

def search():
    files = ["debug_attendance.html", "debug_dashboard.html", "debug_timetable.html"]
    
    keywords = ["conducted", "attended", "present", "absent", "%", "programming", "mathematics", "pps", "physics", "chemistry", "english"]
    
    for filename in files:
        if not os.path.exists(filename):
            print(f"File {filename} does not exist.")
            continue
            
        print(f"\n=== SEARCHING IN {filename} ===")
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
            
        print(f"File size: {len(content)} bytes")
        
        # Check keywords
        found = []
        for kw in keywords:
            matches = list(re.finditer(kw, content, re.IGNORECASE))
            if matches:
                found.append(f"{kw} ({len(matches)} matches)")
        print(f"Keywords found: {', '.join(found) if found else 'None'}")
        
        # If there are percentages, print some context
        pct_matches = list(re.finditer(r'\d+(?:\.\d+)?%', content))
        if pct_matches:
            print("Percentage occurrences:")
            for m in pct_matches[:5]:
                start = max(0, m.start() - 50)
                end = min(len(content), m.end() + 50)
                print(f"  ... {content[start:end].strip().replace('\n', ' ')} ...")
        else:
            print("No percentage signs found.")

if __name__ == "__main__":
    search()
