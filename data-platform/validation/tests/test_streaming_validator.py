import json
import logging
import pytest
from unittest.mock import MagicMock, patch
from confluent_kafka import KafkaError
from src.streaming_validator import main


@patch("src.streaming_validator.DataValidator")
@patch("src.streaming_validator.Consumer")
@patch("src.streaming_validator.Producer")
def test_streaming_validator_full_coverage(mock_producer_class, mock_consumer_class, mock_validator_class, caplog):
    """Simulates a full Kafka stream lifecycle hitting every branch in the infinite loop."""
    caplog.set_level(logging.INFO)

    # 1. Setup Mocks
    mock_consumer = MagicMock()
    mock_producer = MagicMock()
    mock_consumer_class.return_value = mock_consumer
    mock_producer_class.return_value = mock_producer

    mock_validator = MagicMock()
    mock_validator_class.from_config.return_value = mock_validator

    # Helper function to create mock Kafka messages
    def create_mock_msg(value=None, error_code=None):
        msg = MagicMock()
        if error_code is not None:
            err = MagicMock()
            err.code.return_value = error_code
            msg.error.return_value = err
        else:
            msg.error.return_value = None
            msg.value.return_value = value
        return msg

    # 2. Define the exact sequence of events the consumer will encounter
    msg_none = None  # Branch: msg is None
    msg_eof = create_mock_msg(error_code=KafkaError._PARTITION_EOF)  # Branch: EOF Error
    msg_kafka_err = create_mock_msg(error_code=1)  # Branch: Generic Kafka Error
    msg_valid = create_mock_msg(b'{"transaction_id": 1}')  # Branch: Valid payload
    msg_invalid = create_mock_msg(b'{"transaction_id": 2}')  # Branch: Invalid payload
    msg_bad_json = create_mock_msg(b'not_json_data')  # Branch: JSONDecodeError
    msg_crash = create_mock_msg(b'{"transaction_id": "CRASH"}')  # Branch: Exception catch-all

    # The consumer will process these in order, then raise KeyboardInterrupt to exit the infinite loop
    mock_consumer.poll.side_effect = [
        msg_none,
        msg_eof,
        msg_kafka_err,
        msg_valid,
        msg_invalid,
        msg_bad_json,
        msg_crash,
        KeyboardInterrupt()
    ]

    # 3. Define how the Validator Engine responds to the payloads
    def mock_validate_row(record):
        if record.get("transaction_id") == "CRASH":
            raise RuntimeError("Simulated engine crash")

        res = MagicMock()
        if record.get("transaction_id") == 1:
            res.passed = True
        else:
            res.passed = False
            res.errors = ["mock_rule_failure"]
            res.skipped_rules = []
            res.warnings = []
        return res

    mock_validator.validate_row.side_effect = mock_validate_row

    # 4. Execute
    main()

    # 5. Assertions
    mock_validator_class.from_config.assert_called_once_with("configs/dev/sales_rules.yaml")
    mock_consumer.subscribe.assert_called_once_with(['sales.raw'])
    mock_consumer.close.assert_called_once()

    assert mock_producer.produce.call_count == 4
    mock_producer.produce.assert_any_call('sales.valid', '{"transaction_id": 1}')

    assert mock_producer.flush.call_count == 4
    assert mock_consumer.commit.call_count == 4

    assert "Consumer error" in caplog.text
    assert "Unparseable JSON received" in caplog.text
    assert "Unexpected processing error: Simulated engine crash" in caplog.text
    assert "Shutting down consumer..." in caplog.text