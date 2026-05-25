import os
import sys
import json
import argparse
from scraper import parse_timetable, parse_attendance, scrape_portal, AuthenticationRequiredError

# Create a mock Playwright page environment for unit tests
class MockElement:
    def __init__(self, text, tag_name="div", attributes=None):
        self._text = text
        self.tag_name = tag_name
        self.attributes = attributes or {}
        
    def inner_text(self):
        return self._text
        
    def query_selector_all(self, selector):
        # Extremely simplified query selector for mock testing
        if selector == "td" or selector == "td, th" or selector == "th":
            if "|" in self._text:
                return [MockElement(t.strip()) for t in self._text.split("|")]
            return [MockElement(self._text)]
        return []

class MockPage:
    def __init__(self, html_content, url="https://mock.portal.com"):
        self.html_content = html_content
        self.url = url
        
    def wait_for_timeout(self, ms):
        pass
        
    def query_selector_all(self, selector):
        # Mock finding tables and rows based on selectors
        if "table" in selector:
            # Return our mock tables
            return [MockElement("Header 1 | Header 2", tag_name="table")]
        return []
        
    def inner_text(self, selector):
        if selector == "body":
            return self.html_content
        return ""

def run_mock_tests():
    print("="*60)
    print("RUNNING MOCK HTML PARSING TESTS")
    print("="*60)
    
    # We will import BeautifulSoup or parse manually. Since we wrote scraper.py to use Playwright's Page and ElementHandle,
    # we'll test by mocking a page. But to make it even simpler, let's verify our custom row parser:
    from scraper import parse_attendance_row
    
    print("\nTesting parse_attendance_row heuristics:")
    
    # Test case 1: Standard row with percentages
    row_text = "Data Structures | 20 | 18 | 90%"
    cells = ["Data Structures", "20", "18", "90%"]
    sub, cond, att, pct = parse_attendance_row(row_text, cells)
    print(f"Parsed Row 1: Sub={sub}, Cond={cond}, Att={att}, Pct={pct}%")
    assert sub == "Data Structures"
    assert cond == 20
    assert att == 18
    assert pct == 90.0
    print("[OK] Standard percentage row parsed successfully.")
    
    # Test case 2: Row with numeric cells and label format
    row_text = "Subject: Discrete Mathematics Conducted: 16 Attended: 11"
    cells = ["Discrete Mathematics", "Conducted: 16", "Attended: 11", "68%"]
    sub, cond, att, pct = parse_attendance_row(row_text, cells)
    print(f"Parsed Row 2: Sub={sub}, Cond={cond}, Att={att}, Pct={pct}%")
    assert "Discrete Mathematics" in sub
    assert cond == 16
    assert att == 11
    print("[OK] Label format row parsed successfully.")

    # Test case 3: Row with code prefix and no percent sign
    row_text = "CS301 Object Oriented Programming 24 18"
    cells = ["CS301 Object Oriented Programming", "24", "18"]
    sub, cond, att, pct = parse_attendance_row(row_text, cells)
    print(f"Parsed Row 3: Sub={sub}, Cond={cond}, Att={att}, Pct={pct}%")
    assert "Object Oriented Programming" in sub
    assert cond == 24
    assert att == 18
    print("[OK] Code prefix and implicit percent row parsed successfully.")

    print("\nMock tests completed successfully!")
    print("="*60)

def run_live_test(headless=True):
    print("="*60)
    print("RUNNING LIVE SCRAPER TEST")
    print("="*60)
    
    try:
        results = scrape_portal(headless=headless)
        
        print("\nSCRAPING RESULTS:")
        print("\n--- TIMETABLE ---")
        if results["timetable"]:
            for entry in results["timetable"]:
                print(f"- {entry}")
        else:
            print("No timetable slots found (or day is empty).")
            
        print("\n--- ATTENDANCE & BUNK ANALYSIS ---")
        if results["attendance"]:
            for item in results["attendance"]:
                bi = item["bunk_info"]
                print(f"Subject: {item['subject']}")
                print(f"  Conducted: {item['conducted']}, Attended: {item['attended']}, Percentage: {item['percentage']:.2f}%")
                print(f"  Bunk Info: {bi['message']}")
                print("-" * 30)
        else:
            print("No attendance entries found.")
            
    except AuthenticationRequiredError as e:
        print("\n[ERROR] Authentication required.")
        print(e)
        print("\nPlease run the login script first to establish a session:")
        print("  python login.py")
    except Exception as e:
        print(f"\n[ERROR] Scraping failed due to unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test scraper for CampX Bot.")
    parser.add_argument("--mock", action="store_true", help="Run offline parsing tests on mock patterns.")
    parser.add_argument("--live", action="store_true", help="Run live scraper against CampX portal.")
    parser.add_argument("--headful", action="store_true", help="Run live scraper in headful mode (visible browser).")
    
    args = parser.parse_args()
    
    # If no arguments provided, run mock tests and then try live headless
    if not args.mock and not args.live:
        run_mock_tests()
        print("\nRunning live test (headless)...")
        run_live_test(headless=True)
    elif args.mock:
        run_mock_tests()
    elif args.live:
        run_live_test(headless=not args.headful)
