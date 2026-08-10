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


sanction_index: dict[str, dict] = {}

search_keys: list[str] = []

prefix_index: dict[str, list[str]] = {}

two_char_index: dict[str, list[str]] = {}

first_char_index: dict[str, list[str]] = {}

_indexes_loaded = False



def merge_index_records(
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

   

    if not target.get("name"):
        target["name"] = source.get(
            "name"
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

    return target




def create_index_record(
    record: dict,
) -> dict:
    """
    Convert a deduplicated record into an index record.
    """

    return {
        "name": record["name"],
        "aliases": sorted(
            set(
                record.get(
                    "aliases",
                    [],
                )
            )
        ),
        "sources": sorted(
            set(
                record.get(
                    "sources",
                    [],
                )
            )
        ),
        "confidence": record.get(
            "confidence",
            100,
        ),
    }




def add_to_index(
    key: str,
    record: dict,
) -> None:
    

    if not key:
        return

    if len(key) < 3:
        return

    existing = sanction_index.get(
        key
    )

    if existing is None:

        sanction_index[key] = record

    else:

        sanction_index[key] = (
            merge_index_records(
                existing,
                record,
            )
        )




def build_prefix_index() -> None:
   

    prefix_index.clear()
    two_char_index.clear()
    first_char_index.clear()

    for key in search_keys:

        if not key:
            continue

      

        prefix = key[:3]

        prefix_index.setdefault(
            prefix,
            [],
        ).append(
            key
        )


        prefix_2 = key[:2]

        two_char_index.setdefault(
            prefix_2,
            [],
        ).append(
            key
        )

     

        first_char = key[0]

        first_char_index.setdefault(
            first_char,
            [],
        ).append(
            key
        )




def build_sanction_index(
    merged_records: dict,
) -> None:
    

    sanction_index.clear()



    for record in merged_records.values():

        indexed_record = create_index_record(
            record
        )

        main_key = normalize_name(
            indexed_record["name"]
        )

        if not main_key:
            continue

        if len(main_key) < 3:
            continue

        add_to_index(
            main_key,
            indexed_record,
        )

  

    for record in merged_records.values():

        indexed_record = create_index_record(
            record
        )

        for alias in indexed_record[
            "aliases"
        ]:

            alias_key = normalize_name(
                alias
            )

            if not alias_key:
                continue

            if len(alias_key) < 3:
                continue

            add_to_index(
                alias_key,
                indexed_record,
            )

   

    search_keys.clear()

    search_keys.extend(
        sanction_index.keys()
    )

   

    build_prefix_index()

    print(
        f"Index ready: {len(search_keys)}"
    )




def load_all_sanctions() -> None:
   

    global _indexes_loaded

    _indexes_loaded = False


    sanction_index.clear()
    search_keys.clear()
    prefix_index.clear()
    two_char_index.clear()
    first_char_index.clear()

  

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
                f"  - {file}"
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
        + un_records
        + eu_records
    )

    print(
        f"Total records: {len(all_records)}"
    )

  

    merged_records = deduplicate_entities(
        all_records,
        threshold=MATCH_THRESHOLD,
    )

    print(
        f"Merged entities: {len(merged_records)}"
    )


    build_sanction_index(
        merged_records
    )

    _indexes_loaded = True




def ensure_index_loaded() -> None:
   

    global _indexes_loaded

    if (
        not _indexes_loaded
        or not sanction_index
    ):
        load_all_sanctions()




def build_response(
    flagged: bool,
    record: dict | None,
    score: int,
    duration: float,
    entity_name: str | None = None,
) -> dict:
    


    if not flagged:

        return {
            "entity_name": entity_name,
            "is_flagged": False,
            "matched_lists": [],
            "matched_count": 0,
            "matched_name": None,
            "aliases": [],
            "match_score": 0,
            "confidence": 0.0,
            "duration_ms": round(
                duration,
                2,
            ),
        }

  

    sources = sorted(
        set(
            record.get(
                "sources",
                [],
            )
        )
    )

  
    aliases = sorted(
        set(
            record.get(
                "aliases",
                [],
            )
        )
    )

    

    return {
        "entity_name": entity_name,
        "is_flagged": True,
        "matched_lists": sources,
        "matched_count": len(sources),
        "matched_name": record.get(
            "name"
        ),
        "aliases": aliases,
        "match_score": int(score),
        "confidence": round(
            record.get(
                "confidence",
                100,
            ) / 100,
            2,
        ),
        "duration_ms": round(
            duration,
            2,
        ),
    }




def fuzzy_search(
    normalized: str,
):
   

    if not normalized:
        return None

   

    prefix = normalized[:3]

    candidates = prefix_index.get(
        prefix,
        [],
    )

    if candidates:

        return process.extractOne(
            normalized,
            candidates,
            scorer=fuzz.WRatio,
            score_cutoff=MATCH_THRESHOLD,
        )



    prefix_2 = normalized[:2]

    candidates = two_char_index.get(
        prefix_2,
        [],
    )

    if candidates:

        return process.extractOne(
            normalized,
            candidates,
            scorer=fuzz.WRatio,
            score_cutoff=MATCH_THRESHOLD,
        )

 

    first_char = normalized[0]

    candidates = first_char_index.get(
        first_char,
        [],
    )

    if not candidates:
        return None

    # Prevent a huge fuzzy search.
    candidates = candidates[:500]

    return process.extractOne(
        normalized,
        candidates,
        scorer=fuzz.WRatio,
        score_cutoff=MATCH_THRESHOLD,
    )




def screen_normalized_entity(
    normalized: str,
    original_name: str,
) -> dict:
    """
    Screen an already-normalized entity name.
    """

    start = time.perf_counter()

   

    record = sanction_index.get(
        normalized
    )

    if record is not None:

        duration = (
            time.perf_counter()
            - start
        ) * 1000

        return build_response(
            True,
            record,
            100,
            duration,
            original_name,
        )

  

    match = fuzzy_search(
        normalized
    )

    duration = (
        time.perf_counter()
        - start
    ) * 1000

    
    if not match:

        return build_response(
            False,
            None,
            0,
            duration,
            original_name,
        )

    matched_key = match[0]

    score = int(
        match[1]
    )

  

    record = sanction_index.get(
        matched_key
    )

    if record is None:

        return build_response(
            False,
            None,
            0,
            duration,
            original_name,
        )

   

    return build_response(
        True,
        record,
        score,
        duration,
        original_name,
    )




def screen_entity(
    name: str,
) -> dict:
    

    # Automatically load lists if required.
    ensure_index_loaded()

    normalized = normalize_name(
        name
    )

    if not normalized:

        return build_response(
            False,
            None,
            0,
            0,
            name,
        )

    return screen_normalized_entity(
        normalized,
        name,
    )




def screen_bulk(
    names: list[str],
) -> dict:
   

    ensure_index_loaded()

    start = time.perf_counter()

   

    results: list[dict | None] = [
        None
    ] * len(names)

   

    cache: dict[str, dict] = {}

   

    fuzzy_candidates: list[
        tuple[int, str, str]
    ] = []



    for position, name in enumerate(
        names
    ):

        normalized = normalize_name(
            name
        )

       

        if not normalized:

            results[position] = build_response(
                False,
                None,
                0,
                0,
                entity_name=name,
            )

            continue

       

        if normalized in cache:

            result = cache[
                normalized
            ].copy()

            result[
                "entity_name"
            ] = name

            results[position] = result

            continue

       

        record = sanction_index.get(
            normalized
        )

        if record is not None:

            result = build_response(
                True,
                record,
                100,
                0,
                entity_name=name,
            )

            cache[
                normalized
            ] = result

            results[position] = result

            continue

       

        fuzzy_candidates.append(
            (
                position,
                normalized,
                name,
            )
        )

  

    for (
        position,
        normalized,
        original_name,
    ) in fuzzy_candidates:

      

        if normalized in cache:

            result = cache[
                normalized
            ].copy()

            result[
                "entity_name"
            ] = original_name

            results[position] = result

            continue

      

        result = screen_normalized_entity(
            normalized,
            original_name,
        )


        cache[
            normalized
        ] = result

   

        results[position] = result

 

    final_results: list[dict] = []

    for index, result in enumerate(
        results
    ):

        if result is None:

            result = build_response(
                False,
                None,
                0,
                0,
                entity_name=names[index],
            )

        final_results.append(
            result
        )

 

    duration = (
        time.perf_counter()
        - start
    ) * 1000

    return {
        "count": len(names),
        "results": final_results,
        "total_duration_ms": round(
            duration,
            2,
        ),
    }