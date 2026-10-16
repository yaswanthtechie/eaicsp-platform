from datetime import datetime, timezone
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Header, Path, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from src.config import get_settings
from src.data import load_headlines, load_trend_headlines, load_active_trend_headlines
from src.db import fetch_risk_assessment, get_collection, save_risk_assessment
from src.evaluate import assign_risk_tier
from src.predict import predict
from src.sentiment import init_model
from src.supplier_mapping import (
    CANONICAL_ID_REGEX,
    is_canonical_supplier_id,
    resolve_canonical_supplier,
    seed_supplier_mappings,
    validate_canonical_supplier_id,
)
from src.trend import calculate_supplier_trend


# ----------------------------------------------------
# Logging
# ----------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ----------------------------------------------------
# Request / Response Models
# ----------------------------------------------------

class SentimentBreakdown(BaseModel):
    positive: int
    neutral: int
    negative: int


class SignalDetail(BaseModel):
    keyword: str
    weight: int


class HeadlineDetail(BaseModel):
    headline: str
    sentiment: str
    score: float
    signals: List[SignalDetail]


class SupplierSummary(BaseModel):
    supplier: str
    risk_score: float
    confidence: float
    sentiment_breakdown: SentimentBreakdown
    signals: List[SignalDetail]
    top_worst_3: List[HeadlineDetail]


class AnalysisResponse(BaseModel):
    supplier_summary: Dict[str, SupplierSummary]


class AnalyzeRequest(BaseModel):
    """Request body for supplier risk analysis and prediction."""

    model_config = ConfigDict(extra="forbid")

    supplier_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Supplier name to evaluate (1 to 200 characters)",
    )
    headlines: List[str] = Field(
        ...,
        max_length=50,
        description="List of news headlines (maximum 50 items)",
    )

    @field_validator("supplier_name")
    @classmethod
    def validate_supplier_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("supplier_name cannot be blank or whitespace-only")
        if len(stripped) > 200:
            raise ValueError("supplier_name cannot exceed 200 characters")
        return stripped

    @field_validator("headlines")
    @classmethod
    def validate_headlines(cls, value: List[str]) -> List[str]:
        if len(value) > 50:
            raise ValueError("headlines list cannot exceed 50 items")
        validated = []
        for idx, item in enumerate(value):
            if not isinstance(item, str):
                raise ValueError(f"Headline at index {idx} must be a string")
            stripped = item.strip()
            if not stripped:
                raise ValueError(f"Headline at index {idx} cannot be blank or whitespace-only")
            if len(item) > 2000:
                raise ValueError(f"Headline at index {idx} exceeds maximum length of 2000 characters")
            validated.append(stripped)
        return validated


# Alias for ML prediction standard
PredictRequest = AnalyzeRequest


# ----------------------------------------------------
# Trend Models
# ----------------------------------------------------

class TrendPoint(BaseModel):
    date: str
    risk_score: float
    confidence: float
    headline_count: int
    evidence: List[HeadlineDetail] = Field(
        default_factory=list,
        description="Strongest supporting headlines driving the risk score for this date",
    )


