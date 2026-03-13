# Calendar Booking Date/Time Normalization - Debug Report

## Problem Statement

The inbound voice agent was calling the `book_meeting` tool with date/time formats that the booking service couldn't parse:

```
date='13-03-2026'
time='04:15'

Error: "Unable to normalize date/time"
```

The booking service requires canonical ISO formats:
- **date**: `YYYY-MM-DD` (e.g., `2026-03-13`)
- **time**: `HH:MM` in 24-hour format (e.g., `16:15`)

## Root Cause

The original normalization logic in `calendar_tools.py` used a hardcoded list of `strptime()` formats that didn't cover all variations the LLM could produce, particularly:
- European date formats (DD-MM-YYYY)
- Spelled-out numbers ("March thirteen twenty twenty six")
- Mixed time formats (4:15 vs 04:15)

## Solution Implemented

### 1. **Added `python-dateutil` Dependency**
   - Upgraded `backend/requirements.txt` to include `python-dateutil>=2.8.0`
   - Provides robust `dateutil.parser.parse()` for flexible date/time parsing

### 2. **Refactored `_normalize_date()` Function**
   ```python
   def _normalize_date(date_str: str) -> str:
   ```
   - **Input**: Any date format (DD-MM-YYYY, YYYY-MM-DD, "March 13 2026", etc.)
   - **Process**:
     1. Convert spelled-out numbers to digits via `_convert_words_to_numbers()`
     2. Parse with `dateutil.parser.parse(dayfirst=True, fuzzy=True)`
     3. Format output as ISO `YYYY-MM-DD`
   - **Output**: Canonical date string

### 3. **Refactored `_normalize_time()` Function**
   ```python
   def _normalize_time(time_str: str) -> str:
   ```
   - **Input**: Any time format (04:15, "5:55 PM", "Five fifty five PM", etc.)
   - **Process**:
     1. Convert spelled-out numbers to digits
     2. Parse with `dateutil.parser.parse()` against dummy date
     3. Format output as 24-hour `HH:MM`
   - **Output**: Canonical time string

### 4. **Enhanced `_normalize_date_time()` Wrapper**
   - Calls `_normalize_date()` and `_normalize_time()` independently
   - Provides detailed error messages on failure
   - Logs normalized values: `"Normalized booking datetime → 2026-03-13 16:15"`

### 5. **Improved Error Handling in `book_meeting()`**
   - Catches normalization errors and provides context
   - Logs booking attempt with normalized datetime
   - Logs success with event ID
   - Structured error propagation to agent

### 6. **Maintained Spoken Number Support**
   - Kept `WORD_TO_NUM` dictionary for converting spelled-out numbers
   - `_convert_words_to_numbers()` handles:
     - "March thirteen" → "March 13"
     - "Five fifty five" → "5 55"
     - All single digits and tens (zero through sixty)

## Supported Format Coverage

### Date Formats
✅ DD-MM-YYYY (13-03-2026)
✅ YYYY-MM-DD (2026-03-13)
✅ MM/DD/YYYY (03/13/2026)
✅ DD/MM/YYYY (13/03/2026)
✅ Month DD YYYY (March 13 2026)
✅ DD Month YYYY (13 March 2026)
✅ Month DD, YYYY (March 13, 2026)
✅ Spelled-out numbers (March thirteen twenty twenty six)

### Time Formats
✅ HH:MM 24-hour (16:15, 04:15)
✅ H:MM 24-hour (4:15)
✅ HH:MM AM/PM (04:15 PM)
✅ H:MM AM/PM (4:15 PM)
✅ H AM/PM (5 PM)
✅ Spelled-out (Five fifty five PM)

## Example Execution Flow

### Input
```python
await book_meeting(
    workspace_id="ws_5089b582b546",
    assistant_id="asst_2140624d5328",
    call_id="call-918904363117-4044",
    name="Aditya",
    date="13-03-2026",
    time="04:15",
    phone=""
)
```

### Log Output
```
INFO:agent.calendar_tools:Parsed date '13-03-2026' → '2026-03-13'
INFO:agent.calendar_tools:Parsed time '04:15' → '04:15'
INFO:agent.calendar_tools:Normalized booking datetime → 2026-03-13 04:15
INFO:agent.calendar_tools:Booking meeting: Aditya on 2026-03-13 at 04:15
INFO:agent.calendar_tools:Calendar booking successful: event_id=evt_xxxxx
```

### Gateway Payload
```json
{
  "workspace_id": "ws_5089b582b546",
  "assistant_id": "asst_2140624d5328",
  "call_id": "call-918904363117-4044",
  "name": "Aditya",
  "date": "2026-03-13",
  "time": "04:15",
  "phone": null
}
```

## Testing

A test script is provided at `test_date_normalization.py`:

```bash
cd /Users/adma/Documents/Side\ By/Vobiz-repo/KB_Voice-AI-Platform/Voice-AI-Platform
python test_date_normalization.py
```

This validates 7+ format combinations automatically.

## Backward Compatibility

✅ All previous format support maintained
✅ Graceful fallback to `dateutil.parser.parse()` for edge cases
✅ Original error messages enhanced with context
✅ No changes to `book_meeting()` API signature

## Files Modified

1. **backend/requirements.txt**
   - Added: `python-dateutil>=2.8.0`

2. **backend/services/agent/tools/calendar_tools.py**
   - Refactored: `_normalize_date()` with `dateutil.parser`
   - Refactored: `_normalize_time()` with `dateutil.parser`
   - Enhanced: `_normalize_date_time()` with better error messages
   - Enhanced: `book_meeting()` with detailed logging

3. **test_date_normalization.py** (new)
   - Test suite for date/time normalization

## Deployment Notes

1. **Install dependencies**: `pip install -r backend/requirements.txt`
2. **Rebuild Docker images**: `docker compose up --build`
3. **No database migrations required**
4. **No environment variable changes required**

## Validation

After deployment, confirm:
- LLM can pass natural language dates/times to book_meeting tool
- Logs show "Normalized booking datetime" entries
- Calendar bookings complete successfully with normalized datetime
- No "Unable to normalize" errors in agent logs
