import hashlib
import os
import re
import uuid
import zipfile

from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile

from sqlalchemy.orm import Session

from app.models.document import Document


# Keep uploaded documents outside the public web root. Deployments can mount a
# persistent volume and point TRUSTVAULT_STORAGE_DIR at it.
STORAGE_DIR = Path(
    os.getenv(
        "TRUSTVAULT_STORAGE_DIR",
        str(Path(__file__).resolve().parents[2] / "storage"),
    )
).expanduser().resolve()

STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Maximum upload size: 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024


# Supported extensions
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx"
}
STORAGE_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}\.(?:pdf|docx)$")


def resolve_storage_path(storage_key: str) -> Path:
    """Resolve a generated storage key without allowing path traversal."""
    if not STORAGE_KEY_PATTERN.fullmatch(storage_key):
        raise HTTPException(status_code=404, detail="Stored file not found")

    file_path = (STORAGE_DIR / storage_key).resolve()
    if file_path.parent != STORAGE_DIR:
        raise HTTPException(status_code=404, detail="Stored file not found")

    return file_path


async def save_document(
    file: UploadFile,
    owner_id,
    db: Session
):

    original_name = Path(file.filename or "").name
    extension = Path(original_name).suffix.lower()

    if not original_name or len(original_name) > 255:
        raise HTTPException(
            status_code=400,
            detail="Filename must be between 1 and 255 characters",
        )

    # Validate extension
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are allowed"
        )

    # Read file with size limit
    content = await file.read(MAX_FILE_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Empty files are not allowed"
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Maximum file size is 10 MB"
        )

    # Validate actual file signature
    if extension == ".pdf":

        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=400,
                detail="Invalid PDF file"
            )

        content_type = "application/pdf"

    elif extension == ".docx":

        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:

                if not {
                    "[Content_Types].xml",
                    "word/document.xml"
                }.issubset(set(archive.namelist())):
                    raise ValueError("Invalid DOCX")

        except (zipfile.BadZipFile, ValueError):
            raise HTTPException(
                status_code=400,
                detail="Invalid DOCX file"
            )

        content_type = (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        )

    # Generate SHA-256 hash
    file_hash = hashlib.sha256(content).hexdigest()

    # Generate random internal storage name
    storage_key = f"{uuid.uuid4().hex}{extension}"

    file_path = resolve_storage_path(storage_key)

    try:

        # Store file privately
        file_path.write_bytes(content)

        # Create database record
        document = Document(
            owner_id=owner_id,
            filename=original_name,
            storage_key=storage_key,
            content_type=content_type,
            file_size=len(content),
            file_hash=file_hash
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        return document

    except Exception:

        db.rollback()

        # Remove file if database operation fails
        if file_path.exists():
            file_path.unlink()

        raise

    finally:
        await file.close()