from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.permission import DocumentPermission
from app.models.user import User
from app.services.audit_service import log_event


ADMIN_CHANGE_LOCK_KEY = 748292
ADMIN_DOCUMENT_HISTORY_ACTIONS = (
    "DOCUMENT_SHARED",
    "PERMISSION_REVOKED",
    "DOCUMENT_OWNERSHIP_TRANSFERRED",
)


def _lock_admin_changes(db: Session) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": ADMIN_CHANGE_LOCK_KEY},
    )


def list_users(
    db: Session,
    q: str | None,
    role: str | None,
    is_active: bool | None,
    skip: int,
    limit: int,
):
    query = db.query(User)
    if q:
        search_text = q.strip()
        if not search_text:
            raise HTTPException(
                status_code=422,
                detail="Search query must contain non-whitespace characters",
            )
        search = (
            search_text.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        query = query.filter(
            User.name.ilike(f"%{search}%", escape="\\")
            | User.email.ilike(f"%{search}%", escape="\\")
        )
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active.is_(is_active))

    return {
        "items": query.order_by(User.created_at.desc(), User.id).offset(skip).limit(limit).all(),
        "total": query.count(),
        "active_count": db.query(User).filter(User.is_active.is_(True)).count(),
        "admin_count": db.query(User).filter(User.role == "ADMIN").count(),
    }


