from datetime import datetime, timezone

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.user import User
from app.models.document import Document
from app.models.permission import DocumentPermission

from app.services.audit_service import log_event


def share_document(
    document_id,
    email,
    owner: User,
    db: Session
):

    # 1. Verify document ownership
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.owner_id == owner.id,
        Document.is_deleted.is_(False)
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    # 2. Find recipient
    recipient = db.query(User).filter(
        User.email == email.lower(),
        User.is_active.is_(True)
    ).first()

    if not recipient:
        raise HTTPException(
            status_code=404,
            detail="Recipient not found or inactive"
        )

    # 3. Prevent sharing with yourself
    if recipient.id == owner.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot share a document with yourself"
        )

    # 4. Check existing permission
    existing = db.query(DocumentPermission).filter(
        DocumentPermission.document_id == document_id,
        DocumentPermission.user_id == recipient.id
    ).first()

    if existing:

        if existing.revoked_at is None:
            raise HTTPException(
                status_code=409,
                detail="Document is already shared with this user"
            )

        # Reactivate previously revoked permission
        existing.permission = "VIEWER"
        existing.granted_by = owner.id
        existing.created_at = datetime.now(timezone.utc)
        existing.revoked_at = None

        try:
            db.commit()
            db.refresh(existing)

            # Record re-sharing activity
            log_event(
                db=db,
                user_id=owner.id,
                document_id=document_id,
                action="DOCUMENT_SHARED",
                details={
                    "recipient_id": str(recipient.id),
                    "permission": "VIEWER",
                    "operation": "REACTIVATED"
                }
            )

            return existing

        except Exception:
            db.rollback()
            raise

    # 5. Create new permission
    permission = DocumentPermission(
        document_id=document_id,
        user_id=recipient.id,
        permission="VIEWER",
        granted_by=owner.id
    )

    db.add(permission)

    try:
        db.commit()
        db.refresh(permission)

        # Record sharing activity
        log_event(
            db=db,
            user_id=owner.id,
            document_id=document_id,
            action="DOCUMENT_SHARED",
            details={
                "recipient_id": str(recipient.id),
                "permission": "VIEWER",
                "operation": "CREATED"
            }
        )

        return permission

    except Exception:
        db.rollback()
        raise


def list_document_permissions(
    document_id,
    owner: User,
    db: Session
):

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.owner_id == owner.id,
        Document.is_deleted.is_(False)
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    permissions = db.query(
        DocumentPermission,
        User.email
    ).join(
        User,
        DocumentPermission.user_id == User.id
    ).filter(
        DocumentPermission.document_id == document_id
    ).all()

    return [
        {
            "id": permission.id,
            "document_id": permission.document_id,
            "user_id": permission.user_id,
            "permission": permission.permission,
            "granted_by": permission.granted_by,
            "created_at": permission.created_at,
            "revoked_at": permission.revoked_at,
            "recipient_email": email
        }
        for permission, email in permissions
    ]


def revoke_permission(
    permission_id,
    owner: User,
    db: Session
):

    permission = db.query(DocumentPermission).join(
        Document,
        DocumentPermission.document_id == Document.id
    ).filter(
        DocumentPermission.id == permission_id,
        Document.owner_id == owner.id,
        Document.is_deleted.is_(False)
    ).first()

    if not permission:
        raise HTTPException(
            status_code=404,
            detail="Permission not found"
        )

    if permission.revoked_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Permission is already revoked"
        )

    # Capture values before committing
    document_id = permission.document_id
    recipient_id = permission.user_id

    permission.revoked_at = datetime.now(timezone.utc)

    try:
        db.commit()

        # Record revocation activity
        log_event(
            db=db,
            user_id=owner.id,
            document_id=document_id,
            action="PERMISSION_REVOKED",
            details={
                "permission_id": str(permission_id),
                "recipient_id": str(recipient_id)
            }
        )

        return {
            "message": "Access revoked successfully",
            "permission_id": str(permission_id)
        }

    except Exception:
        db.rollback()
        raise