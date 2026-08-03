from sqlalchemy import Column, Integer, String, Float
from app.database import Base


class Inventory(Base):
    __tablename__ = "inventory"

    # A SKU can be stocked independently in many warehouses.
    sku_id = Column(String, primary_key=True)
    product_name = Column(String, nullable=False)
    warehouse_id = Column(String, primary_key=True)
    quantity_on_hand = Column(Integer, nullable=False)
    avg_daily_demand = Column(Float, nullable=False)
    lead_time_days = Column(Integer, nullable=False)
    safety_stock = Column(Integer, nullable=False)
