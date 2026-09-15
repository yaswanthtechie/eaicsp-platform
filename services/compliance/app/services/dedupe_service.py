
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
        name = name.replace(old, new)

    name = re.sub(
    r"[^\w\s]",
    " ",
    name,
    flags=re.UNICODE,
)

    return " ".join(name.split())


def create_bucket_key(name: str) -> str:
   

    normalized = normalize_name(name)

    if not normalized:
        return ""

    words = normalized.split()

    if len(words) >= 2:
        return (
            words[0][:3]
            + words[1][:3]
        )

    return words[0][:4]


def merge_records(
    target: dict,
    source: dict,
) -> dict:
   
    target_sources = set(
        target.get("sources", [])
    )

    source_sources = set(
        source.get("sources", [])
    )

    target["sources"] = sorted(
        target_sources | source_sources
    )

    target_aliases = set(
        target.get("aliases", [])
    )

    source_aliases = set(
        source.get("aliases", [])
    )

    target["aliases"] = sorted(
        target_aliases | source_aliases
    )

    target["confidence"] = max(
        int(
            target.get(
                "confidence",
                100,
            )
        ),
        int(
            source.get(
                "confidence",
                100,
            )
        ),
    )

    target_date = target.get(
        "listed_date"
    )

    source_date = source.get(
        "listed_date"
    )

    if target_date and source_date:

        if str(source_date) < str(target_date):
            target["listed_date"] = source_date

    elif source_date and not target_date:

        target["listed_date"] = source_date

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


def _find_exact_record(
    normalized_name: str,
    bucket_records: dict[str, dict],
):
   

    if normalized_name in bucket_records:
        return normalized_name

    return None


def _find_fuzzy_record(
    normalized_name: str,
    bucket_records: dict[str, dict],
    threshold: int,
):
   

    matched_key = None
    best_score = 0

    for existing_key in bucket_records:

      
        if normalized_name == existing_key:
            continue

        score = fuzz.WRatio(
            normalized_name,
            existing_key,
        )

        if score > best_score:
            best_score = score
            matched_key = existing_key

    if (
        matched_key is not None
        and best_score >= threshold
    ):
        return (
            matched_key,
            int(best_score),
        )

    return (
        None,
        0,
    )


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
        ).append(entity)

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


            exact_key = _find_exact_record(
                normalized,
                bucket_records,
            )

            if exact_key is not None:

                new_record = create_entity_record(
                    entity
                )

                bucket_records[
                    exact_key
                ] = merge_records(
                    bucket_records[
                        exact_key
                    ],
                    new_record,
                )

                continue



            comparisons += max(
                len(bucket_records),
                0,
            )

            (
                matched_key,
                best_score,
            ) = _find_fuzzy_record(
                normalized_name=normalized,
                bucket_records=bucket_records,
                threshold=threshold,
            )


            if matched_key is not None:

                existing_record = (
                    bucket_records[
                        matched_key
                    ]
                )

                new_record = (
                    create_entity_record(
                        entity
                    )
                )

                new_record["confidence"] = (
                    best_score
                )

                bucket_records[
                    matched_key
                ] = merge_records(
                    existing_record,
                    new_record,
                )


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

                final_records[
                    key
                ] = merge_records(
                    final_records[
                        key
                    ],
                    record,
                )

            else:

                final_records[
                    key
                ] = record

    print(
        f"Fuzzy comparisons performed: {comparisons}"
    )

    print(
        f"Merged entities: {len(final_records)}"
    )

    return final_records
