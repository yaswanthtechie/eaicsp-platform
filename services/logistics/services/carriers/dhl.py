from app.services.carriers.base import CarrierAdapter


class DHLAdapter(CarrierAdapter):

    def get_rate(self, origin, destination, weight_kg):

        return {
            "carrier": "DHL",
            "price": 850,
            "estimated_days": 2
        }

    def get_tracking(self, tracking_number):

        return {
            "carrier": "DHL",
            "tracking_number": tracking_number,
            "status": "in_transit"
        }