
import os
from pathlib import Path

from dotenv import load_dotenv



load_dotenv()




BASE_DIR = Path(__file__).resolve().parent.parent.parent

APP_DIR = BASE_DIR / "app"

DATA_DIR = APP_DIR / "data"

DOWNLOAD_DIR = DATA_DIR / "downloads"

SNAPSHOT_DIR = DATA_DIR / "snapshots"

LOG_DIR = DATA_DIR / "logs"

ARCHIVE_DIR = DATA_DIR / "archive"



OFAC_CSV_PATH = DOWNLOAD_DIR / "ofac.csv"

UN_XML_PATH = DOWNLOAD_DIR / "un.xml"

EU_XML_PATH = DOWNLOAD_DIR / "eu.xml"

FIXTURE_DIR = DATA_DIR / "fixtures"

OFAC_FIXTURE_PATH = (
    FIXTURE_DIR / "ofac_sample.csv"
)

UN_FIXTURE_PATH = (
    FIXTURE_DIR / "un_sample.xml"
)

EU_FIXTURE_PATH = (
    FIXTURE_DIR / "eu_sample.xml"
)

SNAPSHOT_FILE = (
    SNAPSHOT_DIR
    / "previous_sanctions.json"
)



DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./compliance.db",
)



SERVICE_NAME = os.getenv(
    "SERVICE_NAME",
    "compliance-service",
)

ENVIRONMENT = os.getenv(
    "ENVIRONMENT",
    "development",
)

MATCH_THRESHOLD = int(
    os.getenv(
        "MATCH_THRESHOLD",
        "90",
    )
)

DEDUPE_THRESHOLD = int(
    os.getenv(
        "DEDUPE_THRESHOLD",
        "90",
    )
)

CONFIDENCE_WEIGHT = float(
    os.getenv(
        "CONFIDENCE_WEIGHT",
        "0.50",
    )
)

SOURCE_WEIGHT = float(
    os.getenv(
        "SOURCE_WEIGHT",
        "0.30",
    )
)

RECENCY_WEIGHT = float(
    os.getenv(
        "RECENCY_WEIGHT",
        "0.20",
    )
)

SANCTIONS_WEIGHT = float(
    os.getenv(
        "SANCTIONS_WEIGHT",
        "0.80",
    )
)

COUNTRY_RISK_WEIGHT = float(
    os.getenv(
        "COUNTRY_RISK_WEIGHT",
        "0.20",
    )
)

PLATFORM_SERVICE_URL = os.getenv(
    "PLATFORM_SERVICE_URL",
    "http://127.0.0.1:8005",
)


OFAC_DOWNLOAD_URL = os.getenv(
    "OFAC_DOWNLOAD_URL",
    "https://sanctionslistservice.ofac.treas.gov/"
    "api/PublicationPreview/exports/SDN.CSV",
)

UN_DOWNLOAD_URL = os.getenv(
    "UN_DOWNLOAD_URL",
    "https://scsanctions.un.org/"
    "resources/xml/en/consolidated.xml",
)

EU_DOWNLOAD_URL = os.getenv(
    "EU_DOWNLOAD_URL",
    "",
)



USE_FIXTURES = os.getenv(
    "USE_FIXTURES",
    "false",
).lower() == "true"
