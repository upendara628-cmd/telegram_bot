import re
import os
import sys

def extract():
    log_path = r"C:\Users\upender\.gemini\antigravity\brain\35dcc180-3af3-46fe-94d6-8f6c4e190996\.system_generated\tasks\task-495.log"
    if not os.path.exists(log_path):
        print("Log file not found.")
        return
        
    with open(log_path, "r", encoding="utf-8") as f:
        text = f.read()
        
    # Find all API RESPONSE JSON blocks
    import re
    # Match blocks starting with API RESPONSE JSON up to the next === boundary
    blocks = re.findall(r'(API RESPONSE JSON:.*?\n={80})', text, re.DOTALL)
    
    # Save the extracted API responses
    with open("api_responses_extracted.txt", "w", encoding="utf-8") as f:
        f.write("\n\n".join(blocks))
        
    print(f"Successfully extracted {len(blocks)} JSON API responses and saved to 'api_responses_extracted.txt'.")
    
    print("\n--- Extracted API Call Summary (ASCII safe) ---")
    for idx, block in enumerate(blocks):
        # Clean lines from the block
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        # Print URL, status, and headers
        print(f"\n[API {idx+1}]")
        for line in lines[:5]:
            ascii_line = line.encode('ascii', 'ignore').decode('ascii')
            print(f"  {ascii_line}")
        if len(lines) > 5:
            print("  ... (response body hidden for brevity)")

if __name__ == "__main__":
    extract()
