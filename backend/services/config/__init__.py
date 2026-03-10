"""Config service package with lazy exports to avoid circular imports."""

from typing import Any

__all__ = [
    "AssistantService",
    "PhoneNumberService",
    "SipConfigService",
    "ToolService",
]


def __getattr__(name: str) -> Any:
    if name == "AssistantService":
        from services.config.assistant_service import AssistantService
        return AssistantService
    if name == "PhoneNumberService":
        from services.config.phone_sip_service import PhoneNumberService
        return PhoneNumberService
    if name == "SipConfigService":
        from services.config.phone_sip_service import SipConfigService
        return SipConfigService
    if name == "ToolService":
        from services.config.tool_service import ToolService
        return ToolService
    raise AttributeError(f"module 'services.config' has no attribute '{name}'")
