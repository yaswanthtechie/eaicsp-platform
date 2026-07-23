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
        25.5
    )

    assert result["carrier"] == "DHL"

# DHL TRACKING TEST
def test_dhl_tracking():
    dhl = DHLAdapter()
    result = dhl.get_tracking(1)
    assert result["carrier"] == "DHL"
    assert result["tracking_number"] == 1

# FEDEX RATE TEST
def test_fedex_rate():
    fedex = FedExAdapter()
    result = fedex.get_rate(
        "Hyderabad",
        "Mumbai",
        25.5
    )
    assert result["carrier"] == "FedEx"

# FEDEX TRACKING TEST
def test_fedex_tracking():
    fedex = FedExAdapter()
    result = fedex.get_tracking(2)
    assert result["carrier"] == "FedEx"
    assert result["tracking_number"] == 2

# UPS RATE TEST
def test_ups_rate():
    ups = UPSAdapter()
    result = ups.get_rate(
        "Hyderabad",
        "Mumbai",
        25.5
    )
    assert result["carrier"] == "UPS"

# UPS TRACKING TEST
def test_ups_tracking():
    ups = UPSAdapter()
    result = ups.get_tracking(3)
    assert result["carrier"] == "UPS"
    assert result["tracking_number"] == 3

# BLUEDART TRACKING TEST
def test_bluedart_rate():
    bluedart = BlueDartAdapter()
    result = bluedart.get_rate(
        "Hyderabad",
        "Mumbai",
        25.5
    )
    assert result["carrier"] == "BlueDart"

def test_bluedart_tracking():
    bluedart = BlueDartAdapter()
    result = bluedart.get_tracking(4)
    assert result["carrier"] == "BlueDart"
    assert result["tracking_number"] == 4