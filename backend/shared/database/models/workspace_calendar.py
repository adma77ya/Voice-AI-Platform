from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel


class WorkspaceCalendar(BaseModel):
    """Workspace-scoped calendar integration (currently Google only)."""

    workspace_id: str
    provider: str = "google"
    access_token_encrypted: str
    refresh_token_encrypted: Optional[str] = None
    calendar_id: str = "primary"
    created_at: datetime
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        data = self.model_dump()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "WorkspaceCalendar":
        return cls(**data)

