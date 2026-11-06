from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.admin import (
    AdminDocumentDetailResponse,
    AdminDocumentPage,
    AdminRoleUpdate,
    AdminStatusUpdate,
    AdminUserPage,
    AdminUserResponse,
    OwnershipTransferRequest,
    OwnershipTransferResponse,
)
from app.security.dependencies import require_admin
from app.services.admin_service import (
    get_document_detail,
    list_documents,
    list_users,
    set_user_active,
    set_user_role,
    transfer_document_ownership,
)


router = APIRouter(prefix="/api/admin", tags=["Administration"])


@router.get("/users", response_model=AdminUserPage)
def get_users(
    q: str | None = Query(default=None, max_length=100),
    role: str | None = Query(default=None, pattern="^(ADMIN|USER)$"),
    is_active: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return list_users(db, q, role, is_active, skip, limit)


@router.patch("/users/{user_id}/role", response_model=AdminUserResponse)
def update_user_role(
    user_id: UUID,
    data: AdminRoleUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return set_user_role(db, user_id, data.role, admin)


@router.patch("/users/{user_id}/status", response_model=AdminUserResponse)
def update_user_status(
    user_id: UUID,
    data: AdminStatusUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return set_user_active(db, user_id, data.is_active, admin)


@router.get("/documents", response_model=AdminDocumentPage)
def get_documents(
    q: str | None = Query(default=None, max_length=100),
    owner_email: str | None = Query(default=None, max_length=255),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return list_documents(db, q, owner_email, skip, limit)


@router.get(
    "/documents/{document_id}",
    response_model=AdminDocumentDetailResponse,
)
def get_document(
    document_id: UUID,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_document_detail(db, document_id)


@router.post(
    "/documents/{document_id}/transfer",
    response_model=OwnershipTransferResponse,
)
def transfer_ownership(
    document_id: UUID,
    data: OwnershipTransferRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return transfer_document_ownership(
        db,
        document_id,
        str(data.new_owner_email),
        admin,
    )
