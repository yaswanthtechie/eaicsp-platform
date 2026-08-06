import json

from datetime import datetime

from app.core.config import (
    DATA_DIR,
    SNAPSHOT_FILE,
    LOG_DIR,
)


# =====================================================
# PATHS
# =====================================================

REFRESH_LOG_FILE = LOG_DIR / "refresh.log"



# =====================================================
# SAVE JSON
# =====================================================

def save_json(path, data):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4
        )



# =====================================================
# LOAD PREVIOUS SNAPSHOT
# =====================================================

def load_snapshot():

    if not SNAPSHOT_FILE.exists():

        return {}


    with open(
        SNAPSHOT_FILE,
        encoding="utf-8"
    ) as file:

        return json.load(file)



# =====================================================
# COMPARE SANCTIONS
# =====================================================

def compare_lists(
    old,
    new
):

    old_names = set(
        old.keys()
    )


    new_names = set(
        new.keys()
    )


    return {

        "added":
            list(
                new_names - old_names
            ),


        "removed":
            list(
                old_names - new_names
            )

    }



# =====================================================
# WRITE REFRESH LOG
# =====================================================

def write_log(message):

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    with open(
        REFRESH_LOG_FILE,
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            f"{datetime.now()} : {message}\n"
        )



# =====================================================
# REFRESH PROCESS
# =====================================================

def refresh_sanctions(current_data):


    old_data = load_snapshot()


    changes = compare_lists(
        old_data,
        current_data
    )


    write_log(
        f"Added: {changes['added']}"
    )


    write_log(
        f"Removed: {changes['removed']}"
    )


    save_json(
        SNAPSHOT_FILE,
        current_data
    )


    return changes