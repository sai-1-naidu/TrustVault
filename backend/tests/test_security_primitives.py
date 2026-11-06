import os
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import jwt

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg2://trustvault_test:trustvault_test@localhost/trustvault_test"
)
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-for-unit-tests"

from app.security import jwt as token_security
from app.routers.documents import get_shared_documents, list_documents
from app.services.audit_service import calculate_event_hash, log_event


def test_password_hash_is_not_plaintext_and_can_be_verified():
    password = "CorrectHorseBatteryStaple42!"

    hashed_password = token_security.hash_password(password)

    assert hashed_password != password
    assert token_security.verify_password(password, hashed_password)
    assert not token_security.verify_password("incorrect-password", hashed_password)


def test_access_token_contains_subject_and_expiration():
    token = token_security.create_access_token("user-123")

    payload = jwt.decode(
        token,
        token_security.SECRET_KEY,
        algorithms=[token_security.ALGORITHM],
    )

    assert payload["sub"] == "user-123"
    assert payload["exp"] > datetime.now(timezone.utc).timestamp()


def test_expired_access_token_is_rejected(monkeypatch):
    monkeypatch.setattr(token_security, "ACCESS_TOKEN_EXPIRE_MINUTES", -1)
    token = token_security.create_access_token("user-123")

    try:
        jwt.decode(
            token,
            token_security.SECRET_KEY,
            algorithms=[token_security.ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        return

    raise AssertionError("An expired access token was accepted")


def test_audit_hash_is_deterministic_and_detects_changed_details():
    event_id = uuid4()
    user_id = uuid4()
    document_id = uuid4()
    timestamp = datetime.now(timezone.utc)
    common = {
        "event_id": event_id,
        "user_id": user_id,
        "document_id": document_id,
        "action": "DOCUMENT_DOWNLOADED",
        "ip_address": "127.0.0.1",
        "previous_hash": None,
        "timestamp": timestamp,
    }

    original_hash = calculate_event_hash(
        **common,
        details={"filename": "report.pdf"},
    )
    matching_hash = calculate_event_hash(
        **common,
        details={"filename": "report.pdf"},
    )
    modified_hash = calculate_event_hash(
        **common,
        details={"filename": "changed.pdf"},
    )

    assert original_hash == matching_hash
    assert original_hash != modified_hash


def test_audit_event_timestamp_advances_after_previous_event():
    previous_timestamp = datetime.now(timezone.utc)
    previous_event = type(
        "PreviousEvent",
        (),
        {
            "event_hash": "previous-event-hash",
            "timestamp": previous_timestamp,
        },
    )()

    class Query:
        def order_by(self, *_):
            return self

        def first(self):
            return previous_event

    class Database:
        event = None

        def execute(self, *_args, **_kwargs):
            return None

        def query(self, *_args, **_kwargs):
            return Query()

        def add(self, event):
            self.event = event

        def commit(self):
            return None

        def refresh(self, _event):
            return None

        def rollback(self):
            return None

    database = Database()
    event = log_event(
        db=database,
        user_id=uuid4(),
        document_id=uuid4(),
        action="DOCUMENT_VIEWED",
    )

    assert event.previous_hash == previous_event.event_hash
    assert event.timestamp > previous_timestamp


class DocumentQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []

    def join(self, *_args, **_kwargs):
        return self

    def filter(self, *conditions):
        self.filters.extend(conditions)
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return self.rows


class DocumentDatabase:
    def __init__(self, rows):
        self.query_result = DocumentQuery(rows)

    def query(self, *_args, **_kwargs):
        return self.query_result


def test_list_documents_returns_owned_document_results():
    rows = [SimpleNamespace(filename="owned.pdf")]
    database = DocumentDatabase(rows)

    result = list_documents(
        current_user=SimpleNamespace(id=uuid4()),
        db=database,
    )

    assert result == rows
    assert len(database.query_result.filters) == 2


def test_shared_documents_filter_by_query_and_return_results():
    rows = [SimpleNamespace(filename="shared-report.pdf")]
    database = DocumentDatabase(rows)

    result = get_shared_documents(
        q="  report  ",
        current_user=SimpleNamespace(id=uuid4()),
        db=database,
    )

    assert result == rows
    assert len(database.query_result.filters) == 4
