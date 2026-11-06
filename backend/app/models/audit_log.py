import uuid

from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class AuditLog(Base):

    __tablename__ = "audit_logs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True
    )

    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id"),
        nullable=True
    )

    action = Column(
        String(100),
        nullable=False
    )

    ip_address = Column(
        String(45),
        nullable=True
    )

    details = Column(
        JSON,
        nullable=True
    )

    previous_hash = Column(
        String(64),
        nullable=True
    )

    event_hash = Column(
        String(64),
        nullable=False
    )

    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )