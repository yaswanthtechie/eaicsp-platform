from abc import ABC, abstractmethod

class CarrierAdapter(ABC):
     
    @abstractmethod
    def get_rate(self,origin,destination,weight_kg):
        pass

    
    @abstractmethod
    def get_tracking(self,tracking_number):
        pass