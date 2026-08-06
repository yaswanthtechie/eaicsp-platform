from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent


DATA_DIR = BASE_DIR / "app" / "data"

DOWNLOAD_DIR = DATA_DIR / "downloads"

ARCHIVE_DIR = DATA_DIR / "archive"

LOG_DIR = DATA_DIR / "logs"


OFAC_CSV_PATH = DOWNLOAD_DIR / "ofac.csv"

UN_XML_PATH = DOWNLOAD_DIR / "un.xml"

EU_XML_PATH = DOWNLOAD_DIR / "eu.xml"

SNAPSHOT_FILE = DATA_DIR / "snapshots" / "previous_sanctions.json"


MATCH_THRESHOLD = 90

SERVICE_NAME = "Compliance Service"


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
    "public/files/xmlFullSanctionsList_1_1/content?token=n002gggg"
)