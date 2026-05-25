import re
import os

def extract_logs():
    log_path = r"C:\Users\upender\.gemini\antigravity\brain\35dcc180-3af3-46fe-94d6-8f6c4e190996\.system_generated\tasks\task-467.log"
    if not os.path.exists(log_path):
        print(f"Log file not found at: {log_path}")
        return
        
    with open(log_path, "r", encoding="utf-8") as f:
        log_content = f.read()
        
    # Find all API response block matches (delimited by the star emoji and = boundary lines)
    api_blocks = re.findall(r'(JSON API RESPONSE:.*?\n={80})', log_content, re.DOTALL)
    print(f"Total API responses intercepted: {len(api_blocks)}")
    
    for idx, block in enumerate(api_blocks):
        print(f"\n" + "#"*80)
        print(f"API CALL {idx + 1}:")
        print("#"*80)
        print(block)

if __name__ == "__main__":
    extract_logs()
