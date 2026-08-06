import time
from pathlib import Path

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


from app.services.dedupe_service import (
    normalize_name,
    deduplicate_entities,
)


from app.services.downloader_service import (
    download_all_lists,
)



sanction_index = {}

search_keys = []



def load_all_sanctions():

    global sanction_index
    global search_keys


    sanction_index.clear()
    search_keys.clear()



    required_files = [

        Path(OFAC_CSV_PATH),
        Path(UN_XML_PATH),
        Path(EU_XML_PATH),

    ]


    missing = [

        str(file)

        for file in required_files

        if not file.exists()

    ]



    if missing:


        print(
            "Missing sanctions files:"
        )


        for file in missing:

            print(
                file
            )


        print(
            "Downloading sanctions lists..."
        )


        download_all_lists()


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


    if not all_records:


        raise RuntimeError(

            "No sanctions loaded. Startup aborted."

        )



    merged_records = deduplicate_entities(

        all_records,

        threshold=MATCH_THRESHOLD

    )



    print(
        f"Merged entities: {len(merged_records)}"
    )



    for _, record in merged_records.items():


        main_key = normalize_name(
            record["name"]
        )



        if not main_key:

            continue



        if len(main_key) < 3:

            continue



        indexed_record = {


            "name": record["name"],


            "sources": sorted(

                list(

                    set(

                        record.get(
                            "sources",
                            []

                        )

                    )

                )

            ),


            "aliases": list(

                set(

                    record.get(
                        "aliases",
                        []

                    )

                )

            ),


            "confidence": record.get(

                "confidence",

                100

            )

        }



        sanction_index[main_key] = indexed_record



        for alias in indexed_record["aliases"]:


            alias_key = normalize_name(
                alias
            )


            if not alias_key:

                continue


            if len(alias_key) < 3:

                continue



            if alias_key in sanction_index:


                existing = sanction_index[alias_key]


                existing["sources"] = sorted(

                    list(

                        set(

                            existing["sources"]

                            +

                            indexed_record["sources"]

                        )

                    )

                )


            else:


                sanction_index[alias_key] = indexed_record





    search_keys.extend(

        sanction_index.keys()

    )



    print(

        f"Sanctions index ready: {len(search_keys)}"

    )



    if not search_keys:


        raise RuntimeError(

            "Sanctions index empty. Startup aborted."

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


            "matched_count": 0,


            "matched_name": None,


            "match_score": 0,


            "confidence": 0,


            "duration_ms": round(

                duration,

                2

            )

        }



    sources = sorted(

        list(

            set(

                record.get(

                    "sources",

                    []

                )

            )

        )

    )



    return {


        "is_flagged": True,


        "matched_lists": sources,


        "matched_count": len(sources),


        "matched_name": record["name"],


        "match_score": score,


        "confidence": round(

            record.get(

                "confidence",

                100

            )

            /

            100,

            2

        ),


        "duration_ms": round(

            duration,

            2

        )

    }



def screen_entity(name: str):


    start = time.perf_counter()



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



    # EXACT MATCH

    if normalized in sanction_index:


        duration = (

            time.perf_counter()

            -

            start

        ) * 1000



        return build_response(

            True,

            sanction_index[normalized],

            100,

            duration

        )



    if not search_keys:


        return build_response(

            False,

            None,

            0,

            0

        )



    match = process.extractOne(

        normalized,

        search_keys,

        scorer=fuzz.WRatio

    )



    duration = (

        time.perf_counter()

        -

        start

    ) * 1000



    if not match:


        return build_response(

            False,

            None,

            0,

            duration

        )



    matched_key = match[0]

    score = int(match[1])



    if score < MATCH_THRESHOLD:


        return build_response(

            False,

            None,

            0,

            duration

        )



    record = sanction_index.get(
        matched_key
    )



    if not record:


        return build_response(

            False,

            None,

            0,

            duration

        )



    return build_response(

        True,

        record,

        score,

        duration

    )


def screen_bulk(
    names: list[str]
):

    start = time.perf_counter()

    results = []

    cache = {}

    fuzzy_candidates = []


    for name in names:

        normalized = normalize_name(
            name
        )


        if not normalized:

            results.append(
                build_response(
                    False,
                    None,
                    0,
                    0
                )
            )

            continue


        # exact match first

        if normalized in sanction_index:

            results.append(

                build_response(

                    True,

                    sanction_index[normalized],

                    100,

                    0

                )

            )

            continue



        if normalized in cache:

            results.append(
                cache[normalized]
            )

        else:

            fuzzy_candidates.append(
                normalized
            )

    for name in fuzzy_candidates:


        result = screen_entity(
            name
        )


        cache[name] = result

        results.append(
            result
        )


    duration = (

        time.perf_counter()

        -

        start

    ) * 1000



    return {

        "count": len(names),

        "results": results,

        "total_duration_ms": round(
            duration,
            2
        )

    }


def get_index_statistics():

    return {


        "indexed_entities": len(search_keys),


        "unique_records": len(sanction_index)

    }



def reload_sanctions():

    load_all_sanctions()


    return {


        "status": "success",


        "indexed_entities": len(search_keys)

    }



def startup_check():

    if not sanction_index:

        load_all_sanctions()