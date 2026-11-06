from uuid import UUID
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, ConfigDict


class ShareDocumentRequest(BaseModel):
    email: EmailStr
    permission: Literal["VIEWER"] = "VIEWER"


class PermissionResponse(BaseModel):
    id: UUID
    document_id: UUID
    user_id: UUID
    permission: str
    granted_by: UUID
    created_at: datetime
    revoked_at: datetime | None
    recipient_email: EmailStr | None = None

    model_config = ConfigDict(from_attributes=True)