import pytest
from pathlib import Path

from app.core.config import (
    OFAC_CSV_PATH,
    UN_XML_PATH,
    EU_XML_PATH,
)

from app.services.downloader_service import (
    download_all_lists,
)


@pytest.mark.integration
def test_live_sanctions_download():
    """
    Integration test that downloads the current OFAC, UN, and EU
    sanctions lists and verifies that the expected files exist.
    """

    # Download the latest live sanctions lists
    download_all_lists()

    # Verify all expected files were downloaded
    expected_files = [
        Path(OFAC_CSV_PATH),
        Path(UN_XML_PATH),
        Path(EU_XML_PATH),
    ]

    for file_path in expected_files:
        assert file_path.exists(), (
            f"Expected sanctions file was not downloaded: {file_path}"
        )

        assert file_path.stat().st_size > 0, (
            f"Downloaded sanctions file is empty: {file_path}"
        )