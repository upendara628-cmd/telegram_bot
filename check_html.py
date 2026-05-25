import re

def search_keywords(filename):
    print("\n" + "="*50)
    print(f"SEARCHING IN: {filename}")
    print("="*50)
    
    with open(filename, "r", encoding="utf-8") as f:
        html = f.read()
        
    print(f"File size: {len(html)} bytes")
    
    # Check for tables
    tables = re.findall(r'<table[^>]*>', html, re.IGNORECASE)
    print(f"Number of <table> tags: {len(tables)}")
    
    # Check for percentages
    percentages = re.findall(r'(\b\d+(?:\.\d+)?\s*%)', html)
    print(f"Number of percentages found: {len(percentages)}")
    if percentages:
        print(f"Sample percentages: {percentages[:10]}")
        
    # Check for keywords
    for keyword in ["conducted", "attended", "present", "absent", "percentage", "timetable", "workspace"]:
        count = len(re.findall(re.escape(keyword), html, re.IGNORECASE))
        print(f"Keyword '{keyword}' count: {count}")
        
    # Let's search for table row texts if tables exist
    if tables:
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)
        print(f"Number of <tr> tags: {len(rows)}")
        for idx, row in enumerate(rows[:5]):
            # Strip tags to get text
            row_text = re.sub(r'<[^>]+>', ' | ', row)
            # Clean spaces
            row_text = " ".join(row_text.split())
            print(f"Row {idx+1}: {row_text[:150]}")
            
    # Print lines containing percentage signs to see context
    print("\n--- Context of percentage signs ---")
    lines = html.split("\n")
    found_lines = 0
    for line in lines:
        if "%" in line and not line.strip().startswith("<style") and not line.strip().startswith(".") and len(line) < 300:
            print(line.strip())
            found_lines += 1
            if found_lines >= 10:
                break

search_keywords("debug_attendance.html")
search_keywords("debug_dashboard.html")
search_keywords("debug_timetable.html")
