import os

log_path = r"C:\Users\upender\AppData\Local\Temp" # Wait, let's use the absolute log path we checked:
log_path = r"C:\Users\upender\.gemini\antigravity\brain\35dcc180-3af3-46fe-94d6-8f6c4e190996\.system_generated\tasks\task-467.log"

if not os.path.exists(log_path):
    print("Log file not found.")
    sys.exit(1)

with open(log_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
# Print any line that contains "RESPONSE" or "Error" or "api" (excluding static files)
for idx, line in enumerate(lines):
    line_str = line.strip()
    if any(k in line_str.lower() for k in ["api", "response", "error"]):
        if not any(static in line_str.lower() for static in [".js", ".css", ".png", ".jpg", "razorpay", "checkout"]):
            print(f"Line {idx+1}: {line_str}")
