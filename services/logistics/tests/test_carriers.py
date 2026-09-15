import pytest

from app.services.carriers.base import (
    api_retry,
    CarrierError,
)

from app.services.carriers.dhl import DHLAdapter
from app.services.carriers.fedex import FedExAdapter
from app.services.carriers.ups import UPSAdapter
from app.services.carriers.bluedart import BlueDartAdapter


# DHL RATE TEST
def test_dhl_rate():

    dhl = DHLAdapter()

    result = dhl.get_rate(
        "Hyderabad",
        "Mumbai",
        25.5,
    )

    assert result.carrier.value == "dhl"
    assert result.origin == "Hyderabad"
    assert result.destination == "Mumbai"
    assert result.weight_kg == 25.5


# DHL TRACKING TEST
def test_dhl_tracking():

    dhl = DHLAdapter()

    result = dhl.get_tracking("1")

    assert result.carrier.value == "dhl"
    assert result.tracking_number == "1"


# FEDEX RATE TEST
def test_fedex_rate():

    fedex = FedExAdapter()

    result = fedex.get_rate(
        "Hyderabad",
        "Mumbai",
        25.5,
    )

    assert result.carrier.value == "fedex"
    assert result.origin == "Hyderabad"
    assert result.destination == "Mumbai"
    assert result.weight_kg == 25.5


# FEDEX TRACKING TEST
def test_fedex_tracking():

    fedex = FedExAdapter()

    result = fedex.get_tracking("2")

    assert result.carrier.value == "fedex"
    assert result.tracking_number == "2"


# UPS RATE TEST
def test_ups_rate():

    ups = UPSAdapter()

    result = ups.get_rate(
        "Hyderabad",
        "Mumbai",
        25.5,
    )

    assert result.carrier.value == "ups"
    assert result.origin == "Hyderabad"
    assert result.destination == "Mumbai"
    assert result.weight_kg == 25.5


# UPS TRACKING TEST
def test_ups_tracking():

    ups = UPSAdapter()

    result = ups.get_tracking("3")

    assert result.carrier.value == "ups"
    assert result.tracking_number == "3"


# BLUEDART RATE TEST
def test_bluedart_rate():

    bluedart = BlueDartAdapter()

    result = bluedart.get_rate(
        "Hyderabad",
        "Mumbai",
        25.5,
    )

    assert result.carrier.value == "bluedart"
    assert result.origin == "Hyderabad"
    assert result.destination == "Mumbai"
    assert result.weight_kg == 25.5


# BLUEDART TRACKING TEST
def test_bluedart_tracking():

    bluedart = BlueDartAdapter()

    result = bluedart.get_tracking("4")

    assert result.carrier.value == "bluedart"
    assert result.tracking_number == "4"


# RETRY TEST
def test_retry_attempts_three_times():

    counter = {"count": 0}

    @api_retry()
    def always_fail():
        counter["count"] += 1
        raise CarrierError("Carrier timeout")

    with pytest.raises(CarrierError):
        always_fail()

    assert counter["count"] == 3