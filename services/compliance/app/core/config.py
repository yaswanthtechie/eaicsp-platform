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


SNAPSHOT_FILE = (
    SNAPSHOT_DIR /
    "previous_sanctions.json"
)


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./compliance.db"
)


SERVICE_NAME = os.getenv(
    "SERVICE_NAME",
    "compliance-service"
)


MATCH_THRESHOLD = int(
    os.getenv(
        "MATCH_THRESHOLD",
        90
    )
)


DEDUPE_THRESHOLD = int(
    os.getenv(
        "DEDUPE_THRESHOLD",
        90
    )
)



OFAC_DOWNLOAD_URL = (
    "https://sanctionslistservice.ofac.treas.gov/"
    "api/PublicationPreview/exports/SDN.CSV"
)


UN_DOWNLOAD_URL = (
    "https://scsanctions.un.org/resources/xml/en/"
    "consolidated.xml"
)


EU_DOWNLOAD_URL = (
    "https://webgate.ec.europa.eu/fsd/fsf/"
    "public/files/xmlFullSanctionsList_1_1/"
    "content?token=n002gggg"
)