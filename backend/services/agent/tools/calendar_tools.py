import os
from typing import Dict, Any

import httpx

from shared.settings import config


async def book_meeting(
    workspace_id: str,
    assistant_id: str,
    call_id: str,
    name: str,
    date: str,
    time: str,
    phone: str = "",
) -> Dict[str, Any]:
    """Call the Gateway to book a calendar meeting for this workspace."""
    internal_key = os.getenv("INTERNAL_API_KEY", config.INTERNAL_API_KEY)
    base_url = os.getenv("GATEWAY_INTERNAL_URL", "http://gateway:8000")

    payload = {
        "workspace_id": workspace_id,
        "assistant_id": assistant_id,
        "call_id": call_id,
        "name": name,
        "phone": phone or None,
        "date": date,
        "time": time,
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            f"{base_url}/calendar/book",
            json=payload,
            headers={"X-API-Key": internal_key},
        )
        resp.raise_for_status()
        return resp.json()

