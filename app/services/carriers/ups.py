from app.services.carriers.base import CarrierAdapter

class UPSAdapter(CarrierAdapter):
    def get_rate(self,orgin,destination,weight_kg):
         return{
              "carrier":"UPS",
              "price":450,
              "estimated_days":4
         }
    def get_tracking(self,tracking_number):
         return {
            "carrier": "UPS",
            "tracking_number": tracking_number,
            "status": "delivered"
        }