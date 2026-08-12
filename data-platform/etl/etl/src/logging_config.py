import logging
from pathlib import Path

log_folder = Path("logs")
log_folder.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("sales_etl")
logger.setLevel(logging.INFO)

if not logger.handlers:

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    file_handler = logging.FileHandler(
        log_folder / "pipeline.log"
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)