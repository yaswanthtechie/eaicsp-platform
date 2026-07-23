from app.services.carriers.base import CarrierAdapter

class FedExAdapter(CarrierAdapter):
  def get_rate(self, origin, destination, weight_kg):
    return{
      "carrier":"FedEx",
      "price":650,
      "estimated_days":1
    }
  def get_tracking(self, tracking_number):
    return {
            "carrier": "FedEx",
            "tracking_number": tracking_number,
            "status": "in_transit"
        }