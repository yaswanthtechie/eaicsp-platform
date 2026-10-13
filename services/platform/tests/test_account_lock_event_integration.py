import json
import time
import uuid
import pytest
from fastapi import HTTPException
from kafka import KafkaAdminClient, KafkaConsumer
from kafka.admin import NewTopic
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.users import User
from app.models.roles import Role
from app.models.failed_login_attempts import FailedLoginAttempt
from app.services.auth_service import login_user
from app.core.security import hash_password
from app.services.audit_service import ACCOUNT_LOCKED

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC = "platform.user.locked"


def ensure_kafka_topic():
    """
    Create the event topic if it does not already exist.

    This makes the integration test independent of whether another
    Kafka test has already created the topic.
    """
    admin = KafkaAdminClient(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        client_id=f"platform-test-admin-{uuid.uuid4()}",
    )

    try:
        topic = NewTopic(
            name=TOPIC,
            num_partitions=1,
            replication_factor=1,
        )

        try:
            admin.create_topics(
                new_topics=[topic],
                validate_only=False,
            )
        except Exception as exc:
            # Kafka raises an exception when the topic already exists.
            # That is acceptable for this test.
            if "TopicAlreadyExists" not in str(exc):
                # Do not fail unnecessarily for a topic that was already
                # created between metadata checks.
                if "already exists" not in str(exc).lower():
                    raise
    finally:
        admin.close()


def wait_for_consumer_assignment(consumer, timeout_seconds=10):
    """
    Wait until Kafka assigns the consumer a partition.
    """
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        consumer.poll(timeout_ms=500)

        if consumer.assignment():
            return True

    return False


@pytest.mark.integration
def test_real_account_lock_publishes_platform_user_locked_event():
    """
    End-to-end integration test:

        failed login x5
              |
              v
        account locked
              |
              +--> ACCOUNT_LOCKED audit event
              |
              +--> Kafka
                     |
                     v
              platform.user.locked

    Requires Kafka running on localhost:9092.
    """

    ensure_kafka_topic()

    db: Session = SessionLocal()

    test_email = (
        f"lock-event-test-{uuid.uuid4().hex[:12]}"
        "@example.com"
    )
    test_password = "ValidTestPassword@123"

    consumer_group = f"platform-lock-test-{uuid.uuid4()}"

    consumer = KafkaConsumer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=consumer_group,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda value: json.loads(
            value.decode("utf-8")
        ),
    )

    user = None

    try:
        # ---------------------------------------------------------
        # Create a dedicated test user
        # ---------------------------------------------------------

        ceo_role = (
            db.query(Role)
            .filter(Role.name == "ceo")
            .first()
        )

        assert ceo_role is not None, (
            "Required seeded role 'ceo' was not found"
        )

        user = User(
            email=test_email,
            full_name="Kafka Lock Integration Test",
            password=hash_password(test_password),
            role_id=ceo_role.id,
            is_active=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        user_id = user.id

        # ---------------------------------------------------------
        # Subscribe BEFORE triggering the event
        # ---------------------------------------------------------

        consumer.subscribe([TOPIC])

        assert wait_for_consumer_assignment(consumer), (
            "Kafka consumer did not receive a partition assignment"
        )

        # ---------------------------------------------------------
        # Trigger five real failed login attempts
        # ---------------------------------------------------------

        client_ip = "10.250.250.250"

        failed_status_codes = []

        for attempt_number in range(1, 6):
            with pytest.raises(HTTPException) as exc:
                login_user(
                    db=db,
                    username=test_email,
                    password="WrongPassword@999",
                    client_ip=client_ip,
                )

            failed_status_codes.append(exc.value.status_code)

            if attempt_number < 5:
                assert exc.value.status_code == 401

        # First four attempts are invalid credentials.
        # Fifth attempt causes the account lock.
        assert failed_status_codes == [
            401,
            401,
            401,
            401,
            423,
        ]

        # ---------------------------------------------------------
        # Verify database state
        # ---------------------------------------------------------

        db.expire_all()

        locked_user = (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )

        assert locked_user is not None

        assert locked_user.locked_until is not None, (
            "User was not marked as locked"
        )

        # ---------------------------------------------------------
        # Verify ACCOUNT_LOCKED audit event
        # ---------------------------------------------------------

        audit_events = (
            db.query(
                __import__(
                    "app.models.auth_audit_logs",
                    fromlist=["AuthAuditLog"],
                ).AuthAuditLog
            )
            .filter(
                __import__(
                    "app.models.auth_audit_logs",
                    fromlist=["AuthAuditLog"],
                ).AuthAuditLog.user_id == user_id,
                __import__(
                    "app.models.auth_audit_logs",
                    fromlist=["AuthAuditLog"],
                ).AuthAuditLog.event_type == ACCOUNT_LOCKED,
            )
            .all()
        )

        assert audit_events, (
            "ACCOUNT_LOCKED audit event was not created"
        )

        # ---------------------------------------------------------
        # Read the Kafka event
        # ---------------------------------------------------------

        received_event = None

        deadline = time.time() + 10

        while time.time() < deadline:
            records = consumer.poll(timeout_ms=1000)

            for messages in records.values():
                for message in messages:
                    event = message.value

                    if (
                        event.get("event_type") == TOPIC
                        and event.get("payload", {}).get("user_id")
                        == user_id
                    ):
                        received_event = event
                        break

                if received_event:
                    break

            if received_event:
                break

        assert received_event is not None, (
            "platform.user.locked event was not received from Kafka"
        )

        # ---------------------------------------------------------
        # Validate standard event envelope
        # ---------------------------------------------------------

        assert set(received_event.keys()) == {
            "event_id",
            "event_type",
            "event_version",
            "occurred_at",
            "producer",
            "payload",
        }

        parsed_uuid = uuid.UUID(received_event["event_id"])

        assert str(parsed_uuid) == received_event["event_id"]
        assert received_event["event_type"] == "platform.user.locked"
        assert received_event["event_version"] == 1
        assert received_event["producer"] == "platform-service"
        assert received_event["occurred_at"].endswith("Z")

        assert received_event["payload"] == {
            "user_id": user_id,
        }

    finally:
        # ---------------------------------------------------------
        # Cleanup dedicated test user and its failed-login records
        # ---------------------------------------------------------

        if user is not None:
            try:
                db.query(FailedLoginAttempt).filter(
                    FailedLoginAttempt.email == test_email
                ).delete(synchronize_session=False)

                db.query(User).filter(
                    User.id == user.id
                ).delete(synchronize_session=False)

                db.commit()
            except Exception:
                db.rollback()

        consumer.close()
        db.close()