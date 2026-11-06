from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User

from app.security.dependencies import get_current_user

from app.services.document_service import (
    resolve_storage_path,
    save_document,
)

from app.schemas.document import DocumentResponse

from uuid import UUID

from fastapi import HTTPException, Query

from fastapi.responses import FileResponse

from app.models.document import Document

from app.models.permission import DocumentPermission

import hashlib

from fastapi import Request

from app.services.audit_service import log_event



router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"]
)

@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=201
)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    document = await save_document(
        file=file,
        owner_id=current_user.id,
        db=db
    )

    log_event(
        db=db,
        user_id=current_user.id,
        document_id=document.id,
        action="DOCUMENT_UPLOADED",
        details={
            "filename": document.filename,
            "file_size": document.file_size
        },
        ip_address=(
            request.client.host if request.client else None
        )
    )

    return document
@router.get("/", response_model=list[DocumentResponse])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    return db.query(Document).filter(
        Document.owner_id == current_user.id,
        Document.is_deleted.is_(False)
    ).order_by(
        Document.created_at.desc()
    ).all()

@router.get("/search", response_model=list[DocumentResponse])
def search_documents(
    q: str = Query(..., min_length=1, max_length=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = q.strip()
    if not query:
        raise HTTPException(
            status_code=422,
            detail="Search query must contain non-whitespace characters",
        )
    escaped_query = (
        query.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )

    documents = db.query(Document).filter(
        Document.owner_id == current_user.id,
        Document.is_deleted.is_(False),
        Document.filename.ilike(f"%{escaped_query}%", escape="\\")
    ).order_by(
        Document.created_at.desc()
    ).all()

    return documents
@router.get(
    "/shared-with-me",
    response_model=list[DocumentResponse]
)
def get_shared_documents(
    q: str | None = Query(default=None, max_length=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Return documents actively shared with the logged-in user.
    """

    query = db.query(Document).join(
        DocumentPermission,
        DocumentPermission.document_id == Document.id
    ).filter(
        DocumentPermission.user_id == current_user.id,
        DocumentPermission.revoked_at.is_(None),
        Document.is_deleted.is_(False)
    )

    if q is not None:
        search_text = q.strip()
        if not search_text:
            raise HTTPException(
                status_code=422,
                detail="Search query must contain non-whitespace characters",
            )
        escaped_query = (
            search_text.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        query = query.filter(
            Document.filename.ilike(
                f"%{escaped_query}%",
                escape="\\",
            )
        )

    return query.order_by(Document.created_at.desc()).all()

def get_owned_document(
    document_id: UUID,
    current_user: User,
    db: Session
):

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.owner_id == current_user.id,
        Document.is_deleted == False
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    return document
def get_accessible_document(
    document_id: UUID,
    current_user: User,
    db: Session
):
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.is_deleted == False
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    # Document owner has access.
    if document.owner_id == current_user.id:
        return document

    # Check active sharing permission.
    permission = db.query(DocumentPermission).filter(
        DocumentPermission.document_id == document_id,
        DocumentPermission.user_id == current_user.id,
        DocumentPermission.revoked_at.is_(None)
    ).first()

    if not permission:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this document"
        )

    return document

@router.get(
    "/{document_id}",
    response_model=DocumentResponse
)
def get_document(
    document_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    document = get_accessible_document(
        document_id,
        current_user,
        db
    )

    log_event(
        db=db,
        user_id=current_user.id,
        document_id=document.id,
        action="DOCUMENT_VIEWED",
        ip_address=(
            request.client.host if request.client else None
        )
    )

    return document

@router.get("/{document_id}/download")
def download_document(
    document_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    document = get_accessible_document(
        document_id,
        current_user,
        db
    )

    file_path = resolve_storage_path(document.storage_key)

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Stored file not found"
        )

    # Verify file integrity
    actual_hash = hashlib.sha256(
        file_path.read_bytes()
    ).hexdigest()

    if actual_hash != document.file_hash:
        raise HTTPException(
            status_code=409,
            detail="Document integrity verification failed"
        )

    log_event(
    db=db,
    user_id=current_user.id,
    document_id=document.id,
    action="DOCUMENT_DOWNLOADED",
    details={
        "filename": document.filename
    },
        ip_address=(
        request.client.host if request.client else None
    )
)

    return FileResponse(
        path=str(file_path),
        media_type=document.content_type,
        filename=document.filename
    )
@router.delete("/{document_id}")
def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # Verify document ownership
    document = get_owned_document(
        document_id,
        current_user,
        db
    )

    # Capture details before deletion
    filename = document.filename
    storage_key = document.storage_key

    file_path = resolve_storage_path(storage_key)

    # Soft delete in database
    document.is_deleted = True

    try:
        db.commit()

        # Record deletion in audit logs
        log_event(
            db=db,
            user_id=current_user.id,
            document_id=document.id,
            action="DOCUMENT_DELETED",
            details={
                "filename": filename,
                "storage_key": storage_key
            }
        )

    except Exception:
        db.rollback()
        raise

    # Remove physical file
    try:
        if file_path.is_file():
            file_path.unlink()

    except OSError as error:
        print("FILE CLEANUP ERROR:", error)

    return {
        "message": "Document deleted successfully",
        "document_id": str(document_id)
    }