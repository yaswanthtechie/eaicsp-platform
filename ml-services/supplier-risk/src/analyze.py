import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.config import get_settings
from src.data import load_headlines, load_trend_headlines, load_active_trend_headlines
from src.predict import predict
from src.sentiment import init_model
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
            if len(item) > 2000:
                raise ValueError(f"Headline at index {idx} exceeds maximum length of 2000 characters")
            validated.append(item)
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
    trend_direction: str | None = Field(
        default=None,
        description="Trend direction: 'rising', 'falling', or 'stable'",
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
        if len(value) > 2000:
            raise ValueError("headline exceeds maximum length of 2000 characters")
        return value


class TrendAnalysisRequest(BaseModel):
    """Request body for date-aware trend analysis."""

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

    @field_validator("supplier_name")
    @classmethod
    def validate_supplier_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("supplier_name cannot be blank or whitespace-only")
        if len(stripped) > 200:
            raise ValueError("supplier_name cannot exceed 200 characters")
        return stripped


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
def get_supplier_risk_trend(supplier_name: str):
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