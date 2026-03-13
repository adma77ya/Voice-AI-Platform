#!/usr/bin/env python3
"""Test script for date/time normalization in calendar_tools.py"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from services.agent.tools.calendar_tools import _normalize_date_time


def test_date_time_normalization():
    """Test various date/time format combinations."""
    
    test_cases = [
        # (date_input, time_input, expected_date, expected_time, description)
        ("13-03-2026", "04:15", "2026-03-13", "04:15", "DD-MM-YYYY with 24-hour time"),
        ("2026-03-13", "04:15", "2026-03-13", "04:15", "YYYY-MM-DD with 24-hour time"),
        ("March 13 2026", "5:55 PM", "2026-03-13", "17:55", "Long date format with 12-hour time"),
        ("13 March 2026", "4:15 PM", "2026-03-13", "16:15", "European date format with 12-hour time"),
        ("March thirteen twenty twenty six", "Five fifty five PM", "2026-03-13", "17:55", "Spelled-out date and time"),
        ("13/03/2026", "16:15", "2026-03-13", "16:15", "Slash format DD/MM/YYYY"),
        ("03/13/2026", "5 PM", "2026-03-13", "17:00", "US format MM/DD/YYYY with hour only"),
    ]
    
    print("Testing date/time normalization...\n")
    passed = 0
    failed = 0
    
    for date_in, time_in, expected_date, expected_time, description in test_cases:
        try:
            normalized_date, normalized_time = _normalize_date_time(date_in, time_in)
            
            # Check results
            date_match = normalized_date == expected_date
            time_match = normalized_time == expected_time
            
            if date_match and time_match:
                status = "✓ PASS"
                passed += 1
            else:
                status = "✗ FAIL"
                failed += 1
                if not date_match:
                    print(f"  Date mismatch: expected {expected_date}, got {normalized_date}")
                if not time_match:
                    print(f"  Time mismatch: expected {expected_time}, got {normalized_time}")
            
            print(f"{status}: {description}")
            print(f"  Input: date='{date_in}', time='{time_in}'")
            print(f"  Output: {normalized_date} {normalized_time}\n")
            
        except Exception as e:
            print(f"✗ ERROR: {description}")
            print(f"  Input: date='{date_in}', time='{time_in}'")
            print(f"  Error: {str(e)}\n")
            failed += 1
    
    print("-" * 60)
    print(f"Results: {passed} passed, {failed} failed\n")
    
    return failed == 0


if __name__ == "__main__":
    success = test_date_time_normalization()
    sys.exit(0 if success else 1)
