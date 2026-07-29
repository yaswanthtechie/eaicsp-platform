import re

from rapidfuzz import (
    fuzz,
    process
)



def normalize_name(name):

    if not name:

        return ""


    name = name.upper()



    replacements = {

        "CORPORATION": "CORP",

        "LIMITED": "LTD",

        "COMPANY": "CO",

        "INCORPORATED": "INC"

    }



    for old, new in replacements.items():

        name = name.replace(
            old,
            new
        )



    name = re.sub(
        r"[^A-Z0-9 ]",
        "",
        name
    )


    return " ".join(
        name.split()
    )





def match_entity(
    input_name,
    sanction_data,
    threshold
):


    normalized_input = normalize_name(
        input_name
    )



    # Exact match first

    for entity, sources in sanction_data.items():


        if normalize_name(entity) == normalized_input:


            return {

                "matched_name": entity,

                "matched_lists": sources,

                "score": 100

            }





    normalized_entities = {

        normalize_name(entity): entity

        for entity in sanction_data

    }



    result = process.extractOne(

        normalized_input,

        normalized_entities.keys(),

        scorer=fuzz.WRatio,

        score_cutoff=threshold

    )



    if not result:


        return {

            "matched_name": None,

            "matched_lists": [],

            "score": 0

        }





    matched_entity = normalized_entities[
        result[0]
    ]



    return {

        "matched_name": matched_entity,

        "matched_lists":
            sanction_data[matched_entity],

        "score":
            int(result[1])

    }