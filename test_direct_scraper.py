from scraper import fetch_portal_data
from bot import format_report

def main():
    try:
        print("Testing fetch_portal_data('default') directly...")
        results = fetch_portal_data("default")
        
        print("\n--- TIMETABLE ---")
        if results["timetable"]:
            for t in results["timetable"]:
                print(t)
        else:
            print("No classes scheduled for today.")
            
        print("\n--- ATTENDANCE & BUNK STATS ---")
        for item in results["attendance"]:
            print(f"\nSubject: {item['subject']}")
            print(f"  Attendance: {item['percentage']:.2f}% ({item['attended']}/{item['conducted']})")
            print(f"  Status: {item['bunk_info']['message']}")
            
        # Try formatting the full report using bot's format_report function
        report = format_report(results)
        print("\n=== FORMATTED BOT REPORT ===")
        print(report)
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
