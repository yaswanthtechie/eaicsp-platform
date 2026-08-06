from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent


DATA_DIR = BASE_DIR / "data"


OFAC_CSV_PATH = DATA_DIR / "ofac.csv"

UN_CSV_PATH = DATA_DIR / "un.csv"


AUDIT_LOG_PATH = BASE_DIR / "app" / "audit.log"


MATCH_THRESHOLD = 85