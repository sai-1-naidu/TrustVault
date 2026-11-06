from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):

    id: UUID
    user_id: UUID | None
    document_id: UUID | None
    action: str
    ip_address: str | None
    details: dict | None
    previous_hash: str | None
    event_hash: str
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)