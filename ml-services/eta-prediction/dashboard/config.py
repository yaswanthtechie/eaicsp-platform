import os


ANOMALY_SERVICE_URL = os.getenv(
    "ANOMALY_SERVICE_URL",
    "http://localhost:8001",
)