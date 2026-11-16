"""
Client Supplier Master and Incident Risk Scoring Module.
GitHub Issue #350 [R15-M7].

Provides support for:
- Client supplier master format (supplier_code, supplier_id, legal_name, country, city, category, on_time_delivery_pct)
- Client supplier incident data (incident_date, incident_type [Quality, Delay, Dispute, Other], description)
- Client-based risk feature extraction (12m incident counts, days since last incident, on-time delivery pct, country)
- Safe handling of missing on-time delivery data (TODO: Issue #325 endpoint integration)
- Grounded top-3 risk reasons generation
- Integration into canonical Supplier Risk scoring workflow
- MongoDB persistence and indexing for client suppliers and incidents
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from src.config import Settings, get_settings
from src.db import (
    get_client_incidents_collection,
    get_client_suppliers_collection,
    get_database,
)
from src.supplier_mapping import (
    CANONICAL_ID_REGEX,
    is_canonical_supplier_id,
    resolve_canonical_supplier,
    validate_canonical_supplier_id,
)

logger = logging.getLogger(__name__)

# Allowed incident types per Issue #350 specification
ALLOWED_INCIDENT_TYPES: Set[str] = {"Quality", "Delay", "Dispute", "Other"}
_ISO_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_incident_date(date_val: Any) -> str:
    """
    Validate that date_val is a string in ISO format YYYY-MM-DD
    representing a valid calendar date.

    Raises:
        ValueError: If the date is malformed, not a string, or an invalid calendar date.
    """
    if not isinstance(date_val, str):
        raise ValueError(f"Incident date must be a string, got {type(date_val).__name__}")

    stripped = date_val.strip()
    if not _ISO_DATE_REGEX.match(stripped):
        raise ValueError(
            f"Invalid incident date format '{date_val}'. Expected ISO format YYYY-MM-DD."
        )

    try:
        parsed = datetime.strptime(stripped, "%Y-%m-%d").date()
        if parsed.strftime("%Y-%m-%d") != stripped:
            raise ValueError(f"Invalid calendar date '{date_val}'.")
    except ValueError as exc:
        raise ValueError(f"Invalid calendar date '{date_val}': {exc}") from exc

    return stripped


def validate_incident_type(raw_type: Any) -> str:
    """
    Validate and normalize incident type against ALLOWED_INCIDENT_TYPES.
    Accepts case-insensitive variants ('quality' -> 'Quality').

    Raises:
        ValueError: If raw_type is not one of Quality, Delay, Dispute, Other.
    """
    if not isinstance(raw_type, str):
        raise ValueError(f"Incident type must be a string, got {type(raw_type).__name__}")

    stripped = raw_type.strip().title()
    if stripped not in ALLOWED_INCIDENT_TYPES:
        raise ValueError(
            f"Invalid incident type '{raw_type}'. Allowed types: {sorted(ALLOWED_INCIDENT_TYPES)}"
        )
    return stripped


# ----------------------------------------------------
# Pydantic Schemas for Client Data
# ----------------------------------------------------

class ClientSupplierMaster(BaseModel):
    """
    Client supplier master format.
    Supports either supplier_code or canonical supplier_id (or both).
    Supports ETL spec alias 'supplier_name' for 'legal_name'.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    supplier_code: Optional[str] = Field(
        default=None,
        description="Client supplier code (e.g. SUP-2231, SUPP-001)",
    )
    supplier_id: Optional[str] = Field(
        default=None,
        description="Canonical supplier ID matching SUP-XXXXX",
    )
    legal_name: str = Field(
        ...,
        validation_alias=AliasChoices("legal_name", "supplier_name", "name"),
        description="Legal entity or commercial name of the supplier",
    )
    country: Optional[str] = Field(
        default=None,
        description="Country of incorporation / operation. Handled safely when omitted.",
    )
    city: Optional[str] = Field(
        default=None,
        description="City of supplier headquarters / facility",
    )
    category: Optional[str] = Field(
        default=None,
        description="Supplier industry or product category. Handled safely when omitted.",
    )
    on_time_delivery_pct: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Historical on-time delivery percentage (0.0 to 100.0). Optional.",
    )

    @field_validator("supplier_code", mode="before")
    @classmethod
    def clean_supplier_code(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @field_validator("supplier_id", mode="before")
    @classmethod
    def validate_supplier_id_field(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip().upper()
        if not s:
            return None
        return validate_canonical_supplier_id(s)

    @field_validator("legal_name", mode="before")
    @classmethod
    def require_non_empty_legal_name(cls, v: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Field 'legal_name' must be a non-empty string.")
        return v.strip()

    @field_validator("country", "city", "category", mode="before")
    @classmethod
    def clean_optional_string(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @field_validator("on_time_delivery_pct", mode="before")
    @classmethod
    def validate_on_time_delivery(cls, v: Any) -> Optional[float]:
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return None
        try:
            val = float(v)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"on_time_delivery_pct must be numeric, got: {v}") from exc
        if val < 0.0 or val > 100.0:
            raise ValueError(f"on_time_delivery_pct must be between 0.0 and 100.0, got: {val}")
        return val

    def model_post_init(self, __context: Any) -> None:
        if not self.supplier_code and not self.supplier_id:
            raise ValueError("Client supplier record must contain at least 'supplier_code' or 'supplier_id'.")


class SupplierIncident(BaseModel):
    """
    Client supplier incident record.
    Supported types: Quality, Delay, Dispute, Other.
    """

    model_config = ConfigDict(extra="ignore")

    incident_id: Optional[str] = Field(
        default=None,
        description="Optional unique incident identifier (e.g. INC-000001)",
    )
    supplier_code: Optional[str] = Field(
        default=None,
        description="Client supplier code reference",
    )
    supplier_id: Optional[str] = Field(
        default=None,
        description="Canonical supplier ID reference (SUP-XXXXX)",
    )
    incident_date: str = Field(
        ...,
        description="Incident occurrence date in ISO YYYY-MM-DD format",
    )
    incident_type: str = Field(
        ...,
        description="Incident classification: Quality, Delay, Dispute, Other",
    )
    description: Optional[str] = Field(
        default="",
        description="Description of the incident. Missing or invalid descriptions handled safely.",
    )
    severity: Optional[str] = Field(
        default=None,
        description="Optional severity level: low, medium, high",
    )
    resolved: Optional[bool] = Field(
        default=None,
        description="Optional resolution flag",
    )

    @field_validator("incident_date", mode="before")
    @classmethod
    def validate_date_field(cls, v: Any) -> str:
        return validate_incident_date(v)

    @field_validator("incident_type", mode="before")
    @classmethod
    def validate_type_field(cls, v: Any) -> str:
        return validate_incident_type(v)

    @field_validator("description", mode="before")
    @classmethod
    def sanitize_description(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()

    def model_post_init(self, __context: Any) -> None:
        if not self.supplier_code and not self.supplier_id:
            raise ValueError("Supplier incident must contain at least 'supplier_code' or 'supplier_id'.")


class ClientRiskFeatures(BaseModel):
    """
    Calculated client-based operational risk features and incident metrics.
    Exposed in API response and persisted in MongoDB assessment cache.
    """

    model_config = ConfigDict(extra="ignore")

    quality_incidents_12m: int = Field(
        default=0,
        ge=0,
        description="Quality incident count in the previous 12 months",
    )
    delay_incidents_12m: int = Field(
        default=0,
        ge=0,
        description="Delay incident count in the previous 12 months",
    )
    dispute_incidents_12m: int = Field(
        default=0,
        ge=0,
        description="Dispute incident count in the previous 12 months",
    )
    other_incidents_12m: int = Field(
        default=0,
        ge=0,
        description="Other incident count in the previous 12 months",
    )
    days_since_last_incident: Optional[int] = Field(
        default=None,
        ge=0,
        description="Days elapsed since the last eligible incident; null when supplier has no prior incidents",
    )
    on_time_delivery_pct: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="On-time delivery percentage from supplier master; null when missing",
    )
    on_time_delivery_missing: bool = Field(
        default=False,
        description="Flag indicating on-time delivery data was omitted from supplier master",
    )
    country: Optional[str] = Field(
        default=None,
        description="Supplier operating country from master data",
    )
    city: Optional[str] = Field(
        default=None,
        description="Supplier operating city from master data",
    )
    category: Optional[str] = Field(
        default=None,
        description="Supplier commodity / product category",
    )


# ----------------------------------------------------
# Canonical Supplier Code Resolution
# ----------------------------------------------------

def resolve_supplier_code_to_canonical_id(
    supplier_code: str,
    client_collection: Optional[Collection] = None,
    mapping_collection: Optional[Collection] = None,
) -> Optional[str]:
    """
    Resolve a client supplier_code to its canonical supplier ID (SUP-XXXXX) using explicit mapping.

    Resolution rules:
    1. If supplier_code is already a canonical supplier ID, verify it exists and return it.
    2. Look up in supplier_mappings collection (by supplier_codes, supplier_code, or aliases).
    3. Look up in client_suppliers collection (by supplier_code).
    4. Never invent canonical supplier IDs.
    5. Never use fuzzy matching or guessed supplier mappings.

    Returns:
        Canonical supplier ID string if explicitly mapped, else None.
    """
    if not supplier_code or not isinstance(supplier_code, str):
        return None

    clean = supplier_code.strip()
    if not clean:
        return None

    # 1. Canonical supplier ID check
    upper_clean = clean.upper()
    if is_canonical_supplier_id(upper_clean):
        # Verify it exists in canonical mappings
        m_rec = resolve_canonical_supplier(upper_clean, collection=mapping_collection)
        if m_rec:
            return upper_clean

    # 2. Look up in supplier_mappings collection
    from src.supplier_mapping import get_supplier_mapping_collection
    col_map = mapping_collection if mapping_collection is not None else get_supplier_mapping_collection()
    try:
        doc = col_map.find_one(
            {"$or": [
                {"supplier_codes": clean},
                {"supplier_code": clean},
                {"aliases": clean},
                {"supplier_codes": upper_clean},
                {"supplier_code": upper_clean},
            ]},
            {"_id": 0, "supplier_id": 1},
        )
        if doc and doc.get("supplier_id") and is_canonical_supplier_id(doc["supplier_id"]):
            return doc["supplier_id"]
    except PyMongoError:
        raise
    except Exception as exc:
        logger.debug("Mapping collection query error: %s", exc)

    # 3. Look up in client_suppliers collection
    col_client = client_collection if client_collection is not None else get_client_suppliers_collection()
    try:
        cdoc = col_client.find_one(
            {"$or": [{"supplier_code": clean}, {"supplier_code": upper_clean}]},
            {"_id": 0, "supplier_id": 1},
        )
        if cdoc and cdoc.get("supplier_id") and is_canonical_supplier_id(cdoc["supplier_id"]):
            return cdoc["supplier_id"]
    except PyMongoError:
        raise
    except Exception as exc:
        logger.debug("Client collection query error: %s", exc)

    return None


# ----------------------------------------------------
# Feature Extraction Logic
# ----------------------------------------------------

def calculate_client_risk_features(
    master: Optional[Dict[str, Any] | ClientSupplierMaster] = None,
    incidents: Optional[List[Dict[str, Any] | SupplierIncident]] = None,
    scoring_date: Optional[str | date] = None,
) -> ClientRiskFeatures:
    """
    Calculate client-based risk features from master and incident records.

    Requirements:
    - Validate incident dates and incident types.
    - Exclude all incidents dated after scoring_date (future incidents).
    - Calculate incident counts by type for previous 12 months (365 days).
    - Incidents older than 12 months are excluded from the 12-month count.
    - Calculate days since last eligible incident (incident_date <= scoring_date).
    - Handle suppliers with no incidents correctly (counts=0, days_since=None).
    - Safely handle missing optional values.
    - Do not treat missing on-time data as zero; clearly indicate missing status.
    - Add clear TODO for Balaji's GitHub Issue #325 endpoint.

    Args:
        master: Optional client supplier master dictionary or model.
        incidents: Optional list of incident records.
        scoring_date: Optional reference scoring date. Defaults to current UTC date.

    Returns:
        ClientRiskFeatures instance.
    """
    # 1. Resolve scoring reference date
    ref_date: date
    if scoring_date is None:
        ref_date = datetime.now(timezone.utc).date()
    elif isinstance(scoring_date, str):
        clean_date = validate_incident_date(scoring_date)
        ref_date = datetime.strptime(clean_date, "%Y-%m-%d").date()
    elif isinstance(scoring_date, (datetime, date)):
        ref_date = scoring_date.date() if isinstance(scoring_date, datetime) else scoring_date
    else:
        raise ValueError(f"Invalid scoring_date: {scoring_date}")

    twelve_months_ago = ref_date - timedelta(days=365)

    # 2. Process incidents
    quality_count = 0
    delay_count = 0
    dispute_count = 0
    other_count = 0
    eligible_dates: List[date] = []

    raw_incidents = incidents or []
    for inc in raw_incidents:
        if isinstance(inc, SupplierIncident):
            inc_dict = inc.model_dump()
        elif isinstance(inc, dict):
            inc_dict = inc
        else:
            logger.warning("Skipping invalid incident item: %s", type(inc).__name__)
            continue

        raw_date = inc_dict.get("incident_date")
        raw_type = inc_dict.get("incident_type")

        # Validate date and type
        try:
            valid_date_str = validate_incident_date(raw_date)
            valid_type = validate_incident_type(raw_type)
        except ValueError as exc:
            logger.warning("Skipping malformed incident record (%s): %s", inc_dict, exc)
            continue

        inc_date = datetime.strptime(valid_date_str, "%Y-%m-%d").date()

        # Exclude all incidents dated after the scoring date (future incidents)
        if inc_date > ref_date:
            logger.debug(
                "Excluding future incident dated %s (scoring_date=%s)",
                inc_date,
                ref_date,
            )
            continue

        # Record as eligible incident
        eligible_dates.append(inc_date)

        # 12-month rolling window count: [ref_date - 365 days, ref_date]
        if inc_date >= twelve_months_ago:
            if valid_type == "Quality":
                quality_count += 1
            elif valid_type == "Delay":
                delay_count += 1
            elif valid_type == "Dispute":
                dispute_count += 1
            elif valid_type == "Other":
                other_count += 1

    # 3. Days since last eligible incident
    days_since_last: Optional[int] = None
    if eligible_dates:
        latest_incident_date = max(eligible_dates)
        days_since_last = max(0, (ref_date - latest_incident_date).days)

    # 4. Extract master details & handle on-time delivery percentage
    country = None
    city = None
    category = None
    on_time_pct: Optional[float] = None
    on_time_missing: bool = True

    if master is not None:
        m_dict = master.model_dump() if isinstance(master, ClientSupplierMaster) else dict(master)
        country = (m_dict.get("country") or "").strip() or None
        city = (m_dict.get("city") or "").strip() or None
        category = (m_dict.get("category") or "").strip() or None

        raw_ot = m_dict.get("on_time_delivery_pct")
        if raw_ot is not None and str(raw_ot).strip() != "":
            try:
                val = float(raw_ot)
                if 0.0 <= val <= 100.0:
                    on_time_pct = round(val, 2)
                    on_time_missing = False
                else:
                    logger.warning("on_time_delivery_pct out of range [0, 100]: %s", val)
            except (ValueError, TypeError):
                logger.warning("Invalid on_time_delivery_pct: %s", raw_ot)

    if on_time_missing:
        # TODO(Issue #325 - Balaji): When Balaji's dynamic on-time delivery endpoint is available,
        # fetch dynamic on-time delivery metric from shipment history as fallback.
        # Do NOT call or integrate that endpoint yet per Issue #350 specification.
        logger.debug(
            "on_time_delivery_pct missing from supplier master; continuing scoring without zero penalty. (TODO: Issue #325)"
        )

    return ClientRiskFeatures(
        quality_incidents_12m=quality_count,
        delay_incidents_12m=delay_count,
        dispute_incidents_12m=dispute_count,
        other_incidents_12m=other_count,
        days_since_last_incident=days_since_last,
        on_time_delivery_pct=on_time_pct,
        on_time_delivery_missing=on_time_missing,
        country=country,
        city=city,
        category=category,
    )


# ----------------------------------------------------
# Client Risk Scoring Algorithm
# ----------------------------------------------------

def calculate_client_risk_score(
    features: ClientRiskFeatures,
    config: Optional[Settings] = None,
) -> float:
    """
    Calculate an operational risk score (0.0 to 100.0) from client-based features.

    Scoring Methodology:
    1. Incident Severity:
       Sum of incident counts multiplied by configurable type weights:
       - Quality: default 15.0 pts/incident
       - Delay: default 10.0 pts/incident
       - Dispute: default 12.0 pts/incident
       - Other: default 8.0 pts/incident
       Capped at client_max_incident_score (default 75.0) to prevent single-domain overflow.
    2. Recency Adjustment:
       - Incident within last 30 days: +10.0 pts (acute active operational failure)
       - Incident within last 90 days: +5.0 pts
       - Incident older than 180 days: -5.0 pts (temporal decay of past friction)
    3. On-Time Delivery Adjustment:
       - Below target (default 95.0%): penalty = (target - actual) * penalty_weight
       - At or above target: -5.0 pts mitigation discount for verified operational excellence
       - Missing on-time data: 0.0 pts (NEVER treated as zero; scoring continues safely)
    4. Clamped to [0.0, 100.0].

    A supplier with 0 incidents and no late deliveries receives a clean baseline score (0.0).
    """
    cfg = config if config is not None else get_settings()

    # 1. Incident severity component
    raw_incident_score = (
        features.quality_incidents_12m * cfg.client_quality_incident_weight
        + features.delay_incidents_12m * cfg.client_delay_incident_weight
        + features.dispute_incidents_12m * cfg.client_dispute_incident_weight
        + features.other_incidents_12m * cfg.client_other_incident_weight
    )
    incident_score = min(cfg.client_max_incident_score, raw_incident_score)

    # 2. Recency modifier
    recency_modifier = 0.0
    if features.days_since_last_incident is not None:
        if features.days_since_last_incident <= 30:
            recency_modifier = 10.0
        elif features.days_since_last_incident <= 90:
            recency_modifier = 5.0
        elif features.days_since_last_incident > 180 and incident_score > 0:
            recency_modifier = -5.0

    # 3. On-time delivery modifier
    delivery_modifier = 0.0
    if not features.on_time_delivery_missing and features.on_time_delivery_pct is not None:
        target = cfg.client_target_on_time_delivery_pct
        actual = features.on_time_delivery_pct
        if actual < target:
            delivery_modifier = (target - actual) * cfg.client_late_delivery_penalty_weight
        else:
            # Mitigation discount for high operational reliability
            delivery_modifier = -5.0
    # Missing on-time delivery is NOT treated as zero: delivery_modifier remains 0.0

    total_client_score = incident_score + recency_modifier + delivery_modifier
    return round(min(100.0, max(0.0, total_client_score)), 2)


# ----------------------------------------------------
# Grounded Top Three Reasons Generator
# ----------------------------------------------------

def generate_top_reasons(
    features: Optional[ClientRiskFeatures] = None,
    nlp_signals: Optional[List[Dict[str, Any]]] = None,
    is_sanctioned: bool = False,
    sanctions_list: str = "",
    config: Optional[Settings] = None,
) -> List[str]:
    """
    Generate top three human-readable reasons explaining the risk score.
    Every reason is strictly grounded in actual input data; nothing is fabricated.

    Candidates are ranked by risk significance / severity, and the top 3 are returned.
    """
    cfg = config if config is not None else get_settings()
    target_delivery = cfg.client_target_on_time_delivery_pct
    candidates: List[Tuple[float, str]] = []

    # 1. Sanctions designation (highest priority)
    if is_sanctioned:
        list_name = sanctions_list.strip() if sanctions_list else "regulatory list"
        candidates.append((100.0, f"Designated on {list_name} (critical compliance risk)"))

    if features is not None:
        # 2. Incidents by type
        if features.delay_incidents_12m > 0:
            count = features.delay_incidents_12m
            s = "s" if count != 1 else ""
            candidates.append((50.0 + count * 5.0, f"{count} delay incident{s} in 12 months"))

        if features.quality_incidents_12m > 0:
            count = features.quality_incidents_12m
            s = "s" if count != 1 else ""
            candidates.append((55.0 + count * 5.0, f"{count} quality incident{s} in 12 months"))

        if features.dispute_incidents_12m > 0:
            count = features.dispute_incidents_12m
            s = "s" if count != 1 else ""
            candidates.append((52.0 + count * 5.0, f"{count} dispute incident{s} in 12 months"))

        if features.other_incidents_12m > 0:
            count = features.other_incidents_12m
            s = "s" if count != 1 else ""
            candidates.append((40.0 + count * 5.0, f"{count} other incident{s} in 12 months"))

        total_incidents = (
            features.quality_incidents_12m
            + features.delay_incidents_12m
            + features.dispute_incidents_12m
            + features.other_incidents_12m
        )
        if total_incidents == 0:
            candidates.append((25.0, "0 incidents reported in the last 12 months"))

        # 3. Recency of incidents
        if features.days_since_last_incident is not None:
            days = features.days_since_last_incident
            s = "s" if days != 1 else ""
            if days <= 30:
                candidates.append((48.0, f"Recent incident occurred {days} day{s} ago"))
            else:
                candidates.append((20.0, f"Last eligible incident occurred {days} day{s} ago"))
        elif total_incidents == 0:
            candidates.append((15.0, "No prior recorded incidents"))

        # 4. On-time delivery performance
        if not features.on_time_delivery_missing and features.on_time_delivery_pct is not None:
            ot = features.on_time_delivery_pct
            if ot < target_delivery:
                candidates.append((
                    45.0 + (target_delivery - ot),
                    f"On-time delivery rate is {ot:.1f}% (below {target_delivery:.1f}% target)",
                ))
            else:
                candidates.append((22.0, f"On-time delivery rate is {ot:.1f}%"))
        else:
            candidates.append((18.0, "On-time delivery data is missing (pending Issue #325)"))

        # 5. Operating country
        if features.country:
            candidates.append((5.0, f"Operating location: {features.country}"))

    # 6. NLP adverse news signals (if provided)
    if nlp_signals:
        for sig in nlp_signals[:3]:
            kw = sig.get("keyword", "")
            wt = float(sig.get("weight", 20.0))
            if kw:
                candidates.append((30.0 + wt, f"Adverse media signal: {kw}"))

    # Sort candidates by weight descending and pick top 3
    candidates.sort(key=lambda item: item[0], reverse=True)
    selected: List[str] = []
    seen = set()
    for _, reason in candidates:
        if reason not in seen:
            seen.add(reason)
            selected.append(reason)
        if len(selected) >= 3:
            break

    return selected


# ----------------------------------------------------
# Client Data Ingestion and Persistence Helpers
# ----------------------------------------------------

def save_client_supplier_master(
    record: Dict[str, Any] | ClientSupplierMaster,
    collection: Optional[Collection] = None,
) -> str:
    """
    Validate and upsert a client supplier master record into MongoDB.
    """
    from src.db import save_client_supplier

    if isinstance(record, ClientSupplierMaster):
        doc = record.model_dump()
    else:
        # Validate through Pydantic
        model = ClientSupplierMaster(**record)
        doc = model.model_dump()

    return save_client_supplier(doc, collection=collection)


def save_supplier_incidents_data(
    records: List[Dict[str, Any] | SupplierIncident],
    collection: Optional[Collection] = None,
) -> int:
    """
    Validate and batch insert client supplier incidents into MongoDB.
    """
    from src.db import save_client_incidents

    validated_docs = []
    for r in records:
        if isinstance(r, SupplierIncident):
            validated_docs.append(r.model_dump())
        else:
            model = SupplierIncident(**r)
            validated_docs.append(model.model_dump())

    return save_client_incidents(validated_docs, collection=collection)
