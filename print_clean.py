import re

def print_summary(filename):
    print("\n" + "="*50)
    print(f"SUMMARY FOR: {filename}")
    print("="*50)
    
    try:
        with open(filename, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception as e:
        print(f"Error opening file: {e}")
        return
        
    title = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    print("Title:", title.group(1).strip() if title else "No Title")
    
    body = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    if body:
        body_content = body.group(1)
        body_content = re.sub(r'<script[^>]*>.*?</script>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
        body_content = re.sub(r'<style[^>]*>.*?</style>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<[^>]+>', ' ', body_content)
        cleaned = " ".join(cleaned.split())
        # Remove non-ASCII characters
        cleaned_ascii = cleaned.encode('ascii', 'ignore').decode('ascii')
        print("Body Text (first 1000 chars):")
        print(cleaned_ascii[:1000])
    else:
        print("No <body> tag found")

if __name__ == "__main__":
    print_summary("debug_attendance.html")
    print_summary("debug_dashboard.html")
