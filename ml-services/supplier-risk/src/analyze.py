import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.data import load_headlines
from src.sentiment import init_model
from src.predict import predict

# ----------------------------------------------------
# Logging
# ----------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ----------------------------------------------------
# Response Models
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
    sentiment_breakdown: SentimentBreakdown
    signals: List[SignalDetail]
    top_worst_3: List[HeadlineDetail]


class AnalysisResponse(BaseModel):
    supplier_summary: Dict[str, SupplierSummary]


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
# Analyze Endpoint
# ----------------------------------------------------

@app.post(
    "/api/v1/supplier-risk/analyze",
    response_model=AnalysisResponse,
)
def analyze_headlines():

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
            "supplier_summary": response_data
        }

    except Exception as exc:

        logger.exception(
            "Supplier risk analysis failed."
        )

        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        ) from exc


# ----------------------------------------------------
# Local Run
# ----------------------------------------------------

if __name__ == "__main__":

    # pyrefly: ignore [missing-import]
    import uvicorn

    uvicorn.run(
        "analyze:app",
        host="0.0.0.0",
        port=8006,
        reload=True,
    )