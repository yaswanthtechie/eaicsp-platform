import re

from rapidfuzz import fuzz


def normalize_name(name: str) -> str:

    if not name:
        return ""

    name = name.upper().strip()

    replacements = {

        "CORPORATION": "CORP",
        "COMPANY": "CO",
        "LIMITED": "LTD",
        "INCORPORATED": "INC",
        "PUBLIC LIMITED COMPANY": "PLC",
        "PUBLIC LIMITED": "PLC",
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


def create_bucket_key(name: str) -> str:

    normalized = normalize_name(name)

    if not normalized:
        return ""


    words = normalized.split()


    if len(words) >= 2:

        return (
            words[0][:3]
            +
            words[1][:3]
        )


    return words[0][:4]


def merge_records(
    target,
    source
):

    # Merge sources

    target["sources"] = sorted(
        list(
            set(
                target.get("sources", [])
                +
                source.get("sources", [])
            )
        )
    )


    # Merge aliases

    target["aliases"] = list(
        set(
            target.get("aliases", [])
            +
            source.get("aliases", [])
        )
    )


    # Keep highest confidence

    target["confidence"] = max(
        target.get(
            "confidence",
            100
        ),
        source.get(
            "confidence",
            100
        )
    )


    return target



def deduplicate_entities(
    entities,
    threshold=90
):

    buckets = {}

    comparisons = 0



    for entity in entities:


        key = create_bucket_key(
            entity.name
        )


        if not key:

            continue


        buckets.setdefault(
            key,
            []
        ).append(entity)



    print(
        f"Created buckets: {len(buckets)}"
    )



    final_records = {}



    for bucket_key, bucket_entities in buckets.items():


        bucket_records = {}



        for entity in bucket_entities:


            normalized = normalize_name(
                entity.name
            )


            if not normalized:
                continue


            if len(normalized) < 3:
                continue



            matched = None

            best_score = 0



            for existing_key, existing_record in bucket_records.items():


                comparisons += 1


                score = fuzz.WRatio(
                    normalized,
                    existing_key
                )


                if score > best_score:

                    best_score = score

                    matched = existing_key


            if (
                matched
                and
                best_score >= threshold
            ):


                existing_record = bucket_records[matched]


                # add source

                if entity.source not in existing_record["sources"]:

                    existing_record["sources"].append(
                        entity.source
                    )


                # add aliases

                for alias in entity.aliases:

                    if alias not in existing_record["aliases"]:

                        existing_record["aliases"].append(
                            alias
                        )


                # confidence

                existing_record["confidence"] = max(

                    existing_record["confidence"],

                    int(best_score)

                )


            else:


                bucket_records[normalized] = {


                    "name": entity.name,


                    "aliases": list(
                        entity.aliases
                    ),


                    "sources": [

                        entity.source

                    ],


                    "confidence": 100

                }


        for key, record in bucket_records.items():


            if key in final_records:


                final_records[key] = merge_records(

                    final_records[key],

                    record

                )


            else:

                final_records[key] = record



    print(
        f"Fuzzy comparisons performed: {comparisons}"
    )


    print(
        f"Merged entities: {len(final_records)}"
    )


    return final_records