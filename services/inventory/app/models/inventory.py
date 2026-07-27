from sqlalchemy import Column, Integer, String, Float
from app.database import Base


class Inventory(Base):
    __tablename__ = "inventory"

    sku_id = Column(String, primary_key=True, index=True)
    product_name = Column(String, nullable=False)
    warehouse_id = Column(String, nullable=False)
    quantity_on_hand = Column(Integer, nullable=False)
    avg_daily_demand = Column(Float, nullable=False)
    lead_time_days = Column(Integer, nullable=False)
    safety_stock = Column(Integer, nullable=False)