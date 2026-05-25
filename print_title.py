import re

def print_summary(filename):
    print("\n" + "="*50)
    print(f"SUMMARY FOR: {filename}")
    print("="*50)
    
    with open(filename, "r", encoding="utf-8") as f:
        html = f.read()
        
    title = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    print("Title:", title.group(1).strip() if title else "No Title")
    
    body = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    if body:
        body_content = body.group(1)
        # Strip script and style blocks
        body_content = re.sub(r'<script[^>]*>.*?</script>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
        body_content = re.sub(r'<style[^>]*>.*?</style>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
        # Strip HTML tags
        cleaned = re.sub(r'<[^>]+>', ' ', body_content)
        cleaned = " ".join(cleaned.split())
        print("Body Text (first 800 chars):")
        print(cleaned[:800])
    else:
        print("No <body> tag found")

print_summary("debug_timetable.html")
