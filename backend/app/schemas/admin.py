from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class AdminUserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: Literal["ADMIN", "USER"]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserPage(BaseModel):
    items: list[AdminUserResponse]
    total: int
    active_count: int
    admin_count: int


class AdminRoleUpdate(BaseModel):
    role: Literal["ADMIN", "USER"]


class AdminStatusUpdate(BaseModel):
    is_active: bool


class AdminDocumentResponse(BaseModel):
    id: UUID
    filename: str
    content_type: str
    file_size: int
    created_at: datetime
    owner_id: UUID
    owner_name: str
    owner_email: EmailStr
    is_deleted: bool
    active_viewer_count: int


class AdminDocumentPage(BaseModel):
    items: list[AdminDocumentResponse]
    total: int


class AdminPermissionResponse(BaseModel):
    id: UUID
    user_id: UUID
    recipient_name: str
    recipient_email: EmailStr
    permission: str
    granted_by: UUID
    created_at: datetime
    revoked_at: datetime | None


class AdminDocumentHistoryEvent(BaseModel):
    id: UUID
    user_id: UUID | None
    action: str
    details: dict | None
    timestamp: datetime


class AdminDocumentDetailResponse(BaseModel):
    document: AdminDocumentResponse
    permissions: list[AdminPermissionResponse]
    sharing_history: list[AdminDocumentHistoryEvent]


class OwnershipTransferRequest(BaseModel):
    new_owner_email: EmailStr


class OwnershipTransferResponse(BaseModel):
    message: str
    document_id: UUID
    previous_owner_id: UUID
    new_owner_id: UUID
