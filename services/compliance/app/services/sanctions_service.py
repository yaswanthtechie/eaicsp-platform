import csv
import json
from pathlib import Path
from datetime import datetime, timezone

from rapidfuzz import process, fuzz

from app.core.config import (
    OFAC_CSV_PATH,
    UN_CSV_PATH,
    AUDIT_LOG_PATH,
    MATCH_THRESHOLD,
)



sanction_data = {}


def load_csv():

    sanction_data.clear()

    files = [
        (OFAC_CSV_PATH, "OFAC SDN"),
        (UN_CSV_PATH, "UN")
    ]

    total = 0

    for file_path, source in files:

        path = Path(file_path)

        if not path.exists():
            raise RuntimeError(
                f"Missing sanctions file: {path}"
            )

        with path.open(
            mode="r",
            encoding="utf-8",
            newline=""
        ) as file:

            reader = csv.reader(file)

            
            next(reader, None)

            for row in reader:

                
                if len(row) < 2:
                    continue

                name = row[1].strip()

                
                if not name:
                    continue

                
                if name not in sanction_data:

                    sanction_data[name] = source
                    total += 1

    if total == 0:

        raise RuntimeError(
            "No sanctions loaded. Service startup aborted."
        )

    print(f"Loaded {total} sanction names")




def write_audit(
    input_name,
    matched_name,
    score,
    flagged,
    matched_lists
):

    log_path = Path(AUDIT_LOG_PATH)

    log_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    record = {

        "timestamp":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "input_name": input_name,

        "matched_name": matched_name,

        "match_score": score,

        "is_flagged": flagged,

        "matched_lists": matched_lists

    }

    try:

        with log_path.open(
            "a",
            encoding="utf-8"
        ) as log:

            log.write(
                json.dumps(record)
            )

            log.write("\n")

    except Exception as e:

        print(
            f"Audit Log Error : {e}"
        )




def check_name(name):

    if not name or not name.strip():

        return {

            "is_flagged": False,

            "matched_lists": [],

            "matched_name": "",

            "match_score": 0

        }

    input_name = name.strip()

 

    for sanction_name, source in sanction_data.items():

        if sanction_name.lower() == input_name.lower():

            write_audit(
                input_name,
                sanction_name,
                100,
                True,
                [source]
            )

            return {

                "is_flagged": True,

                "matched_lists": [source],

                "matched_name": sanction_name,

                "match_score": 100

            }



    match = process.extractOne(

        query=input_name,

        choices=sanction_data.keys(),

        scorer=fuzz.WRatio

    )

    if match:

        matched_name = match[0]

        score = int(match[1])

        source = sanction_data[matched_name]

    else:

        matched_name = ""

        score = 0

        source = None

    flagged = score >= MATCH_THRESHOLD

    matched_lists = [source] if flagged else []

    write_audit(

        input_name,

        matched_name,

        score,

        flagged,

        matched_lists

    )

    return {

        "is_flagged": flagged,

        "matched_lists": matched_lists,

        "matched_name": matched_name,

        "match_score": score

    }