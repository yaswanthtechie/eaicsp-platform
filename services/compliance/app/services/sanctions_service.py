from app.services.csv_reader import (
    load_sanctions
)

from app.services.entity_matching import (
    match_entity
)

from app.services.audit_service import (
    write_audit
)


from app.core.config import (

    OFAC_CSV_PATH,

    UN_CSV_PATH,

    AUDIT_LOG_PATH,

    MATCH_THRESHOLD

)

sanction_data = {}

def load_csv():

    global sanction_data

    sanction_data = load_sanctions(

        [

            (
                OFAC_CSV_PATH,
                "OFAC SDN",
                False,
                1
            ),

(
    UN_CSV_PATH,
    "UN Consolidated",
    True,
    1
)

        ]

    )

def check_name(name):

    if not name or not name.strip():

        return {

            "is_flagged": False,

            "matched_lists": [],

            "matched_name": None,

            "match_score": 0

        }
    result = match_entity(

        name,

        sanction_data,

        MATCH_THRESHOLD
    )
    flagged = (

        result["score"]

        >= MATCH_THRESHOLD

    )

    response = {

    "is_flagged": flagged,

    "matched_lists":
        result["matched_lists"]
        if flagged
        else [],

    "matched_name":
        result["matched_name"]
        if flagged
        else None,

    "match_score":
        result["score"]

}

    write_audit(

        AUDIT_LOG_PATH,

        {
            "input_name": name,
            **response
        }

    )
    return response