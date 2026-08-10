import json
import shutil
import time

from datetime import datetime


from app.core.config import (
    LOG_DIR,
    DATA_DIR,
)


from app.services.downloader_service import (
    download_all_lists,
)


from app.services.sanctions_service import (
    load_all_sanctions,
    sanction_index,
)


from app.services.refresh_service import (
    refresh_sanctions,
)




def write_refresh_log(message: str):

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    log_file = LOG_DIR / "refresh.log"


    with open(
        log_file,
        "a",
        encoding="utf-8",
    ) as file:


        file.write(
            f"{datetime.now()} : {message}\n"
        )



def archive_previous_downloads():

    download_dir = DATA_DIR / "downloads"

    archive_dir = DATA_DIR / "archive"



    if not download_dir.exists():

        print(
            "No downloads folder found"
        )

        return



    archive_dir.mkdir(
        parents=True,
        exist_ok=True,
    )



    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )



    archived = 0



    for file in download_dir.iterdir():


        if not file.is_file():

            continue



        destination = (

            archive_dir

            /

            f"{file.stem}_{timestamp}{file.suffix}"

        )



        try:


            shutil.move(

                str(file),

                str(destination)

            )


            archived += 1


            print(

                f"Archived: {file.name}"

            )


            write_refresh_log(

                f"Archived {file.name}"

            )



        except PermissionError:


            print(

                f"Skipped locked file: {file.name}"

            )


            write_refresh_log(

                f"Locked file skipped: {file.name}"

            )



        except Exception as error:


            print(

                f"Archive failed {file.name}: {error}"

            )


            write_refresh_log(

                f"Archive failed {file.name}: {error}"

            )



    print(

        f"Archived files: {archived}"

    )



def create_snapshot():


    snapshot = {}



    for key, record in sanction_index.items():


        snapshot[key] = {


            "name":
                record.get(
                    "name"
                ),


            "sources":
                record.get(
                    "sources",
                    []
                ),


            "confidence":
                record.get(
                    "confidence",
                    100
                ),

        }



    return snapshot



def print_changes(changes):


    added = changes.get(
        "added",
        []
    )


    removed = changes.get(
        "removed",
        []
    )


    print(
        "\nRefresh Summary"
    )


    print(
        "----------------------------"
    )


    print(
        f"Added   : {len(added)}"
    )


    print(
        f"Removed : {len(removed)}"
    )



    if added:


        print(
            "\nAdded Entities:"
        )


        for item in added[:20]:


            print(
                f" + {item}"
            )



        if len(added) > 20:


            print(

                f"... and {len(added)-20} more"

            )




    if removed:


        print(
            "\nRemoved Entities:"
        )


        for item in removed[:20]:


            print(
                f" - {item}"
            )



        if len(removed) > 20:


            print(

                f"... and {len(removed)-20} more"

            )



def run_refresh():


    start_time = time.perf_counter()



    print(

        "\nStarting sanctions refresh...\n"

    )


    write_refresh_log(

        "Refresh started"

    )



    try:



        print(

            "Archiving previous downloads..."

        )


        archive_previous_downloads()




        print(

            "\nDownloading latest sanctions lists..."

        )


        download_all_lists()



        print(

            "Download completed"

        )


        write_refresh_log(

            "Download completed"

        )



        print(

            "\nLoading sanctions data..."

        )


        load_all_sanctions()



        total_entities = len(

            sanction_index

        )



        print(

            f"Loaded entities: {total_entities}"

        )


        write_refresh_log(

            f"Loaded {total_entities} entities"

        )




        current_snapshot = create_snapshot()





        changes = refresh_sanctions(

            current_snapshot

        )



        write_refresh_log(

            json.dumps(

                changes,

                ensure_ascii=False

            )

        )




        print_changes(

            changes

        )



        duration = (

            time.perf_counter()

            -

            start_time

        ) * 1000



        print(

            f"\nRefresh completed successfully"

        )


        print(

            f"Duration: {round(duration,2)} ms"

        )



        write_refresh_log(

            "Refresh completed successfully"

        )



        return changes




    except Exception as error:


        print(

            f"\nRefresh failed: {error}"

        )


        write_refresh_log(

            f"Refresh failed: {error}"

        )


        raise






if __name__ == "__main__":

    run_refresh()