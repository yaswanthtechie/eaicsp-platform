import logging
from pathlib import Path

# Create logs folder if it doesn't exist
log_folder = Path("logs")
log_folder.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(log_folder / "pipeline.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("sales_etl")