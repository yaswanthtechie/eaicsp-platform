import json

from datetime import datetime, timezone

from app.core.config import (
    SNAPSHOT_FILE,
    LOG_DIR,
)


def utc_now():

    return datetime.now(
        timezone.utc
    ).isoformat()


def save_snapshot(
    data: dict
):

    SNAPSHOT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    temp_file = SNAPSHOT_FILE.with_suffix(
        ".tmp"
    )


    with open(
        temp_file,
        "w",
        encoding="utf-8",
    ) as file:


        json.dump(
            data,
            file,
            indent=4,
        )


    temp_file.replace(
        SNAPSHOT_FILE
    )


def load_snapshot():

    if not SNAPSHOT_FILE.exists():

        return {}


    try:

        with open(
            SNAPSHOT_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)


    except json.JSONDecodeError:


        write_refresh_log(
            "Snapshot corrupted. Starting fresh."
        )


        return {}


def write_refresh_log(
    message: str
):

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
            f"{utc_now()} : {message}\n"
        )


def build_snapshot(
    sanction_index: dict
):

    snapshot = {}


    for key, record in sanction_index.items():


        snapshot[key] = {

            "name": record.get(
                "name"
            ),


            "sources": sorted(

                record.get(
                    "sources",
                    []
                )

            ),


            "confidence": record.get(
                "confidence",
                100
            )

        }


    return snapshot



def compare_snapshots(
    previous: dict,
    current: dict,
):


    previous_keys = set(
        previous.keys()
    )


    current_keys = set(
        current.keys()
    )


    added = sorted(
        current_keys - previous_keys
    )


    removed = sorted(
        previous_keys - current_keys
    )


    return {

        "added": added,

        "removed": removed,

        "timestamp": utc_now(),

    }



def refresh_sanctions(
    current_snapshot: dict
):


    previous_snapshot = load_snapshot()


    changes = compare_snapshots(

        previous_snapshot,

        current_snapshot,

    )


    write_refresh_log(
        "Refresh comparison completed"
    )


    write_refresh_log(
        f"Added entities: {len(changes['added'])}"
    )


    write_refresh_log(
        f"Removed entities: {len(changes['removed'])}"
    )


    # Avoid huge log files

    if changes["added"]:


        write_refresh_log(
            f"First added entities: {changes['added'][:20]}"
        )


    if changes["removed"]:


        write_refresh_log(
            f"First removed entities: {changes['removed'][:20]}"
        )



    save_snapshot(
        current_snapshot
    )


    return changes