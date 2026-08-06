from pathlib import Path
import shutil

import requests

from app.core.config import (
    OFAC_DOWNLOAD_URL,
    UN_DOWNLOAD_URL,
    EU_DOWNLOAD_URL,
    OFAC_CSV_PATH,
    UN_XML_PATH,
    EU_XML_PATH,
)



def validate_download(
    file_path: Path
):

    if not file_path.exists():

        raise RuntimeError(
            f"{file_path.name} missing after download."
        )


    file_size = file_path.stat().st_size


    minimum_size = 100


    if file_size < minimum_size:

        raise RuntimeError(
            f"{file_path.name} is too small. "
            "Possible incomplete download."
        )



    with open(
        file_path,
        "rb"
    ) as file:

        first_bytes = file.read(500).lower()


    if (

        b"<html" in first_bytes

        or

        b"<!doctype html" in first_bytes

    ):

        raise RuntimeError(
            f"{file_path.name} contains HTML response."
        )



    if file_path.suffix.lower() == ".xml":


        if not first_bytes.lstrip().startswith(
            b"<"
        ):

            raise RuntimeError(
                f"{file_path.name} is not valid XML."
            )




    if file_path.suffix.lower() == ".csv":


        if b"," not in first_bytes:

            raise RuntimeError(
                f"{file_path.name} is not valid CSV."
            )



def download_file(
    url: str,
    save_path: Path,
):


    save_path.parent.mkdir(

        parents=True,

        exist_ok=True

    )



    temp_path = save_path.with_suffix(

        save_path.suffix + ".tmp"

    )



    try:


        print(
            f"Downloading {save_path.name}..."
        )



        response = requests.get(

            url,

            stream=True,

            timeout=60,

            headers={

                "User-Agent":
                "Compliance-Service/1.0"

            }

        )



        response.raise_for_status()


        content_type = response.headers.get(

            "content-type",

            ""

        ).lower()



        if (

            "text/html" in content_type

            and

            save_path.suffix.lower() != ".html"

        ):

            raise RuntimeError(

                f"{save_path.name} returned HTML instead of data."

            )

        with open(

            temp_path,

            "wb"

        ) as file:



            for chunk in response.iter_content(

                chunk_size=8192

            ):

                if chunk:

                    file.write(chunk)



        # Validate before replacing

        validate_download(

            temp_path

        )

        shutil.move(

            str(temp_path),

            str(save_path)

        )



        print(

            f"Downloaded {save_path.name}"

        )



    except Exception as error:


        print(

            f"Download failed for {save_path.name}: {error}"

        )


        raise



    finally:


        # Remove temporary file if failure happened

        if temp_path.exists():

            temp_path.unlink()


def download_all_lists():


    download_tasks = [


        (OFAC_DOWNLOAD_URL,
            OFAC_CSV_PATH),

       (UN_DOWNLOAD_URL,
            UN_XML_PATH),

        (EU_DOWNLOAD_URL,
            EU_XML_PATH),


    ]



    for url, path in download_tasks:


        download_file(

            url,

            path

        )



    print(

        "All sanctions lists downloaded successfully."

    )



    return True