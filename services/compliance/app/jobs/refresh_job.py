import json
from datetime import datetime

from app.services.downloader_service import (
    download_all_lists
)

from app.services.sanctions_service import (
    load_all_sanctions,
    sanction_index
)

from app.services.refresh_service import (
    refresh_sanctions
)

from app.core.config import (
    LOG_DIR
)



# =====================================================
# WRITE REFRESH LOG
# =====================================================

def write_refresh_log(message: str):

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    log_file = LOG_DIR / "refresh.log"


    with open(
        log_file,
        "a",
        encoding="utf-8"
    ) as file:

        file.write(

            f"{datetime.now()} : {message}\n"

        )



# =====================================================
# CREATE SNAPSHOT DATA
# =====================================================

def create_snapshot():

    snapshot = {}


    for name, data in sanction_index.items():


        snapshot[name] = {


            "sources":
                data["sources"],


            "matched_name":
                data["name"]

        }


    return snapshot



# =====================================================
# DAILY REFRESH JOB
# =====================================================

def run_refresh():


    try:

        write_refresh_log(
            "Starting sanctions refresh"
        )


        print(
            "Starting sanctions refresh"
        )


        # -------------------------------------------------
        # STEP 1
        # Download latest OFAC / UN / EU files
        # -------------------------------------------------

        download_all_lists()


        write_refresh_log(
            "Downloaded latest sanctions files"
        )


        print(
            "Download completed"
        )



        # -------------------------------------------------
        # STEP 2
        # Reload sanctions into memory
        # -------------------------------------------------

        load_all_sanctions()


        write_refresh_log(
            f"Loaded {len(sanction_index)} entities"
        )


        print(
            f"Loaded {len(sanction_index)} entities"
        )



        # -------------------------------------------------
        # STEP 3
        # Create current snapshot
        # -------------------------------------------------

        current_snapshot = create_snapshot()



        # -------------------------------------------------
        # STEP 4
        # Compare with previous snapshot
        # -------------------------------------------------

        changes = refresh_sanctions(
            current_snapshot
        )



        write_refresh_log(
            json.dumps(
                changes
            )
        )


        print(
            "Refresh completed"
        )


        print(
            json.dumps(
                changes,
                indent=4
            )
        )



        return changes



    except Exception as error:


        write_refresh_log(
            f"FAILED : {str(error)}"
        )


        print(
            f"Refresh failed : {error}"
        )


        raise



# =====================================================
# SCRIPT EXECUTION
# =====================================================

if __name__ == "__main__":

    run_refresh()