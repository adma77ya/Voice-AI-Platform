"""Inbound call handler endpoint for SIP/LiveKit events."""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared.database.models import CreateCallRequest
from services.config.phone_sip_service import PhoneNumberService
from services.config.assistant_service import AssistantService
from services.analytics.call_service import CallService

logger = logging.getLogger("api.inbound-calls")
router = APIRouter()


class InboundCallRequest(BaseModel):
    """Inbound webhook payload from SIP provider or LiveKit."""
    from_number: str
    to_number: str
    sip_trunk_id: str


@router.post("/inbound-call")
async def inbound_call(request: InboundCallRequest):
    """Create inbound call record and dispatch agent via outbound-equivalent pipeline."""
    logger.info("INBOUND CALL RECEIVED: from=%s to=%s sip_trunk_id=%s", request.from_number, request.to_number, request.sip_trunk_id)

    assistant = await PhoneNumberService.get_assistant_by_number(request.to_number)
    if not assistant:
        raise HTTPException(status_code=404, detail="No assistant mapped to inbound number")

    mapped_trunk_id = assistant.get("inbound_trunk_id")
    if mapped_trunk_id and request.sip_trunk_id and mapped_trunk_id != request.sip_trunk_id:
        raise HTTPException(status_code=400, detail="SIP trunk does not match inbound number mapping")

    assistant_id = assistant.get("assistant_id")
    workspace_id: Optional[str] = assistant.get("workspace_id")
    if not assistant_id:
        raise HTTPException(status_code=400, detail="Inbound number mapping is missing assistant_id")

    assistant_config = await AssistantService.get_assistant_for_call(assistant_id)
    if not assistant_config:
        raise HTTPException(status_code=404, detail="Assistant config not found or inactive")

    voice = assistant_config.get("voice") or assistant.get("voice") or {}

    logger.info(
        "INBOUND assistant resolved: assistant_id=%s workspace_id=%s voice_mode=%s",
        assistant_id,
        workspace_id,
        voice.get("mode") or assistant.get("voice_mode"),
    )

    call_request = CreateCallRequest(
        phone_number=request.from_number,
        from_number=request.to_number,
        assistant_id=assistant_id,
        instructions=assistant_config.get("instructions") or assistant.get("instructions"),
        metadata={
            "is_inbound": True,
            "direction": "inbound",
            "phone_number": request.from_number,
            "from_number": request.from_number,
            "to_number": request.to_number,
            "sip_trunk_id": request.sip_trunk_id,
            "assistant_id": assistant_id,
            "workspace_id": workspace_id,
            "instructions": assistant_config.get("instructions") or assistant.get("instructions"),
            "first_message": assistant_config.get("first_message") or assistant.get("first_message"),
            "temperature": assistant_config.get("temperature") or assistant.get("temperature"),
            "voice": voice,
            "voice_mode": voice.get("mode") or assistant.get("voice_mode"),
            "voice_provider": voice.get("llm_provider") if (voice.get("mode") or "pipeline") == "pipeline" else voice.get("realtime_provider"),
            "voice_model": voice.get("llm_model") if (voice.get("mode") or "pipeline") == "pipeline" else voice.get("realtime_model"),
        },
    )

    call = await CallService.create_call(call_request, workspace_id=workspace_id, auto_dispatch=False)
    logger.info("INBOUND call created: call_id=%s", call.call_id)

    await CallService._dispatch_agent(
        call,
        assistant_config={
            "assistant_id": assistant_id,
            "workspace_id": workspace_id,
            "instructions": assistant_config.get("instructions") or assistant.get("instructions"),
            "first_message": assistant_config.get("first_message") or assistant.get("first_message"),
            "temperature": assistant_config.get("temperature") or assistant.get("temperature"),
            "voice": voice,
        },
        sip_trunk_id=request.sip_trunk_id,
    )

    logger.info("INBOUND agent dispatched: call_id=%s", call.call_id)
    logger.info("INBOUND room created: room=%s", call.room_name)

    return {
        "status": "ok",
        "message": "Inbound call accepted",
        "call_id": call.call_id,
        "room_name": call.room_name,
        "assistant_id": assistant_id,
        "workspace_id": workspace_id,
    }
