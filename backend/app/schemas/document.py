from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):

    id: UUID
    filename: str
    content_type: str
    file_size: int
    file_hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)