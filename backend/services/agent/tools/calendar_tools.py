import os
from typing import Dict, Any
import logging

import httpx
import dateparser

from shared.settings import config

logger = logging.getLogger("agent.calendar_tools")

# dateparser settings used across all parsing calls
_DATEPARSER_SETTINGS = {
    "RETURN_AS_TIMEZONE_AWARE": False,
    "PREFER_DAY_OF_MONTH": "first",
    "DATE_ORDER": "DMY",  # prefer DD-MM-YYYY for ambiguous inputs
    "PREFER_DATES_FROM": "future",
}


def normalize_datetime(date_str: str, time_str: str) -> tuple[str, str]:
    """Normalize natural-language date/time to canonical ISO formats.

    Uses ``dateparser`` to handle the full range of LLM-produced strings:

    Date examples accepted:
      - "2026-03-13" / "13-03-2026" / "13/03/2026"
      - "March 13 2026" / "13 March 2026"
      - "March thirteen twenty twenty six" (fully spoken)
      - "Thirteenth of March twenty twenty six"

    Time examples accepted:
      - "04:15" / "4:15 AM" / "4:15AM"
      - "Five fifty five PM" / "5:55 PM" / "17:55"

    Args:
        date_str: Date string in any supported format.
        time_str: Time string in any supported format.

    Returns:
        ``(normalized_date, normalized_time)`` where
        - ``normalized_date`` is ``YYYY-MM-DD``
        - ``normalized_time`` is ``HH:MM`` (24-hour)

    Raises:
        ValueError: If the combined string cannot be parsed.
    """
    raw_date = (date_str or "").strip()
    raw_time = (time_str or "").strip()
    text = f"{raw_date} {raw_time}".strip()
    logger.debug(f"Attempting to parse datetime text: '{text}'")

    parsed = dateparser.parse(text, settings=_DATEPARSER_SETTINGS)

    if parsed is None:
        logger.error(
            "Datetime parse failed: raw_date='%s' raw_time='%s'",
            raw_date,
            raw_time,
        )
        raise ValueError(
            f"Unable to normalize date/time: date='{raw_date}' time='{raw_time}'"
        )

    normalized_date = parsed.strftime("%Y-%m-%d")
    normalized_time = parsed.strftime("%H:%M")
    logger.debug(
        "Parsed datetime: raw_date='%s' raw_time='%s' normalized='%s %s'",
        raw_date,
        raw_time,
        normalized_date,
        normalized_time,
    )
    logger.info(f"Normalized booking datetime → {normalized_date} {normalized_time}")
    return normalized_date, normalized_time


def _normalize_date_time(date: str, time: str) -> tuple[str, str]:
    """Backward-compatible wrapper around `normalize_datetime()`."""
    return normalize_datetime(date, time)


async def book_meeting(
    workspace_id: str,
    assistant_id: str,
    call_id: str,
    name: str,
    date: str,
    time: str,
    phone: str = "",
) -> Dict[str, Any]:
    """Call the Gateway to book a calendar meeting for this workspace.
    
    Normalizes date/time to canonical formats before sending to gateway.
    
    Args:
        workspace_id: Workspace identifier
        assistant_id: Assistant identifier
        call_id: Call identifier
        name: Attendee name
        date: Date in any supported format (see _normalize_date_time)
        time: Time in any supported format (see _normalize_date_time)
        phone: Optional phone number
    
    Returns:
        Response from gateway with booking confirmation
    
    Raises:
        ValueError: If date/time normalization fails
        httpx.HTTPStatusError: If gateway request fails
    """
    internal_key = os.getenv("INTERNAL_API_KEY", config.INTERNAL_API_KEY)
    base_url = os.getenv("GATEWAY_INTERNAL_URL", "http://gateway:8000")
    
    logger.debug("book_meeting raw datetime: date='%s' time='%s'", date, time)

    # Normalize date/time to canonical formats
    try:
        normalized_date, normalized_time = normalize_datetime(date, time)
    except ValueError as e:
        logger.error(
            "Failed to normalize date/time for booking: raw_date='%s' raw_time='%s' error='%s'",
            date,
            time,
            str(e),
        )
        raise
    
    logger.info(f"Booking meeting: {name} on {normalized_date} at {normalized_time}")
    
    payload = {
        "workspace_id": workspace_id,
        "assistant_id": assistant_id,
        "call_id": call_id,
        "name": name,
        "phone": phone or None,
        "date": normalized_date,
        "time": normalized_time,
    }

    logger.debug(f"Calendar booking payload: {payload}")

    async with httpx.AsyncClient(timeout=5.0) as client:
        # Canonical route is mounted under /api.
        resp = await client.post(
            f"{base_url}/api/calendar/book",
            json=payload,
            headers={"X-API-Key": internal_key},
        )
        # Backward compatibility fallback for older route wiring.
        if resp.status_code == 404:
            resp = await client.post(
                f"{base_url}/calendar/book",
                json=payload,
                headers={"X-API-Key": internal_key},
            )

        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Calendar booking successful: event_id={result.get('event_id')}")
        return result


async def execute_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an agent tool by name."""
    logger.info("Executing tool '%s' with args=%s", tool_name, args)

    if tool_name != "book_meeting":
        raise ValueError(f"Unsupported tool: {tool_name}")

    result = await book_meeting(
        workspace_id=args["workspace_id"],
        assistant_id=args["assistant_id"],
        call_id=args["call_id"],
        name=args["name"],
        date=args["date"],
        time=args["time"],
        phone=args.get("phone", ""),
    )
    logger.info(
        "Calendar booking successful: call_id=%s event_id=%s",
        args.get("call_id"),
        result.get("event_id"),
    )
    return result

