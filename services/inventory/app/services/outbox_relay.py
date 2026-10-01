import logging
from sqlalchemy.orm import Session

from app.services.kafka_producer import KafkaEventPublisher, KafkaPublishError
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
    """

    def __init__(self, publisher: KafkaEventPublisher):
        self.publisher = publisher

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

            except (KafkaPublishError, Exception) as exc:
                failed_count += 1
                error_msg = str(exc)
                mark_failed(db=db, outbox_id=event.id, error=error_msg)
                logger.error(
                    "Outbox event %s failed to publish (will retry later): %s",
                    event.id,
                    error_msg,
                )

        return published_count, failed_count
