import re

def parse():
    with open("login_failed_final.html", "r", encoding="utf-8") as f:
        html = f.read()
        
    # Find all input fields
    inputs = re.findall(r'<input[^>]*>', html)
    print("=== INPUT FIELDS ===")
    for inp in inputs:
        print(inp)
        
    # Find all buttons
    buttons = re.findall(r'<button[^>]*>.*?</button>', html, re.DOTALL)
    print("\n=== BUTTONS ===")
    for btn in buttons:
        # Strip long interior HTML if any
        cleaned_btn = re.sub(r'\s+', ' ', btn).strip()
        if len(cleaned_btn) > 200:
            cleaned_btn = cleaned_btn[:200] + "..."
        print(cleaned_btn)
        
    # Find all forms
    forms = re.findall(r'<form[^>]*>', html)
    print("\n=== FORMS ===")
    for form in forms:
        print(form)
        
    # Find some page headings or text
    body_text = re.sub(r'<[^>]*>', ' ', html)
    body_text = re.sub(r'\s+', ' ', body_text).strip()
    print("\n=== SAMPLE TEXT ===")
    # Print first 1000 chars of visible text
    print(body_text[:1000])

if __name__ == "__main__":
    parse()
