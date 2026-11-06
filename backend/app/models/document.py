import uuid

from sqlalchemy import (
    Column,
    String,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class Document(Base):

    __tablename__ = "documents"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    filename = Column(
        String(255),
        nullable=False
    )

    storage_key = Column(
        String(500),
        unique=True,
        nullable=False
    )

    content_type = Column(
        String(100),
        nullable=False
    )

    file_size = Column(
        BigInteger,
        nullable=False
    )

    file_hash = Column(
        String(64),
        nullable=False
    )

    is_deleted = Column(
        Boolean,
        default=False,
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )