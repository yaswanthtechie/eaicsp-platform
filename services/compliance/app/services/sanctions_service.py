import time

from rapidfuzz import fuzz, process

from app.core.config import (
    OFAC_CSV_PATH,
    UN_XML_PATH,
    EU_XML_PATH,
    MATCH_THRESHOLD,
)

from app.services.sources.ofac import load_ofac
from app.services.sources.un import load_un
from app.services.sources.eu import load_eu

from app.services.dedupe_service import normalize_name




sanction_index = {}

search_keys = []



def load_all_sanctions():

    global sanction_index
    global search_keys


    sanction_index.clear()
    search_keys.clear()


    print("Loading OFAC")

    ofac_records = load_ofac(
        OFAC_CSV_PATH
    )


    print(
        f"Loaded {len(ofac_records)} OFAC records"
    )


    print("Loading UN")

    un_records = load_un(
        UN_XML_PATH
    )


    print(
        f"Loaded {len(un_records)} UN records"
    )


    print("Loading EU")

    eu_records = load_eu(
        EU_XML_PATH
    )


    print(
        f"Loaded {len(eu_records)} EU records"
    )


    all_records = (
        ofac_records
        +
        un_records
        +
        eu_records
    )


    print(
        f"Total sanctions records: {len(all_records)}"
    )




    for entity in all_records:


        names = []


        if entity.name:

            names.append(
                entity.name
            )


        if entity.aliases:

            names.extend(
                entity.aliases
            )



        for current_name in names:


            key = normalize_name(current_name)
            if not key:
                continue
            if len(key) < 3:
                continue



            source = entity.source.upper()



            if key not in sanction_index:


                sanction_index[key] = {


                    "name":
                        current_name,


                    "sources":
                        [
                            source
                        ],


                    "aliases":
                        []

                }



            else:


                if source not in sanction_index[key]["sources"]:

                    sanction_index[key]["sources"].append(
                        source
                    )



    search_keys.extend(
        sanction_index.keys()
    )


    print(
        f"Sanctions index ready: {len(search_keys)}"
    )



def build_response(
        flagged,
        record,
        score,
        duration
):


    if not flagged:

        return {

            "is_flagged": False,

            "matched_lists": [],

            "matched_name": None,

            "match_score":0,

            "confidence":0.0,

            "duration_ms":round(duration,2)

        }



    return {

        "is_flagged":True,

        "matched_lists":
            record["sources"],

        "matched_name":
            record["name"],

        "match_score":
            score,

        "confidence":
            round(score/100,2),

        "duration_ms":
            round(duration,2)

    }


def screen_entity(
        name:str
):


    start=time.perf_counter()



    normalized = normalize_name(
        name
    )


    if not normalized:


        return build_response(
            False,
            None,
            0,
            0
        )



    if normalized in sanction_index:


        duration=(

            time.perf_counter()
            -
            start

        )*1000


        return build_response(

            True,

            sanction_index[normalized],

            100,

            duration

        )



    match = process.extractOne(

        normalized,

        search_keys,

        scorer=fuzz.WRatio

    )



    duration=(

        time.perf_counter()
        -
        start

    )*1000



    if match:
        matched_key = match[0]
    score = int(match[1])

    if len(matched_key) < 3:
        return build_response(
            False,
            None,
            0,
            duration
        )

    if score >= MATCH_THRESHOLD:

        record = sanction_index[matched_key]

        return build_response(
            True,
            record,
            score,
            duration
        )
    return build_response(
    False,
    None,
    0,
    duration
)





def screen_bulk(
        names:list[str]
):


    start=time.perf_counter()


    results=[]


    for name in names:


        results.append(

            screen_entity(
                name
            )

        )



    duration=(

        time.perf_counter()
        -
        start

    )*1000



    return {


        "count":
            len(names),


        "results":
            results,


        "total_duration_ms":
            round(duration,2)

    }