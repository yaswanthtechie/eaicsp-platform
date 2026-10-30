"""
Realtime analytics WebSocket and Kafka consumer module (R15-M3).
"""

from app.services.realtime.auth import ws_auth_service
from app.services.realtime.connection_manager import connection_manager
from app.services.realtime.deduplicator import Deduplicator
from app.services.realtime.dlq import dlq_service
from app.services.realtime.kafka_consumer import realtime_consumer_service

__all__ = [
    "connection_manager",
    "Deduplicator",
    "dlq_service",
    "realtime_consumer_service",
    "ws_auth_service",
]
