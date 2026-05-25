import math
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class SubjectAttendance:
    subject_name: str
    conducted: int
    attended: int
    percentage: float  # Scraped percentage (often matches attended/conducted, but scraped from portal)

def calculate_bunks_or_attendance_required(
    attended: int, conducted: int, target_percentage: float = 75.0
) -> Dict[str, Any]:
    """
    Calculates current percentage, status, and how many classes can be bunked or must be attended.
    
    Formula Reference:
    - Bunks allowed (if percentage >= target_percentage):
      bunks = floor((attended - (target_rate * conducted)) / target_rate)
    - Classes to attend (if percentage < target_percentage):
      classes_to_attend = ceiling(((target_rate * conducted) - attended) / (1 - target_rate))
    """
    target_rate = target_percentage / 100.0
    
    # Handle edge case: No classes conducted yet
    if conducted <= 0:
        return {
            "current_percentage": 0.0,
            "status": "neutral",
            "classes_to_bunk": 0,
            "classes_to_attend": 0,
            "message": "No classes conducted yet."
        }
        
    current_percentage = (attended / conducted) * 100.0
    
    if current_percentage >= target_percentage:
        # User is safe, check how many classes they can bunk
        # Bunks allowed = floor((Attended - (target_rate * Conducted)) / target_rate)
        # Avoid division by zero (though target_rate is typically 0.75, which is > 0)
        if target_rate > 0:
            bunks_allowed = math.floor((attended - (target_rate * conducted)) / target_rate)
            classes_to_bunk = max(0, bunks_allowed)
        else:
            classes_to_bunk = 0
            
        return {
            "current_percentage": current_percentage,
            "status": "above",
            "classes_to_bunk": classes_to_bunk,
            "classes_to_attend": 0,
            "message": f"You can safely bunk {classes_to_bunk} more class{'es' if classes_to_bunk != 1 else ''}."
        }
    else:
        # User is short of attendance, check how many they must attend
        # Classes to attend = ceiling(((target_rate * Conducted) - Attended) / (1 - target_rate))
        # Avoid division by zero if target_rate is 1.0 (100%)
        if target_rate >= 1.0:
            # If target is 100%, and attended < conducted, you can never reach 100% since you already missed one.
            # We treat this as attending infinite classes, or we just return an impossible status.
            classes_to_attend = float('inf')
            msg = "Impossible to reach 100% attendance because classes have already been missed."
        else:
            required = math.ceil(((target_rate * conducted) - attended) / (1 - target_rate))
            classes_to_attend = max(1, required)
            msg = f"You must attend the next {classes_to_attend} consecutive class{'es' if classes_to_attend != 1 else ''}."
            
        return {
            "current_percentage": current_percentage,
            "status": "below",
            "classes_to_bunk": 0,
            "classes_to_attend": classes_to_attend,
            "message": msg
        }

def run_tests():
    """Runs a suite of self-contained unit tests to verify the math logic."""
    print("Running math logic verification tests...")
    
    # Test case 1: Above threshold (75%)
    # Attended = 15, Conducted = 16 (93.75%). Bunks allowed: 4.
    res = calculate_bunks_or_attendance_required(15, 16, 75.0)
    assert res["status"] == "above", f"Expected 'above', got {res['status']}"
    assert res["classes_to_bunk"] == 4, f"Expected 4, got {res['classes_to_bunk']}"
    print("[OK] Test case 1 passed (15/16 classes, 75% target)")

    # Test case 2: Above threshold (75%)
    # Attended = 15, Conducted = 17 (88.24%). Bunks allowed: 3.
    res = calculate_bunks_or_attendance_required(15, 17, 75.0)
    assert res["classes_to_bunk"] == 3, f"Expected 3, got {res['classes_to_bunk']}"
    print("[OK] Test case 2 passed (15/17 classes, 75% target)")

    # Test case 3: Below threshold (75%)
    # Attended = 10, Conducted = 20 (50%). Classes to attend: 20.
    res = calculate_bunks_or_attendance_required(10, 20, 75.0)
    assert res["status"] == "below", f"Expected 'below', got {res['status']}"
    assert res["classes_to_attend"] == 20, f"Expected 20, got {res['classes_to_attend']}"
    print("[OK] Test case 3 passed (10/20 classes, 75% target)")

    # Test case 4: Below threshold (75%)
    # Attended = 11, Conducted = 18 (61.11%). Classes to attend: 10.
    res = calculate_bunks_or_attendance_required(11, 18, 75.0)
    assert res["classes_to_attend"] == 10, f"Expected 10, got {res['classes_to_attend']}"
    print("[OK] Test case 4 passed (11/18 classes, 75% target)")

    # Test case 5: Boundary case - exactly at 75%
    # Attended = 15, Conducted = 20 (75%). Bunks allowed: 0.
    res = calculate_bunks_or_attendance_required(15, 20, 75.0)
    assert res["status"] == "above"
    assert res["classes_to_bunk"] == 0
    print("[OK] Test case 5 passed (15/20 classes, 75% target)")

    # Test case 6: Conducted is 0
    res = calculate_bunks_or_attendance_required(0, 0, 75.0)
    assert res["status"] == "neutral"
    assert res["classes_to_bunk"] == 0
    assert res["classes_to_attend"] == 0
    print("[OK] Test case 6 passed (0/0 classes)")

    print("All tests passed successfully!")

if __name__ == "__main__":
    run_tests()
