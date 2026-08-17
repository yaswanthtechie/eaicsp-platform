import re

from rapidfuzz import fuzz


def normalize_name(name: str) -> str:
    if not name:
        return ""

    name = name.upper().strip()

    replacements = {
        "PUBLIC LIMITED COMPANY": "PLC",
        "PUBLIC LIMITED": "PLC",
        "CORPORATION": "CORP",
        "COMPANY": "CO",
        "LIMITED": "LTD",
        "INCORPORATED": "INC",
        "&": "AND",
    }

    for old, new in replacements.items():
        name = name.replace(
            old,
            new,
        )

    name = re.sub(
        r"[^A-Z0-9 ]",
        " ",
        name,
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
    target: dict,
    source: dict,
) -> dict:



    target_sources = target.get(
        "sources",
        [],
    )

    source_sources = source.get(
        "sources",
        [],
    )

    target["sources"] = sorted(
        set(
            target_sources
            +
            source_sources
        )
    )

    target_aliases = target.get(
        "aliases",
        [],
    )

    source_aliases = source.get(
        "aliases",
        [],
    )

    target["aliases"] = sorted(
        set(
            target_aliases
            +
            source_aliases
        )
    )


    target["confidence"] = max(
        target.get(
            "confidence",
            100,
        ),
        source.get(
            "confidence",
            100,
        ),
    )



    target_date = target.get(
        "listed_date"
    )

    source_date = source.get(
        "listed_date"
    )

    if target_date and source_date:

        if source_date < target_date:
            target["listed_date"] = source_date

    elif source_date and not target_date:

        target["listed_date"] = source_date


    if not target.get("name"):
        target["name"] = source.get(
            "name"
        )

    return target



def create_entity_record(
    entity,
) -> dict:

    return {
        "name": entity.name,

        "aliases": sorted(
            set(
                entity.aliases or []
            )
        ),

        "sources": [
            entity.source
        ],

        "confidence": 100,

        "listed_date": entity.listed_date,
    }



def deduplicate_entities(
    entities,
    threshold: int = 90,
) -> dict:

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
            [],
        ).append(
            entity
        )

    print(
        f"Created buckets: {len(buckets)}"
    )

    final_records = {}



    for (
        bucket_key,
        bucket_entities,
    ) in buckets.items():

        bucket_records = {}

        for entity in bucket_entities:

            normalized = normalize_name(
                entity.name
            )

            if not normalized:
                continue

            if len(normalized) < 3:
                continue

            matched_key = None
            best_score = 0


            for existing_key in bucket_records:

                comparisons += 1

                score = fuzz.WRatio(
                    normalized,
                    existing_key,
                )

                if score > best_score:

                    best_score = score

                    matched_key = existing_key

            if (
                matched_key
                and best_score >= threshold
            ):

                existing_record = bucket_records[
                    matched_key
                ]

                new_record = create_entity_record(
                    entity
                )

                new_record["confidence"] = int(
                    best_score
                )

                merged_record = merge_records(
                    existing_record,
                    new_record,
                )

                bucket_records[
                    matched_key
                ] = merged_record

   

            else:

                bucket_records[
                    normalized
                ] = create_entity_record(
                    entity
                )


        for (
            key,
            record,
        ) in bucket_records.items():

            if key in final_records:

                final_records[key] = merge_records(
                    final_records[key],
                    record,
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