def set_user_role(
    db: Session,
    target_user_id: UUID,
    role: str,
    actor: User,
):
    _lock_admin_changes(db)
    target = db.get(User, target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role == role:
        return target

    if target.role == "ADMIN" and target.is_active and role == "USER":
        active_admins = db.query(User).filter(
            User.role == "ADMIN",
            User.is_active.is_(True),
        ).count()
        if active_admins <= 1:
            raise HTTPException(
                status_code=409,
                detail="The last active administrator cannot be demoted",
            )

    previous_role = target.role
    target.role = role
    action = (
        "USER_PROMOTED_TO_ADMIN"
        if role == "ADMIN"
        else "ADMIN_DEMOTED_TO_USER"
    )
    log_event(
        db=db,
        user_id=actor.id,
        document_id=None,
        action=action,
        details={
            "target_user_id": str(target.id),
            "target_email": target.email,
            "previous_role": previous_role,
            "new_role": role,
        },
    )
    return target


def set_user_active(
    db: Session,
    target_user_id: UUID,
    is_active: bool,
    actor: User,
):
    _lock_admin_changes(db)
    target = db.get(User, target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == actor.id and not is_active:
        raise HTTPException(
            status_code=409,
            detail="You cannot deactivate your own account",
        )
    if target.is_active == is_active:
        return target

    if target.role == "ADMIN" and target.is_active and not is_active:
        active_admins = db.query(User).filter(
            User.role == "ADMIN",
            User.is_active.is_(True),
        ).count()
        if active_admins <= 1:
            raise HTTPException(
                status_code=409,
                detail="The last active administrator cannot be deactivated",
            )

    target.is_active = is_active
    log_event(
        db=db,
        user_id=actor.id,
        document_id=None,
        action="USER_ACTIVATED" if is_active else "USER_DEACTIVATED",
        details={
            "target_user_id": str(target.id),
            "target_email": target.email,
            "is_active": is_active,
        },
    )
    return target


def _document_response(document: Document, owner: User, active_viewer_count: int):
    return {
        "id": document.id,
        "filename": document.filename,
        "content_type": document.content_type,
        "file_size": document.file_size,
        "created_at": document.created_at,
        "owner_id": owner.id,
        "owner_name": owner.name,
        "owner_email": owner.email,
        "is_deleted": document.is_deleted,
        "active_viewer_count": active_viewer_count,
    }


def list_documents(
    db: Session,
    q: str | None,
    owner_email: str | None,
    skip: int,
    limit: int,
):
    query = db.query(Document, User).join(User, Document.owner_id == User.id)
    if q:
        search_text = q.strip()
        if not search_text:
            raise HTTPException(
                status_code=422,
                detail="Search query must contain non-whitespace characters",
            )
        search = (
            search_text.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        query = query.filter(Document.filename.ilike(f"%{search}%", escape="\\"))
    if owner_email:
        owner_search = (
            owner_email.strip()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        if not owner_search:
            raise HTTPException(
                status_code=422,
                detail="Owner search must contain non-whitespace characters",
            )
        query = query.filter(User.email.ilike(f"%{owner_search}%", escape="\\"))

    total = query.count()
    rows = query.order_by(
        Document.created_at.desc(),
        Document.id,
    ).offset(skip).limit(limit).all()
    document_ids = [document.id for document, _owner in rows]
    viewer_counts = {}
    if document_ids:
        viewer_counts = dict(
            db.query(
                DocumentPermission.document_id,
                func.count(DocumentPermission.id),
            ).filter(
                DocumentPermission.document_id.in_(document_ids),
                DocumentPermission.revoked_at.is_(None),
            ).group_by(DocumentPermission.document_id).all()
        )

    return {
        "items": [
            _document_response(
                document,
                owner,
                viewer_counts.get(document.id, 0),
            )
            for document, owner in rows
        ],
        "total": total,
    }


def get_document_detail(db: Session, document_id: UUID):
    row = db.query(Document, User).join(
        User,
        Document.owner_id == User.id,
    ).filter(Document.id == document_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")

    document, owner = row
    active_viewer_count = db.query(DocumentPermission).filter(
        DocumentPermission.document_id == document.id,
        DocumentPermission.revoked_at.is_(None),
    ).count()

    permission_rows = db.query(
        DocumentPermission,
        User,
    ).join(
        User,
        DocumentPermission.user_id == User.id,
    ).filter(
        DocumentPermission.document_id == document.id,
    ).order_by(
        DocumentPermission.created_at.desc(),
    ).all()
    history_rows = db.query(AuditLog).filter(
        AuditLog.document_id == document.id,
        AuditLog.action.in_(ADMIN_DOCUMENT_HISTORY_ACTIONS),
    ).order_by(AuditLog.timestamp.desc()).all()

    return {
        "document": _document_response(
            document,
            owner,
            active_viewer_count,
        ),
        "permissions": [
            {
                "id": permission.id,
                "user_id": recipient.id,
                "recipient_name": recipient.name,
                "recipient_email": recipient.email,
                "permission": permission.permission,
                "granted_by": permission.granted_by,
                "created_at": permission.created_at,
                "revoked_at": permission.revoked_at,
            }
            for permission, recipient in permission_rows
        ],
        "sharing_history": [
            {
                "id": event.id,
                "user_id": event.user_id,
                "action": event.action,
                "details": event.details,
                "timestamp": event.timestamp,
            }
            for event in history_rows
        ],
    }


def transfer_document_ownership(
    db: Session,
    document_id: UUID,
    new_owner_email: str,
    actor: User,
):
    """Transfer ownership, retaining viewer history and revoking the new owner's viewer grant."""
    document = db.query(Document).filter(
        Document.id == document_id,
    ).with_for_update().first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.is_deleted:
        raise HTTPException(
            status_code=409,
            detail="Deleted documents cannot be transferred",
        )

    new_owner = db.query(User).filter(
        func.lower(User.email) == new_owner_email.lower(),
        User.is_active.is_(True),
    ).first()
    if new_owner is None:
        raise HTTPException(
            status_code=404,
            detail="New owner not found or inactive",
        )
    if new_owner.id == document.owner_id:
        raise HTTPException(
            status_code=409,
            detail="The selected user is already the document owner",
        )

    previous_owner_id = document.owner_id
    previous_owner = db.get(User, previous_owner_id)
    now = datetime.now(timezone.utc)
    recipient_permission = db.query(DocumentPermission).filter(
        DocumentPermission.document_id == document.id,
        DocumentPermission.user_id == new_owner.id,
        DocumentPermission.revoked_at.is_(None),
    ).first()
    if recipient_permission is not None:
        recipient_permission.revoked_at = now

    document.owner_id = new_owner.id
    log_event(
        db=db,
        user_id=actor.id,
        document_id=document.id,
        action="DOCUMENT_OWNERSHIP_TRANSFERRED",
        details={
            "previous_owner_id": str(previous_owner_id),
            "previous_owner_email": previous_owner.email if previous_owner else None,
            "new_owner_id": str(new_owner.id),
            "new_owner_email": new_owner.email,
            "new_owner_viewer_permission_revoked": (
                recipient_permission is not None
            ),
        },
    )
    return {
        "message": "Document ownership transferred successfully",
        "document_id": document.id,
        "previous_owner_id": previous_owner_id,
        "new_owner_id": new_owner.id,
    }
