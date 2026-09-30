import json
import logging
import sys
from confluent_kafka import Consumer, Producer, KafkaError
from src.validator import DataValidator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    # Initialize the core validator engine using the local dev profile
    validator = DataValidator.from_config("configs/dev/sales_rules.yaml")

    consumer = Consumer({
        'bootstrap.servers': 'localhost:9092',
        'group.id': 'validation-group-v1',
        'auto.offset.reset': 'earliest',
        # Disable auto-commit to prevent data loss if the consumer crashes mid-processing
        'enable.auto.commit': False
    })

    producer = Producer({
        'bootstrap.servers': 'localhost:9092',
        'enable.idempotence': True  # Ensures exact-once writes downstream
    })

    consumer.subscribe(['sales.raw'])
    logger.info("Listening to 'sales.raw'...")

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error(f"Consumer error: {msg.error()}")
                continue

            raw_payload = msg.value().decode('utf-8')

            try:
                record = json.loads(raw_payload)
                transaction_id = record.get("transaction_id", "UNKNOWN")

                # Execute row-level validation
                result = validator.validate_row(record)

                if result.passed:
                    logger.info(f"Record [{transaction_id}] PASSED. Routing to 'sales.valid'.")
                    producer.produce('sales.valid', raw_payload)
                else:
                    logger.warning(f"Record [{transaction_id}] FAILED {result.errors}. Routing to 'sales.dlq'.")
                    # Construct DLQ payload with the original record and all engine diagnostics
                    dlq_payload = {
                        "original_record": record,
                        "validation_errors": result.errors,
                        "schema_reasons": result.skipped_rules,
                        "warnings": result.warnings
                    }
                    producer.produce('sales.dlq', json.dumps(dlq_payload).encode('utf-8'))

                # Block until the broker acknowledges the message has been written to .valid or .dlq
                producer.flush()

                # ONLY commit the offset after the downstream write is guaranteed
                consumer.commit(msg)

            except json.JSONDecodeError:
                # Hard JSON failures bypass the engine entirely and go straight to DLQ
                logger.error("Unparseable JSON received. Routing to DLQ.")
                dlq_payload = {"original_record": raw_payload, "validation_errors": ["json_parse_error"]}
                producer.produce('sales.dlq', json.dumps(dlq_payload).encode('utf-8'))
                producer.flush()
                consumer.commit(msg)

            except Exception as e:
                # Catch-all to ensure a bad record NEVER stops the consumer
                logger.error(f"Unexpected processing error: {e}. Routing to DLQ.")
                dlq_payload = {"original_record": raw_payload, "validation_errors": ["fatal_consumer_exception"]}
                producer.produce('sales.dlq', json.dumps(dlq_payload).encode('utf-8'))
                producer.flush()
                consumer.commit(msg)

    except KeyboardInterrupt:
        logger.info("Shutting down consumer...")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()