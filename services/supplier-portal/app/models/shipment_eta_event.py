from sqlalchemy import Column, DateTime, String, func

from app.core.config import settings
from app.database import Base


class ShipmentETAEvent(Base):
    __tablename__ = "shipment_eta_events"
    __table_args__ = {"schema": settings.SUPPLIER_DB_SCHEMA}

    event_id = Column(String(36), primary_key=True)
    shipment_id = Column(String(20), nullable=False, index=True)
    predicted_at = Column(DateTime(timezone=True), nullable=False)
    processed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )