from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.document import Document

from app.security.dependencies import (
    get_current_user,
    require_admin
)

from app.schemas.audit import AuditLogResponse
from app.services.audit_service import verify_audit_chain


router = APIRouter(
    prefix="/api/audit",
    tags=["Audit Logs"]
)


@router.get(
    "/all",
    response_model=list[AuditLogResponse]
)
def get_all_audit_logs(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    return db.query(AuditLog).order_by(
        AuditLog.timestamp.desc()
    ).all()


@router.get(
    "/documents/{document_id}",
    response_model=list[AuditLogResponse]
)
def get_document_audit_logs(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.owner_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    return db.query(AuditLog).filter(
        AuditLog.document_id == document_id
    ).order_by(
        AuditLog.timestamp.desc()
    ).all()


@router.get("/verify")
def verify_audit_logs(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    return verify_audit_chain(db)