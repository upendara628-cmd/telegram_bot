import json
from collections import defaultdict

def calculate():
    with open("timetable_data.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    subject_stats = defaultdict(lambda: {"conducted": 0, "attended": 0})
    
    for entry in data:
        # Check if this is a completed class with attendance marked
        subject = entry.get("subject", {})
        sub_name = subject.get("name")
        sub_code = subject.get("subjectCode")
        
        if not sub_name:
            continue
            
        key = f"{sub_name} ({sub_code})"
        
        # Check if the class session was completed and had attendance marked
        is_completed = entry.get("completed", False)
        
        student_att = entry.get("studentAttendance")
        
        if is_completed and student_att:
            subject_stats[key]["conducted"] += 1
            # status represents whether student is present
            is_present = student_att.get("status", False)
            if is_present:
                subject_stats[key]["attended"] += 1
                
    print("=== SUBJECT-WISE ATTENDANCE CALCULATED FROM API ===")
    for sub, stats in subject_stats.items():
        cond = stats["conducted"]
        att = stats["attended"]
        pct = (att / cond * 100) if cond > 0 else 0
        print(f"{sub}:")
        print(f"  Conducted: {cond}")
        print(f"  Attended: {att}")
        print(f"  Percentage: {pct:.2f}%")
        print("-" * 40)

if __name__ == "__main__":
    calculate()
