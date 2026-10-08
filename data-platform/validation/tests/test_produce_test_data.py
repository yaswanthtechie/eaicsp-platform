import pytest
from unittest.mock import MagicMock, patch
from data_validator.produce_test_data import delivery_report, main


def test_delivery_report_success(capsys):
    """Test the delivery callback when a message succeeds."""
    mock_msg = MagicMock()
    mock_msg.topic.return_value = "sales.raw"
    mock_msg.partition.return_value = 0

    delivery_report(None, mock_msg)

    captured = capsys.readouterr()
    assert "Message delivered to sales.raw [0]" in captured.out


def test_delivery_report_error(capsys):
    """Test the delivery callback when a message fails."""
    delivery_report("Connection timeout", None)

    captured = capsys.readouterr()
    assert "Message delivery failed: Connection timeout" in captured.out


@patch("data_validator.produce_test_data.Producer")
def test_produce_main(mock_producer_class):
    """Test the main producer execution."""
    mock_producer = MagicMock()
    mock_producer_class.return_value = mock_producer

    main()

    # Verify the producer was instantiated with the correct config
    mock_producer_class.assert_called_once_with({'bootstrap.servers': 'localhost:9092'})

    # Verify 3 messages were produced and the producer was flushed
    assert mock_producer.produce.call_count == 3
    mock_producer.flush.assert_called_once()