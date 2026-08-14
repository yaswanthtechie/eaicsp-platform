import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# etl/src/config.py -> parents[2] is the project/Airflow root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
BATCH_DIR = DATA_DIR / "batches"
REJECTED_DIR = DATA_DIR / "rejected"
LOG_DIR = PROJECT_ROOT / "logs"

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