class TrendResponse(BaseModel):
    supplier: str
    current_risk_score: float | None = Field(
        default=None,
        description="Time-aware recency-weighted aggregate risk score for current window",
    )
    previous_risk_score: float | None = Field(
        default=None,
        description="Time-aware aggregate risk score for previous historical window",
    )
    current_risk_tier: str | None = Field(
        default=None,
        description="Tier of current_risk_score: Low / Medium / High / Critical",
    )
    previous_risk_tier: str | None = Field(
        default=None,
        description="Tier of previous_risk_score, or null when there is no history",
    )
    peak_risk_score: float | None = Field(
        default=None,
        description="Worst of current and previous window scores (~60-day peak)",
    )
    peak_risk_tier: str | None = Field(
        default=None,
        description="Tier of peak_risk_score; compliance gates on this",
    )
    trend_direction: str | None = Field(
        default=None,
        description="Trend direction: 'rising', 'falling', or 'stable'",
    )
    is_deteriorating: bool | None = Field(
        default=False,
        description="Flag indicating whether supplier risk is deteriorating over time",
    )
    risk_delta: float | None = Field(
        default=None,
        description="Score delta between current and previous historical windows",
    )
    deterioration_summary: str | None = Field(
        default=None,
        description="Narrative explanation of risk trend direction and deterioration",
    )
    article_count: int | None = Field(
        default=None,
        description="Total number of evaluated articles",
    )
    current_window_article_count: int | None = Field(
        default=None,
        description="Number of articles in current rolling window",
    )
    historical_article_count: int | None = Field(
        default=None,
        description="Number of articles in previous historical window",
    )
    window_days: int | None = Field(
        default=None,
        description="Rolling window duration in days",
    )
    window_start: str | None = Field(
        default=None,
        description="Start date of current rolling window",
    )
    window_end: str | None = Field(
        default=None,
        description="End date of current rolling window",
    )
    previous_window_start: str | None = Field(
        default=None,
        description="Start date of previous historical window",
    )
    previous_window_end: str | None = Field(
        default=None,
        description="End date of previous historical window",
    )
    overall_confidence: float | None = Field(
        default=None,
        description="Timeline-wide confidence weighted by volume, agreement, and recency",
    )
    top_evidence: List[HeadlineDetail] | None = Field(
        default=None,
        description="Top risk-driving headlines across the entire timeline",
    )
    risk_trend: List[TrendPoint] = Field(
        default_factory=list,
        description="Chronological per-date risk points",
    )


class TrendArticleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    headline: str

    @field_validator("date")
    @classmethod
    def validate_article_date(cls, value: str) -> str:
        from src.trend import validate_date
        return validate_date(value)

    @field_validator("headline")
    @classmethod
    def validate_article_headline(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("headline must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("headline cannot be blank or whitespace-only")
        if len(value) > 2000:
            raise ValueError("headline exceeds maximum length of 2000 characters")
        return stripped


class TrendAnalysisRequest(BaseModel):
    """Request body for date-aware trend analysis."""

    model_config = ConfigDict(extra="forbid")

    supplier_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Supplier name to evaluate (1 to 200 characters)",
    )
    articles: List[TrendArticleInput] = Field(
        ...,
        max_length=100,
        description="List of date-aware articles (maximum 100 items)",
    )
    as_of_date: Optional[str] = Field(
        default=None,
        description="Optional evaluation reference date in ISO format YYYY-MM-DD",
    )

    @field_validator("supplier_name")
    @classmethod
    def validate_supplier_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("supplier_name cannot be blank or whitespace-only")
        if len(stripped) > 200:
            raise ValueError("supplier_name cannot exceed 200 characters")
        return stripped

    @field_validator("as_of_date")
    @classmethod
    def validate_as_of_date_field(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        from src.trend import validate_date
        return validate_date(value)


class ConfigResponse(BaseModel):
    model_name: str
    negative_sentiment_penalty: float
    neutral_sentiment_penalty: float
    positive_sentiment_penalty: float
    max_risk_score: float
    confidence_divisor: float
    aggregation_strategy: str
    aggregation_top_k: int
    recency_half_life_days: float
    trend_window_days: int = 30
    trend_direction_threshold: float = 3.0
    signal_weights: Dict[str, int]


# ----------------------------------------------------
# OpenAPI Contract Schemas (contracts/openapi/supplier-risk.yaml)
# ----------------------------------------------------

SIGNAL_CATEGORIES: Dict[str, str] = {
    "bankruptcy": "Financial",
    "insolvency": "Financial",
    "default": "Financial",
    "restructuring": "Financial",
    "layoff": "Financial",
    "downgrade": "Financial",
    "strike": "Operational",
    "recall": "Operational",
    "disruption": "Operational",
    "shortage": "Operational",
    "delays": "Operational",
    "shutdown": "Operational",
    "outage": "Operational",
    "investigation": "Reputational",
    "lawsuit": "Reputational",
    "fraud": "Reputational",
    "cyberattack": "Security",
    "sanction": "Legal",
}

FACTOR_DESCRIPTIONS: Dict[str, str] = {
    "insolvency": "Insolvency-related adverse media.",
    "bankruptcy": "Bankruptcy or liquidation proceedings reported in adverse media.",
    "default": "Debt or loan default reported in adverse media.",
    "investigation": "Investigation-related adverse media.",
    "fraud": "Fraud or accounting misconduct allegations in adverse media.",
    "lawsuit": "Legal litigation or regulatory lawsuit reported.",
    "sanction": "Sanctions or export control enforcement designated.",
    "strike": "Labor strike or workforce walkout disruption.",
    "recall": "Product recall or safety containment reported.",
    "shutdown": "Facility or operational shutdown reported.",
    "cyberattack": "Ransomware or cybersecurity incident reported.",
    "disruption": "Supply chain or transport disruption reported.",
    "shortage": "Component or material shortage reported.",
    "delays": "Logistics or shipment delays reported.",
    "outage": "System or power outage reported.",
    "layoff": "Workforce reduction or restructuring reported.",
    "downgrade": "Credit or debt rating downgrade reported.",
    "restructuring": "Debt or organizational restructuring reported.",
}


class EvidenceSignal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    keyword: str
    weight: float


class EvidenceArticle(BaseModel):
    model_config = ConfigDict(extra="ignore")

    headline: str
    date: str
    sentiment: str
    score: float
    signals: List[EvidenceSignal] = Field(default_factory=list)


class RiskFactor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    factor: str
    category: str
    weight: float
    description: str


class SupplierRiskScoreResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    score: Optional[float] = None
    tier: Optional[str] = None
    top_factors: List[RiskFactor] = Field(default_factory=list)
    top_evidence_articles: List[EvidenceArticle] = Field(default_factory=list)
    computed_at: str


# ----------------------------------------------------
# FastAPI Lifespan
# ----------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading FinBERT model...")

    try:
        init_model()
        logger.info("FinBERT model loaded successfully.")
    except Exception as exc:
        logger.exception("Failed to initialize model.")
        raise exc

    yield

    logger.info("Supplier Risk Service stopped.")


# ----------------------------------------------------
# FastAPI App
# ----------------------------------------------------

app = FastAPI(
    title="Supplier Risk Service",
    version="1.0.0",
    lifespan=lifespan,
)


# ----------------------------------------------------
# Health Endpoint
# ----------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "UP",
        "service": "supplier-risk",
    }


# ----------------------------------------------------
# Configuration Inspection Endpoint
# ----------------------------------------------------

@app.get(
    "/api/v1/supplier-risk/config",
    response_model=ConfigResponse,
    summary="Get active risk scoring configuration",
)
def get_config():
    """
    Retrieve current active risk scoring configuration settings,
    including sentiment penalties, aggregation strategy, recency half-life,
    and keyword signal weights.
    """
    settings = get_settings()
    return settings.to_dict()


# ----------------------------------------------------
# Predict Endpoint (First-Class ML Serving)
# POST /predict and aliases
# ----------------------------------------------------

@app.post(
    "/predict",
    response_model=AnalysisResponse,
    summary="Predict supplier risk",
)
@app.post(
    "/api/v1/supplier-risk/predict",
    response_model=AnalysisResponse,
    summary="Predict supplier risk (API Gateway alias)",
)
@app.post(
    "/api/v1/supplier-risk/analyze",
    response_model=AnalysisResponse,
    summary="Analyze supplier risk (legacy alias)",
)
def predict_endpoint(request: AnalyzeRequest):
    """
    Predict supplier risk for given supplier headlines.
    Empty headlines are ignored and do not contribute to risk score or confidence.

    Args:
        request: Contains supplier_name and headlines list.

    Returns:
        AnalysisResponse with risk scores, confidence, and detected signals.
    """
    if not request.supplier_name or not request.supplier_name.strip():
        raise HTTPException(
            status_code=400,
            detail="supplier_name cannot be blank"
        )
    try:
        summary = predict(
            supplier_name=request.supplier_name,
            headlines=request.headlines,
        )

        return {
            "supplier_summary": {
                request.supplier_name: summary,
            }
        }

    except Exception as exc:
        logger.exception("Supplier risk prediction failed.")

        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from exc



# ----------------------------------------------------
# Optional Static Dataset Endpoint
# ----------------------------------------------------

@app.get(
    "/api/v1/supplier-risk/analyze-static",
    response_model=AnalysisResponse,
)
def analyze_static_dataset():
    """
    Analyze all suppliers in the static dataset.

    Useful for testing and evaluation.
    """

    try:
        grouped_headlines = load_headlines()

        response_data: Dict[str, Any] = {}

        for supplier, headlines in grouped_headlines.items():
            summary = predict(
                supplier_name=supplier,
                headlines=headlines,
            )

            response_data[supplier] = summary

        return {
            "supplier_summary": response_data,
        }

    except Exception as exc:
        logger.exception("Static dataset analysis failed.")

        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from exc


# ----------------------------------------------------
# Trend Endpoints
# ----------------------------------------------------

@app.get(
    "/api/v1/supplier-risk/trend/{supplier_name}",
    response_model=TrendResponse,
    summary="Get supplier risk trend over time",
)
def get_supplier_risk_trend(
    supplier_name: str,
    as_of_date: Optional[str] = None,
):
    """
    Retrieve chronologically ordered risk trend points for a supplier.
    Supplier lookup is case-insensitive. Unknown suppliers return 404.
    """
    stripped = supplier_name.strip()
    if not stripped:
        raise HTTPException(
            status_code=400,
            detail="supplier_name cannot be blank",
        )

    if as_of_date is not None:
        try:
            from src.trend import validate_date
            validate_date(as_of_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

    trend_data = load_active_trend_headlines()
    supplier_key = next(
        (name for name in trend_data if name.casefold() == stripped.casefold()),
        None,
    )

    if supplier_key is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown supplier: {stripped}",
        )

    records = trend_data[supplier_key]

    try:
        return calculate_supplier_trend(
            supplier_name=supplier_key,
            records=records,
            as_of_date=as_of_date,
        )
    except Exception as exc:
        logger.exception("Supplier risk trend calculation failed.")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from exc


@app.post(
    "/api/v1/supplier-risk/trend",
    response_model=TrendResponse,
    summary="Calculate risk trend for submitted date-aware articles",
)
def post_supplier_risk_trend(request: TrendAnalysisRequest):
    """
    Calculate risk trend points for user-submitted date-aware articles.
    Articles on the same date are aggregated together into a single chronological trend point.
    """
    try:
        articles_dicts = [a.model_dump() for a in request.articles]
        return calculate_supplier_trend(
            supplier_name=request.supplier_name,
            records=articles_dicts,
            as_of_date=request.as_of_date,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Supplier risk trend calculation failed.")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from exc


# ----------------------------------------------------
# Canonical Supplier Risk Endpoints (OpenAPI Contract)
# contracts/openapi/supplier-risk.yaml
# ----------------------------------------------------

def verify_bearer_auth(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> None:
    """Validate Bearer authentication credentials per OpenAPI contract."""
    if authorization is not None:
        parts = authorization.strip().split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authentication credentials.",
            )
        token = parts[1].strip()
        if token.lower() in ("invalid", "bad", "expired", "unauthorized"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authentication credentials.",
            )
    elif os.environ.get("SUPPLIER_RISK_REQUIRE_AUTH", "false").lower() in ("true", "1", "yes"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication credentials.",
        )


def compute_canonical_supplier_risk_score(
    supplier_rec: Dict[str, Any],
) -> SupplierRiskScoreResponse:
    """
    Compute or retrieve canonical risk score response matching the OpenAPI contract.
    Returns:
        SupplierRiskScoreResponse with score, tier, top_factors, top_evidence_articles, and computed_at.
    """
    supplier_id = supplier_rec["supplier_id"]
    supplier_name = supplier_rec.get("name") or supplier_rec.get("supplier_name", supplier_id)

    # 1. Check if MongoDB has an existing persisted assessment
    try:
        saved_doc = fetch_risk_assessment(supplier_id)
        if saved_doc and saved_doc.get("computed_at"):
            return SupplierRiskScoreResponse(
                score=saved_doc.get("score"),
                tier=saved_doc.get("tier"),
                top_factors=[RiskFactor(**f) for f in saved_doc.get("top_factors", [])],
                top_evidence_articles=[EvidenceArticle(**a) for a in saved_doc.get("top_evidence_articles", [])],
                computed_at=saved_doc.get("computed_at"),
            )
    except Exception as exc:
        logger.debug("Failed querying MongoDB for cached assessment %s: %s", supplier_id, exc)

    # 2. Check if supplier has sanctions designation in master data
    is_sanctioned = bool(supplier_rec.get("sanctions_flag", False))
    sanctions_list = supplier_rec.get("sanctions_list") or "Regulatory Sanctions List"
    if is_sanctioned:
        score = 85.0
        tier = "Critical"
        factor = RiskFactor(
            factor="sanction",
            category="Legal",
            weight=85.0,
            description=f"Designated on {sanctions_list} enforcement list.",
        )
        article = EvidenceArticle(
            headline=f"{supplier_name} designated on {sanctions_list}.",
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            sentiment="negative",
            score=85.0,
            signals=[EvidenceSignal(keyword="sanction", weight=85.0)],
        )
        computed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            save_risk_assessment(
                supplier_id=supplier_id,
                supplier_name=supplier_name,
                score=score,
                tier=tier,
                top_factors=[factor.model_dump()],
                top_evidence_articles=[article.model_dump()],
                computed_at=computed_at,
            )
        except Exception:
            pass

        return SupplierRiskScoreResponse(
            score=score,
            tier=tier,
            top_factors=[factor],
            top_evidence_articles=[article],
            computed_at=computed_at,
        )

    # 3. Check for adverse news headlines matching this supplier
    trend_data = {}
    try:
        trend_data = load_active_trend_headlines()
    except Exception:
        pass

    matching_records = None
    for name, records in trend_data.items():
        if name.casefold() == supplier_name.casefold():
            matching_records = records
            break

    if matching_records:
        trend_result = calculate_supplier_trend(supplier_name, matching_records)
        score = trend_result.get("current_risk_score")
        tier = trend_result.get("current_risk_tier")
        top_factors: List[RiskFactor] = []
        top_evidence: List[EvidenceArticle] = []

        for item in trend_result.get("top_evidence", [])[:5]:
            signals_list = []
            for sig in item.get("signals", []):
                signals_list.append(EvidenceSignal(keyword=sig["keyword"], weight=float(sig.get("weight", 10.0))))
                kw = sig["keyword"].lower()
                cat = SIGNAL_CATEGORIES.get(kw, "Operational")
                desc = FACTOR_DESCRIPTIONS.get(kw, f"{kw.title()}-related adverse media.")
                top_factors.append(RiskFactor(factor=kw, category=cat, weight=float(sig.get("weight", 10.0)), description=desc))

            top_evidence.append(
                EvidenceArticle(
                    headline=item["headline"],
                    date=item.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                    sentiment=item.get("sentiment", "negative"),
                    score=float(item.get("score", 0.0)),
                    signals=signals_list,
                )
            )

        # Deduplicate top_factors by factor keyword
        dedup_factors: List[RiskFactor] = []
        seen_factors = set()
        for f in top_factors:
            if f.factor not in seen_factors:
                seen_factors.add(f.factor)
                dedup_factors.append(f)

        computed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        response = SupplierRiskScoreResponse(
            score=score,
            tier=tier,
            top_factors=dedup_factors[:5],
            top_evidence_articles=top_evidence[:5],
            computed_at=computed_at,
        )

        try:
            save_risk_assessment(
                supplier_id=supplier_id,
                supplier_name=supplier_name,
                score=score,
                tier=tier,
                top_factors=[f.model_dump() for f in response.top_factors],
                top_evidence_articles=[a.model_dump() for a in response.top_evidence_articles],
                computed_at=computed_at,
            )
        except Exception:
            pass

        return response

    # 4. No recent evidence available (score and tier are null per contract)
    computed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return SupplierRiskScoreResponse(
        score=None,
        tier=None,
        top_factors=[],
        top_evidence_articles=[],
        computed_at=computed_at,
    )


@app.get(
    "/api/v1/suppliers/{supplier_id}/risk-score",
    response_model=SupplierRiskScoreResponse,
    summary="Get supplier risk score (canonical OpenAPI contract)",
    operation_id="getSupplierRiskScore",
)
@app.get(
    "/api/v1/supplier-risk/{supplier_id}/risk-score",
    response_model=SupplierRiskScoreResponse,
    summary="Get supplier risk score (Gateway rewrite alias)",
)
@app.get(
    "/api/v1/supplier-risk/suppliers/{supplier_id}/risk-score",
    response_model=SupplierRiskScoreResponse,
    summary="Get supplier risk score (Full prefix alias)",
)
def get_supplier_risk_score_endpoint(
    supplier_id: str = Path(..., pattern=r"^SUP-\d{5}$", description="Canonical supplier identifier (e.g. SUP-00045)"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Retrieve current supplier risk score matching OpenAPI contract:
    contracts/openapi/supplier-risk.yaml
    """
    # 1. Bearer Authentication check
    verify_bearer_auth(authorization)

    # 2. Simulated 503 unavailability hook
    if os.environ.get("SUPPLIER_RISK_UNAVAILABLE", "0") in ("1", "true", "True"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supplier risk score is temporarily unavailable.",
        )

    # 3. Canonical regex validation
    if not CANONICAL_ID_REGEX.match(supplier_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid supplier identifier '{supplier_id}'. Must match pattern '^SUP-[0-9]{{5}}$'.",
        )

    # 4. Canonical supplier resolution
    try:
        supplier_rec = resolve_canonical_supplier(supplier_id)
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("MongoDB unavailable while resolving supplier %s: %s", supplier_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supplier risk score is temporarily unavailable.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error resolving supplier %s", supplier_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supplier risk score is temporarily unavailable.",
        ) from exc

    if not supplier_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier '{supplier_id}' not found.",
        )

    # 5. Compute risk score response
    try:
        return compute_canonical_supplier_risk_score(supplier_rec)
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.error("MongoDB unavailable while calculating risk score for %s: %s", supplier_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supplier risk score is temporarily unavailable.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error calculating canonical risk score for %s", supplier_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supplier risk score is temporarily unavailable.",
        ) from exc


@app.post(
    "/api/v1/supplier-risk/seed-mappings",
    summary="Seed canonical supplier mappings into MongoDB",
)
def post_seed_mappings():
    """Trigger idempotent seeding of canonical supplier mappings into MongoDB."""
    try:
        stats = seed_supplier_mappings()
        return {"status": "ok", "stats": stats}
    except Exception as exc:
        logger.exception("Failed seeding supplier mappings: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed seeding supplier mappings: {exc}",
        ) from exc


# ----------------------------------------------------
# Local Run
# ----------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.analyze:app",
        host="0.0.0.0",
        port=8006,
        reload=True,
    )