import os
from datetime import datetime, timezone
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://trustvault_test:trustvault_test@localhost/trustvault_test",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-only-secret-key-for-unit-tests",
)

import pytest
from fastapi import HTTPException

from app.models.document import Document
from app.models.permission import DocumentPermission
from app.models.user import User
from app.routers.admin import router
from app.schemas.admin import AdminUserResponse
from app.security.dependencies import require_admin
from app.services import admin_service


class FakeQuery:
    def __init__(self, result=None, count=0):
        self.result = result
        self.count_result = count

    def filter(self, *_conditions):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.result

    def count(self):
        return self.count_result


class FakeDatabase:
    def __init__(
        self,
        *,
        user=None,
        document=None,
        recipient=None,
        permission=None,
        active_admin_count=0,
    ):
        self.user = user
        self.document = document
        self.recipient = recipient
        self.permission = permission
        self.active_admin_count = active_admin_count
        self.commits = 0

    def execute(self, *_args, **_kwargs):
        return None

    def get(self, model, _identifier):
        if model is User:
            return self.user
        return None

    def query(self, *models):
        model = models[0]
        if model is Document:
            result = self.document
        elif model is DocumentPermission:
            result = self.permission
        elif model is User and len(models) == 1:
            result = self.recipient or self.user
        else:
            result = None
        return FakeQuery(
            result,
            count=self.active_admin_count if model is User else 0,
        )

    def commit(self):
        self.commits += 1


def make_user(*, role="USER", is_active=True, name="Test User", email=None):
    user = User(
        id=uuid4(),
        name=name,
        email=email or f"{uuid4().hex}@example.com",
        password_hash="not-returned",
        role=role,
        is_active=is_active,
        created_at=datetime.now(timezone.utc),
    )
    return user


def test_every_admin_route_requires_admin_dependency():
    assert router.routes
    for route in router.routes:
        assert any(
            dependency.call is require_admin
            for dependency in route.dependant.dependencies
        ), route.path


def test_admin_user_response_does_not_expose_password_hash():
    assert "password_hash" not in AdminUserResponse.model_fields
    user = make_user(role="ADMIN")

    response = AdminUserResponse.model_validate(user)

    assert response.id == user.id
    assert response.email == user.email


def test_admin_can_promote_user_and_action_is_audited(monkeypatch):
    target = make_user()
    actor = make_user(role="ADMIN")
    db = FakeDatabase(user=target)
    audit_events = []

    def record_event(**event):
        audit_events.append(event)
        db.commit()

    monkeypatch.setattr(admin_service, "log_event", record_event)

    result = admin_service.set_user_role(db, target.id, "ADMIN", actor)

    assert result.role == "ADMIN"
    assert db.commits == 1
    assert audit_events[0]["action"] == "USER_PROMOTED_TO_ADMIN"
    assert audit_events[0]["user_id"] == actor.id


def test_last_active_admin_cannot_be_demoted(monkeypatch):
    target = make_user(role="ADMIN")
    actor = make_user(role="ADMIN")
    db = FakeDatabase(user=target, active_admin_count=1)
    monkeypatch.setattr(
        admin_service,
        "log_event",
        lambda **_event: pytest.fail("Must not audit a rejected change"),
    )

    with pytest.raises(HTTPException) as error:
        admin_service.set_user_role(db, target.id, "USER", actor)

    assert error.value.status_code == 409
    assert target.role == "ADMIN"


def test_last_active_admin_cannot_be_deactivated(monkeypatch):
    target = make_user(role="ADMIN")
    actor = make_user(role="ADMIN")
    db = FakeDatabase(user=target, active_admin_count=1)
    monkeypatch.setattr(
        admin_service,
        "log_event",
        lambda **_event: pytest.fail("Must not audit a rejected change"),
    )

    with pytest.raises(HTTPException) as error:
        admin_service.set_user_active(db, target.id, False, actor)

    assert error.value.status_code == 409
    assert target.is_active


def test_admin_cannot_deactivate_self():
    actor = make_user(role="ADMIN")
    db = FakeDatabase(user=actor)

    with pytest.raises(HTTPException) as error:
        admin_service.set_user_active(db, actor.id, False, actor)

    assert error.value.status_code == 409
    assert actor.is_active


def test_transfer_reassigns_owner_preserves_file_and_audits_policy(monkeypatch):
    owner = make_user(name="Previous Owner")
    new_owner = make_user(name="New Owner")
    actor = make_user(role="ADMIN")
    file_hash = "a" * 64
    document = Document(
        id=uuid4(),
        owner_id=owner.id,
        filename="confidential.pdf",
        storage_key=f"{uuid4().hex}.pdf",
        content_type="application/pdf",
        file_size=123,
        file_hash=file_hash,
        is_deleted=False,
        created_at=datetime.now(timezone.utc),
    )
    viewer_permission = DocumentPermission(
        id=uuid4(),
        document_id=document.id,
        user_id=new_owner.id,
        permission="VIEWER",
        granted_by=owner.id,
        created_at=datetime.now(timezone.utc),
        revoked_at=None,
    )
    db = FakeDatabase(
        user=owner,
        document=document,
        recipient=new_owner,
        permission=viewer_permission,
    )
    audit_events = []

    def record_event(**event):
        audit_events.append(event)
        db.commit()

    monkeypatch.setattr(admin_service, "log_event", record_event)

    response = admin_service.transfer_document_ownership(
        db,
        document.id,
        new_owner.email,
        actor,
    )

    assert document.owner_id == new_owner.id
    assert document.file_hash == file_hash
    assert document.storage_key.endswith(".pdf")
    assert viewer_permission.revoked_at is not None
    assert response["previous_owner_id"] == owner.id
    assert response["new_owner_id"] == new_owner.id
    assert audit_events[0]["action"] == "DOCUMENT_OWNERSHIP_TRANSFERRED"
    assert audit_events[0]["document_id"] == document.id
    assert audit_events[0]["user_id"] == actor.id
    assert audit_events[0]["details"]["new_owner_viewer_permission_revoked"]


def test_transfer_rejects_existing_owner_as_recipient(monkeypatch):
    owner = make_user()
    actor = make_user(role="ADMIN")
    document = Document(
        id=uuid4(),
        owner_id=owner.id,
        filename="report.pdf",
        storage_key=f"{uuid4().hex}.pdf",
        content_type="application/pdf",
        file_size=12,
        file_hash="b" * 64,
        is_deleted=False,
        created_at=datetime.now(timezone.utc),
    )
    db = FakeDatabase(
        user=owner,
        document=document,
        recipient=owner,
    )
    monkeypatch.setattr(
        admin_service,
        "log_event",
        lambda **_event: pytest.fail("Must not audit a rejected transfer"),
    )

    with pytest.raises(HTTPException) as error:
        admin_service.transfer_document_ownership(
            db,
            document.id,
            owner.email,
            actor,
        )

    assert error.value.status_code == 409
    assert document.owner_id == owner.id
