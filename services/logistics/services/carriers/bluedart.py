from app.services.carriers.base import CarrierAdapter
class BlueDartAdapter(CarrierAdapter):
    def get_rate(self, origin, destination, weight_kg):
        return{"carrier":"BlueDart","price":550,"estimated_days":2}
    def get_tracking(self, tracking_number):
        return{"carrier":"BlueDart","tracking_number":tracking_number,"status":"in_transit"}
        

    