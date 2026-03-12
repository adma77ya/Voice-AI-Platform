import logging
from datetime import datetime, timezone
from typing import Optional

from shared.database.connection import get_database
from shared.database.models import WorkspaceCalendar
from shared.security.crypto import encrypt_secret, decrypt_secret

logger = logging.getLogger("workspace_calendar_service")


class WorkspaceCalendarService:
    """Service for managing workspace-scoped calendar integrations."""

    COLLECTION = "workspace_calendars"

    @classmethod
    async def _collection(cls):
        db = get_database()
        coll = db[cls.COLLECTION]
        # Ensure index exists (idempotent)
        try:
            await coll.create_index(
                [("workspace_id", 1), ("provider", 1)],
                unique=True,
                name="workspace_provider_unique",
            )
        except Exception as e:
            logger.debug(f"WorkspaceCalendar index creation skipped/failed: {e}")
        return coll

    @classmethod
    async def upsert_google_calendar(
        cls,
        workspace_id: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        calendar_id: str = "primary",
    ) -> WorkspaceCalendar:
        """Create or update a Google Calendar connection for a workspace."""
        coll = await cls._collection()

        now = datetime.now(timezone.utc)
        enc_access = encrypt_secret(access_token)
        enc_refresh = encrypt_secret(refresh_token) if refresh_token else None

        existing = await coll.find_one({"workspace_id": workspace_id, "provider": "google"})
        if existing:
            # Preserve existing refresh token if Google does not send a new one.
            if not enc_refresh:
                enc_refresh = existing.get("refresh_token_encrypted")

        doc = {
            "workspace_id": workspace_id,
            "provider": "google",
            "access_token_encrypted": enc_access,
            "refresh_token_encrypted": enc_refresh,
            "calendar_id": calendar_id,
            "updated_at": now,
        }
        if not existing:
            doc["created_at"] = now

        await coll.update_one(
            {"workspace_id": workspace_id, "provider": "google"},
            {"$set": doc},
            upsert=True,
        )

        stored = await coll.find_one({"workspace_id": workspace_id, "provider": "google"})
        return WorkspaceCalendar.from_dict(stored)

    @classmethod
    async def get_google_calendar(
        cls, workspace_id: str, decrypt: bool = False
    ) -> Optional[dict]:
        """Get Google Calendar connection for a workspace."""
        coll = await cls._collection()
        doc = await coll.find_one({"workspace_id": workspace_id, "provider": "google"})
        if not doc:
            return None

        if not decrypt:
            return doc

        access_token = decrypt_secret(doc.get("access_token_encrypted"))
        refresh_token = decrypt_secret(doc.get("refresh_token_encrypted"))
        return {
            "workspace_id": doc["workspace_id"],
            "provider": doc["provider"],
            "access_token": access_token,
            "refresh_token": refresh_token,
            "calendar_id": doc.get("calendar_id", "primary"),
        }

    @classmethod
    async def update_google_access_token(cls, workspace_id: str, access_token: str) -> None:
        """Update only the access token for a workspace calendar."""
        coll = await cls._collection()
        enc_access = encrypt_secret(access_token)
        now = datetime.now(timezone.utc)
        await coll.update_one(
            {"workspace_id": workspace_id, "provider": "google"},
            {"$set": {"access_token_encrypted": enc_access, "updated_at": now}},
        )

