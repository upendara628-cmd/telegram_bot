import re

def parse():
    with open("attendance_page.html", "r", encoding="utf-8") as f:
        html = f.read()
        
    # Search for occurrences of Close (case insensitive)
    matches = re.finditer(r'close', html, re.IGNORECASE)
    print("=== OCCURRENCES OF 'CLOSE' ===")
    for m in matches:
        start = max(0, m.start() - 100)
        end = min(len(html), m.end() + 100)
        print(f"Context: ... {html[start:end].replace('\n', ' ')} ...\n")

if __name__ == "__main__":
    parse()
