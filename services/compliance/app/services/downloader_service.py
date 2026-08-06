from pathlib import Path
import requests

from app.core.config import (
    OFAC_DOWNLOAD_URL,
    UN_DOWNLOAD_URL,
    EU_DOWNLOAD_URL,

    OFAC_CSV_PATH,
    UN_XML_PATH,
    EU_XML_PATH,
)



def download_file(
    url: str,
    save_path: Path
):

    save_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    response = requests.get(
        url,
        timeout=60
    )

    response.raise_for_status()


    with open(
        save_path,
        "wb"
    ) as file:

        file.write(
            response.content
        )


    print(
        f"Downloaded {save_path}"
    )



def download_all_lists():


    files = [

        (
            OFAC_DOWNLOAD_URL,
            OFAC_CSV_PATH
        ),

        (
            UN_DOWNLOAD_URL,
            UN_XML_PATH
        ),

        (
            EU_DOWNLOAD_URL,
            EU_XML_PATH
        )

    ]


    for url, path in files:

        download_file(
            url,
            path
        )


    return True