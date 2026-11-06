from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User

from app.security.dependencies import get_current_user

from app.schemas.permission import (
    ShareDocumentRequest,
    PermissionResponse
)

from app.services.permission_service import (
    share_document,
    list_document_permissions,
    revoke_permission
)


router = APIRouter(
    prefix="/api/permissions",
    tags=["Document Permissions"]
)


@router.post(
    "/documents/{document_id}/share",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED
)
def share(
    document_id: UUID,
    data: ShareDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    return share_document(
        document_id=document_id,
        email=str(data.email).lower(),
        owner=current_user,
        db=db
    )


@router.get(
    "/documents/{document_id}",
    response_model=list[PermissionResponse]
)
def get_permissions(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    return list_document_permissions(
        document_id=document_id,
        owner=current_user,
        db=db
    )


@router.delete("/{permission_id}")
def revoke(
    permission_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    return revoke_permission(
        permission_id=permission_id,
        owner=current_user,
        db=db
    )