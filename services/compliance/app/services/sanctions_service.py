import time
from pathlib import Path
from typing import Any

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

from app.services.risk_score_service import (
    calculate_risk_score,
    calculate_country_risk,
    calculate_overall_supplier_risk,
)



sanction_index: dict[str, dict[str, Any]] = {}

search_keys: list[str] = []

prefix_index: dict[str, list[str]] = {}
two_char_index: dict[str, list[str]] = {}
first_char_index: dict[str, list[str]] = {}

_indexes_loaded: bool = False


MAX_FALLBACK_CANDIDATES = 500
MIN_SEARCH_KEY_LENGTH = 3


def _normalize_sources(
    sources: Any,
) -> list[str]:
   

    if not sources:
        return []

    if isinstance(sources, str):
        sources = [sources]

    normalized = {
        str(source).strip().upper()
        for source in sources
        if source is not None
        and str(source).strip()
    }

    return sorted(normalized)


def _normalize_aliases(
    aliases: Any,
) -> list[str]:
    

    if not aliases:
        return []

    if isinstance(aliases, str):
        aliases = [aliases]

    normalized = {
        str(alias).strip()
        for alias in aliases
        if alias is not None
        and str(alias).strip()
    }

    return sorted(normalized)


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
   

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    

    return max(
        minimum,
        min(value, maximum),
    )



