import hashlib
import json
import uuid

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.audit_log import AuditLog


# PostgreSQL transaction-level advisory lock.
# This serializes audit-chain writes.
AUDIT_LOCK_KEY = 748291


def calculate_event_hash(
    event_id,
    user_id,
    document_id,
    action,
    ip_address,
    details,
    previous_hash,
    timestamp
):
    payload = {
        "id": str(event_id),
        "user_id": str(user_id) if user_id else None,
        "document_id": str(document_id) if document_id else None,
        "action": action,
        "ip_address": ip_address,
        "details": details,
        "previous_hash": previous_hash,
        "timestamp": timestamp.astimezone(timezone.utc).isoformat()
    }

    canonical_data = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False
    )

    return hashlib.sha256(
        canonical_data.encode("utf-8")
    ).hexdigest()


def log_event(
    db: Session,
    user_id,
    document_id,
    action: str,
    details: dict | None = None,
    ip_address: str | None = None
):

    try:
        # Ensure only one transaction appends to the chain at a time.
        db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": AUDIT_LOCK_KEY}
        )

        # Get the latest audit event.
        latest_event = db.query(AuditLog).order_by(
            AuditLog.timestamp.desc(),
            AuditLog.id.desc()
        ).first()

        previous_hash = (
            latest_event.event_hash
            if latest_event else None
        )

        event_id = uuid.uuid4()

        timestamp = datetime.now(timezone.utc)
        if latest_event:
            latest_timestamp = latest_event.timestamp
            if latest_timestamp.tzinfo is None:
                latest_timestamp = latest_timestamp.replace(
                    tzinfo=timezone.utc
                )
            timestamp = max(
                timestamp,
                latest_timestamp + timedelta(microseconds=1)
            )

        safe_details = details or {}

        event_hash = calculate_event_hash(
            event_id=event_id,
            user_id=user_id,
            document_id=document_id,
            action=action,
            ip_address=ip_address,
            details=safe_details,
            previous_hash=previous_hash,
            timestamp=timestamp
        )

        audit = AuditLog(
            id=event_id,
            user_id=user_id,
            document_id=document_id,
            action=action,
            ip_address=ip_address,
            details=safe_details,
            previous_hash=previous_hash,
            event_hash=event_hash,
            timestamp=timestamp
        )

        db.add(audit)
        db.commit()
        db.refresh(audit)

        return audit

    except Exception:
        db.rollback()
        raise


def verify_audit_chain(db: Session):

    events = db.query(AuditLog).order_by(
        AuditLog.timestamp.asc(),
        AuditLog.id.asc()
    ).all()

    expected_previous_hash = None

    for event in events:

        # Check chain connection
        if event.previous_hash != expected_previous_hash:
            return {
                "valid": False,
                "message": "Previous hash mismatch",
                "event_id": str(event.id)
            }

        # Recalculate event hash
        calculated_hash = calculate_event_hash(
            event_id=event.id,
            user_id=event.user_id,
            document_id=event.document_id,
            action=event.action,
            ip_address=event.ip_address,
            details=event.details,
            previous_hash=event.previous_hash,
            timestamp=event.timestamp
        )

        if calculated_hash != event.event_hash:
            return {
                "valid": False,
                "message": "Event integrity verification failed",
                "event_id": str(event.id),
                "action": event.action,
                "stored_hash": event.event_hash,
                "calculated_hash": calculated_hash,
                "stored_timestamp": event.timestamp.isoformat()
            }

        expected_previous_hash = event.event_hash

    return {
        "valid": True,
        "message": "Audit chain verified successfully",
        "total_events": len(events)
    }