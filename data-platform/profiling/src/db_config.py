import os

from dotenv import load_dotenv

load_dotenv()


def get_db_url() -> str:
    """Return the profiling DB URL from the environment. Fails loudly if missing."""
    url = os.environ.get("PROFILING_DB_URL")
    if not url:
        raise RuntimeError(
            "PROFILING_DB_URL is not set. Copy .env.example to .env and fill it in."
        )
    return url