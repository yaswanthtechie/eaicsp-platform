import re

from rapidfuzz import fuzz


def normalize_name(name: str) -> str:

    if not name:
        return ""

    name = name.upper()


    replacements = {

        "CORPORATION": "CORP",
        "COMPANY": "CO",
        "LIMITED": "LTD",
        "INCORPORATED": "INC",
        "PUBLIC LIMITED COMPANY": "PLC",
        "&": "AND",

    }


    for old, new in replacements.items():

        name = name.replace(
            old,
            new
        )


    name = re.sub(
        r"[^A-Z0-9 ]",
        " ",
        name
    )


    return " ".join(
        name.split()
    )




def create_bucket_key(name: str):

    normalized = normalize_name(name)


    if not normalized:

        return ""


    words = normalized.split()


    return words[0][:4]




def calculate_similarity(
        entity1,
        entity2
):

    names = [

        normalize_name(entity1.name),

        normalize_name(entity2.name)

    ]


    scores = [

        fuzz.WRatio(
            names[0],
            names[1]
        )

    ]


    # compare aliases also

    for alias1 in entity1.aliases:

        for alias2 in entity2.aliases:

            scores.append(

                fuzz.WRatio(

                    normalize_name(alias1),

                    normalize_name(alias2)

                )

            )


    return max(scores)



def deduplicate_entities(
        entities,
        threshold=90
):

    buckets = {}



    for entity in entities:


        key = create_bucket_key(
            entity.name
        )


        if key not in buckets:

            buckets[key] = []


        buckets[key].append(
            entity
        )



    merged = {}



    for bucket in buckets.values():


        for entity in bucket:


            normalized = normalize_name(
                entity.name
            )


            if not normalized:

                continue



            matched_key = None

            best_score = 0



            for key, record in merged.items():


                score = fuzz.WRatio(

                    normalized,

                    normalize_name(
                        record["name"]
                    )

                )


                if score > best_score:

                    best_score = score

                    matched_key = key




            if best_score >= threshold:


                record = merged[
                    matched_key
                ]


                if entity.source not in record["sources"]:

                    record["sources"].append(
                        entity.source
                    )



                for alias in entity.aliases:


                    if alias not in record["aliases"]:

                        record["aliases"].append(
                            alias
                        )


                record["confidence"] = max(

                    record["confidence"],

                    int(best_score)

                )





            else:


                merged[normalized] = {


                    "name":
                        entity.name,


                    "aliases":
                        list(entity.aliases),


                    "sources":
                        [
                            entity.source
                        ],


                    "confidence":
                        100

                }



    return merged