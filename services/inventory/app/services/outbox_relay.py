import logging
import os
import time
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from app.services.kafka_producer import (
    KafkaEventPublisher,
    KafkaPublishError,
    is_broker_error,
)
from app.services.outbox_service import (
    get_pending_events,
    mark_failed,
    mark_published,
)

logger = logging.getLogger(__name__)


class OutboxRelay:
    """
    Transactional Outbox Relay Worker.
    Polls the outbox table for pending events and delivers them to Kafka.
    Guarantees at-least-once delivery without losing events during Kafka downtime.

    Includes a Circuit Breaker:
    When a broker outage or connection timeout is encountered, the circuit breaker
    trips immediately, stopping the batch loop so that 50 pending events do not each
    wait for a 5-second timeout (preventing the 250s cycle delay).
    """

    def __init__(
        self,
        publisher: KafkaEventPublisher,
        circuit_cooldown_seconds: float = 10.0,
    ):
        self.publisher = publisher
        self.circuit_cooldown_seconds = circuit_cooldown_seconds
        self._circuit_open_until: float = 0.0

    @property
    def is_circuit_open(self) -> bool:
        return time.monotonic() < self._circuit_open_until

    def trip_circuit_breaker(self, cooldown: Optional[float] = None) -> None:
        duration = cooldown if cooldown is not None else self.circuit_cooldown_seconds
        self._circuit_open_until = time.monotonic() + duration
        logger.warning(
            "Broker outage detected; circuit breaker tripped for %.1fs to protect broker and avoid poll timeouts",
            duration,
        )

    def relay_pending_events(
        self,
        db: Session,
        batch_size: int = 50,
    ) -> tuple[int, int]:
        """
        Process a batch of pending outbox events.
        
        Returns:
            tuple[int, int]: (published_count, failed_count)
        """
        if self.is_circuit_open:
            logger.debug("Relay skipped: circuit breaker is open")
            return 0, 0

        pending = get_pending_events(db=db, limit=batch_size)
        published_count = 0
        failed_count = 0

        for event in pending:
            try:
                self.publisher.publish(
                    topic=event.event_type,
                    key=event.aggregate_id,
                    value=event.payload,
                )
                mark_published(db=db, outbox_id=event.id)
                published_count += 1
                logger.info(
                    "Outbox event %s (%s) published to topic %s",
                    event.id,
                    event.aggregate_id,
                    event.event_type,
                )

            except Exception as exc:
                failed_count += 1
                error_msg = str(exc)
                broker_err = is_broker_error(exc)

                mark_failed(
                    db=db,
                    outbox_id=event.id,
                    error=error_msg,
                    is_broker_error=broker_err,
                )

                if broker_err:
                    # Circuit breaker: broker is unreachable / timed out.
                    # Stop processing remainder of batch immediately so we don't spend 5s * 50 per cycle.
                    logger.error(
                        "Broker outage while publishing event %s: %s. Tripping circuit breaker.",
                        event.id,
                        error_msg,
                    )
                    self.trip_circuit_breaker()
                    break
                else:
                    logger.error(
                        "Outbox event %s failed to publish due to event defect: %s",
                        event.id,
                        error_msg,
                    )

        return published_count, failed_count


HEARTBEAT_FILE = Path(
    os.getenv("OUTBOX_RELAY_HEARTBEAT_FILE", "/tmp/outbox-relay.heartbeat")
)


def write_heartbeat(path: Path = HEARTBEAT_FILE) -> None:
    """Touch the heartbeat file; the container healthcheck checks its age."""
    try:
        path.write_text(str(time.time()), encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not write relay heartbeat %s: %s", path, exc)


def run_relay_worker(
    poll_interval: float = 2.0,
    stop_event=None,
) -> None:
    """
    Continuous worker loop that polls and relays pending outbox events.
    Can be run as a standalone process (python -m app.services.outbox_relay)
    or as a background thread inside FastAPI lifespan.
    """
    from app.database import SessionLocal

    logger.info("Starting Outbox Relay Worker (poll_interval=%s s)...", poll_interval)
    publisher = KafkaEventPublisher()
    relay = OutboxRelay(publisher=publisher)

    while True:
        if stop_event is not None and stop_event.is_set():
            logger.info("Stopping Outbox Relay Worker...")
            break

        db = SessionLocal()
        try:
            pub, fail = relay.relay_pending_events(db=db)
            if pub > 0 or fail > 0:
                logger.info(
                    "Outbox relay cycle: %d published, %d failed",
                    pub,
                    fail,
                )
        except Exception as exc:
            logger.error("Outbox relay error: %s", exc)
        finally:
            db.close()

        # Written after every completed cycle, including cycles skipped by the
        # circuit breaker. If the loop hangs or dies, the file goes stale.
        write_heartbeat()

        if stop_event is not None:
            stop_event.wait(poll_interval)
        else:
            time.sleep(poll_interval)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_relay_worker()