def merge_index_records(
    target: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    


    target_sources = set(
        _normalize_sources(
            target.get("sources", [])
        )
    )

    source_sources = set(
        _normalize_sources(
            source.get("sources", [])
        )
    )

    target["sources"] = sorted(
        target_sources | source_sources
    )


    target_aliases = set(
        _normalize_aliases(
            target.get("aliases", [])
        )
    )

    source_aliases = set(
        _normalize_aliases(
            source.get("aliases", [])
        )
    )

    target["aliases"] = sorted(
        target_aliases | source_aliases
    )

   

    if not target.get("name"):
        target["name"] = source.get("name")

  

    target_confidence = _safe_float(
        target.get("confidence", 100),
        100.0,
    )

    source_confidence = _safe_float(
        source.get("confidence", 100),
        100.0,
    )

    target["confidence"] = max(
        target_confidence,
        source_confidence,
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



def create_index_record(
    record: dict[str, Any],
) -> dict[str, Any]:
  
    confidence = _safe_float(
        record.get("confidence", 100),
        100.0,
    )

    return {
        "name": record.get("name"),

        "aliases": _normalize_aliases(
            record.get("aliases", [])
        ),

        "sources": _normalize_sources(
            record.get("sources", [])
        ),

        "confidence": _clamp(
            confidence
        ),

        "listed_date": record.get(
            "listed_date"
        ),
    }




def add_to_index(
    key: str,
    record: dict[str, Any],
) -> None:
    

    if not key:
        return

    if len(key) < MIN_SEARCH_KEY_LENGTH:
        return

    existing = sanction_index.get(
        key
    )

    if existing is None:

        sanction_index[key] = record

        return

    sanction_index[key] = merge_index_records(
        existing,
        record,
    )



def build_prefix_index() -> None:
   

    prefix_index.clear()
    two_char_index.clear()
    first_char_index.clear()

    for key in search_keys:

        if not key:
            continue



        if len(key) >= 3:

            prefix_index.setdefault(
                key[:3],
                [],
            ).append(key)

    
        if len(key) >= 2:

            two_char_index.setdefault(
                key[:2],
                [],
            ).append(key)

  

        first_char_index.setdefault(
            key[0],
            [],
        ).append(key)




def build_sanction_index(
    merged_records: dict[str, dict[str, Any]],
) -> None:
   

    sanction_index.clear()
    search_keys.clear()

    prefix_index.clear()
    two_char_index.clear()
    first_char_index.clear()

  

    for record in merged_records.values():

        indexed_record = create_index_record(
            record
        )

        name = indexed_record.get(
            "name"
        )

        normalized_name = normalize_name(
            name or ""
        )

        if len(normalized_name) < MIN_SEARCH_KEY_LENGTH:
            continue

        add_to_index(
            normalized_name,
            indexed_record,
        )

  

    for record in merged_records.values():

        indexed_record = create_index_record(
            record
        )

        aliases = indexed_record.get(
            "aliases",
            [],
        )

        for alias in aliases:

            normalized_alias = normalize_name(
                alias
            )

            if len(normalized_alias) < MIN_SEARCH_KEY_LENGTH:
                continue

            add_to_index(
                normalized_alias,
                indexed_record,
            )



    search_keys.extend(
        sanction_index.keys()
    )

  

    build_prefix_index()

    print(
        f"Index ready: {len(search_keys)}"
    )




def _clear_indexes() -> None:
  
    global _indexes_loaded

    sanction_index.clear()
    search_keys.clear()

    prefix_index.clear()
    two_char_index.clear()
    first_char_index.clear()

    _indexes_loaded = False




def load_all_sanctions() -> None:
   

    global _indexes_loaded

    _clear_indexes()

    required_files = [
        Path(OFAC_CSV_PATH),
        Path(UN_XML_PATH),
        Path(EU_XML_PATH),
    ]

   

    missing_files = [
        file
        for file in required_files
        if not file.exists()
    ]

    if missing_files:

        print(
            "Missing sanctions files:"
        )

        for file in missing_files:

            print(
                f"  - {file}"
            )

        print(
            "Downloading sanctions lists..."
        )

        download_all_lists()



    missing_after_download = [
        file
        for file in required_files
        if not file.exists()
    ]

    if missing_after_download:

        raise FileNotFoundError(
            "Required sanctions files are missing: "
            + ", ".join(
                str(file)
                for file in missing_after_download
            )
        )

  

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




def refresh_sanctions_data() -> None:
   

    print(
        "Refreshing sanctions data..."
    )

    download_all_lists()

    load_all_sanctions()

    print(
        "Sanctions data refresh completed."
    )




def ensure_index_loaded() -> None:
   

    if (
        not _indexes_loaded
        or not sanction_index
    ):

        load_all_sanctions()



def build_clean_response(
    duration: float,
    entity_name: str | None,
    country: str | None,
) -> dict[str, Any]:
   

    country_risk_score = _clamp(
        _safe_float(
            calculate_country_risk(
                country
            )
        )
    )

    sanctions_risk_score = 0.0

    overall_supplier_risk = _clamp(
        _safe_float(
            calculate_overall_supplier_risk(
                sanctions_risk_score,
                country_risk_score,
            )
        )
    )

    return {
        "entity_name": entity_name,

        "is_flagged": False,

        "matched_lists": [],

        "matched_count": 0,

        "matched_name": None,

        "aliases": [],

        "match_score": 0,

        "confidence": 0.0,

        "risk_score": 0.0,

        "risk_factors": {
            "match_confidence": 0.0,
            "source_coverage": 0.0,
            "recency": 0.0,
        },

        "country_risk_score": round(
            country_risk_score,
            2,
        ),

        "overall_supplier_risk": round(
            overall_supplier_risk,
            2,
        ),

        "duration_ms": max(
            round(
                _safe_float(duration),
                2,
            ),
            0.0,
        ),

        "source": [],

        "override_applied": False,

        "override_reason": None,

        "reviewed_by": None,

        "screening_type": "INITIAL",

        "newly_flagged": False,

        "screening_run_id": None,
    }




def build_matched_response(
    record: dict[str, Any],
    score: int,
    duration: float,
    entity_name: str | None,
    country: str | None,
) -> dict[str, Any]:
   

   

    sources = _normalize_sources(
        record.get(
            "sources",
            [],
        )
    )



    aliases = _normalize_aliases(
        record.get(
            "aliases",
            [],
        )
    )


    confidence_value = _clamp(
        _safe_float(
            record.get(
                "confidence",
                100,
            ),
            100.0,
        )
    )

    confidence = round(
        confidence_value / 100.0,
        2,
    )



    matched_name = record.get(
        "name"
    )

    listed_date = record.get(
        "listed_date"
    )


    risk_result = calculate_risk_score(
        match_score=score,
        matched_sources=sources,
        listed_date=listed_date,
    )

    sanctions_risk_score = _clamp(
        _safe_float(
            risk_result.get(
                "risk_score",
                0,
            )
        )
    )


    country_risk_score = _clamp(
        _safe_float(
            calculate_country_risk(
                country
            )
        )
    )



    overall_supplier_risk = _clamp(
        _safe_float(
            calculate_overall_supplier_risk(
                sanctions_risk_score,
                country_risk_score,
            )
        )
    )


    risk_factors = risk_result.get(
        "risk_factors",
        {},
    )

    match_confidence = _clamp(
        _safe_float(
            risk_factors.get(
                "match_confidence",
                0,
            )
        )
    )

    source_coverage = _clamp(
        _safe_float(
            risk_factors.get(
                "source_coverage",
                0,
            )
        )
    )

    recency = _clamp(
        _safe_float(
            risk_factors.get(
                "recency",
                0,
            )
        )
    )



    return {
        "entity_name": entity_name,

        "is_flagged": True,

        "matched_lists": sources,

        "matched_count": len(sources),

        "matched_name": matched_name,

        "aliases": aliases,

        "match_score": max(
            0,
            min(
                int(score),
                100,
            ),
        ),

        "confidence": confidence,

        "risk_score": round(
            sanctions_risk_score,
            2,
        ),

        "risk_factors": {
            "match_confidence": round(
                match_confidence,
                2,
            ),

            "source_coverage": round(
                source_coverage,
                2,
            ),

            "recency": round(
                recency,
                2,
            ),
        },

        "country_risk_score": round(
            country_risk_score,
            2,
        ),

        "overall_supplier_risk": round(
            overall_supplier_risk,
            2,
        ),

        "duration_ms": max(
            round(
                _safe_float(duration),
                2,
            ),
            0.0,
        ),

        "source": sources,

        "override_applied": False,

        "override_reason": None,

        "reviewed_by": None,

        "screening_type": "INITIAL",

        "newly_flagged": False,

        "screening_run_id": None,
    }




def build_response(
    flagged: bool,
    record: dict[str, Any] | None,
    score: int,
    duration: float,
    entity_name: str | None = None,
    country: str | None = None,
) -> dict[str, Any]:
    

    if (
        not flagged
        or record is None
    ):

        return build_clean_response(
            duration=duration,
            entity_name=entity_name,
            country=country,
        )

    return build_matched_response(
        record=record,
        score=score,
        duration=duration,
        entity_name=entity_name,
        country=country,
    )




def _get_fuzzy_candidates(
    normalized: str,
) -> list[str]:
    

    if not normalized:
        return []


    if len(normalized) >= 3:

        candidates = prefix_index.get(
            normalized[:3],
            [],
        )

        if candidates:
            return candidates


    if len(normalized) >= 2:

        candidates = two_char_index.get(
            normalized[:2],
            [],
        )

        if candidates:
            return candidates

   
    candidates = first_char_index.get(
        normalized[0],
        [],
    )

    if candidates:

        return candidates[
            :MAX_FALLBACK_CANDIDATES
        ]


    return search_keys[
        :MAX_FALLBACK_CANDIDATES
    ]



def fuzzy_search(
    normalized: str,
):
   

    if not normalized:
        return None

    candidates = _get_fuzzy_candidates(
        normalized
    )

    if not candidates:
        return None

    return process.extractOne(
        normalized,
        candidates,
        scorer=fuzz.WRatio,
        score_cutoff=MATCH_THRESHOLD,
    )



def screen_normalized_entity(
    normalized: str,
    original_name: str,
    country: str | None = None,
) -> dict[str, Any]:
    """
    Screen a normalized entity name.
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
            flagged=True,
            record=record,
            score=100,
            duration=duration,
            entity_name=original_name,
            country=country,
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
            flagged=False,
            record=None,
            score=0,
            duration=duration,
            entity_name=original_name,
            country=country,
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
            flagged=False,
            record=None,
            score=0,
            duration=duration,
            entity_name=original_name,
            country=country,
        )

    return build_response(
        flagged=True,
        record=record,
        score=score,
        duration=duration,
        entity_name=original_name,
        country=country,
    )



def _validate_entity_name(
    name: str,
) -> None:
   

    if name is None:

        raise ValueError(
            "entity_name must not be null"
        )

    if not isinstance(
        name,
        str,
    ):

        raise ValueError(
            "entity_name must be a string"
        )

    if not name.strip():

        raise ValueError(
            "entity_name must not be blank"
        )




def screen_entity(
    name: str,
    country: str | None = None,
) -> dict[str, Any]:
  

    _validate_entity_name(
        name
    )


    ensure_index_loaded()


    normalized = normalize_name(
        name
    )



    if not normalized:

        return build_clean_response(
            duration=0,
            entity_name=name,
            country=country,
        )

  

    return screen_normalized_entity(
        normalized=normalized,
        original_name=name,
        country=country,
    )



def screen_bulk(
    names: list[str],
    country: str | None = None,
) -> dict[str, Any]:
    

  

    if names is None:

        raise ValueError(
            "entity_names must not be null"
        )

    if not isinstance(
        names,
        list,
    ):

        raise ValueError(
            "entity_names must be a list"
        )

    if not names:

        raise ValueError(
            "entity_names must contain at least one item"
        )

 

    for name in names:

        _validate_entity_name(
            name
        )

  

    ensure_index_loaded()

    start = time.perf_counter()

    results: list[
        dict[str, Any] | None
    ] = [None] * len(names)



    cache: dict[
        str,
        dict[str, Any],
    ] = {}

    fuzzy_items: list[
        tuple[int, str, str]
    ] = []



    for position, name in enumerate(
        names
    ):

        normalized = normalize_name(
            name
        )


        if not normalized:

            results[position] = (
                build_clean_response(
                    duration=0,
                    entity_name=name,
                    country=country,
                )
            )

            continue



        cached = cache.get(
            normalized
        )

        if cached is not None:

            result = cached.copy()

            result["entity_name"] = name

            results[position] = result

            continue

   

        record = sanction_index.get(
            normalized
        )

        if record is not None:

            result = build_response(
                flagged=True,
                record=record,
                score=100,
                duration=0,
                entity_name=name,
                country=country,
            )

            cache[normalized] = result

            results[position] = result

            continue


        fuzzy_items.append(
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
    ) in fuzzy_items:

        cached = cache.get(
            normalized
        )

        if cached is not None:

            result = cached.copy()

            result["entity_name"] = (
                original_name
            )

            results[position] = result

            continue

        result = screen_normalized_entity(
            normalized=normalized,
            original_name=original_name,
            country=country,
        )

        cache[normalized] = result

        results[position] = result


    final_results: list[
        dict[str, Any]
    ] = []

    for index, result in enumerate(
        results
    ):

        if result is None:

            result = build_clean_response(
                duration=0,
                entity_name=names[index],
                country=country,
            )

        final_results.append(
            result
        )


    total_duration = (
        time.perf_counter()
        - start
    ) * 1000

    return {
        "count": len(names),

        "results": final_results,

        "total_duration_ms": round(
            total_duration,
            2,
        ),
    }