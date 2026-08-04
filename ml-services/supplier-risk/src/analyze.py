import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from data import load_headlines
from sentiment import init_model
from predict import predict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for response validation
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.
    Initializes the NLP model on startup.
    """
    logger.info("Loading ProsusAI/finbert model... (this may take a moment)")
    try:
        init_model()
        logger.info("Model loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
    yield
    # Clean up on shutdown can be added here if needed

app = FastAPI(title="Supplier Risk Service", lifespan=lifespan)

@app.get("/api/v1/supplier-risk/analyze", response_model=AnalysisResponse)
def analyze_headlines():
    """
    Endpoint to analyze hardcoded supplier headlines and return a risk summary.
    """
    try:
        # Load grouped headlines
        grouped_headlines = load_headlines()
        
        response_data: Dict[str, Any] = {}
        
        # Analyze each supplier
        for supplier, headlines in grouped_headlines.items():
            summary = predict(supplier, headlines)
            response_data[supplier] = summary
            
        return {"supplier_summary": response_data}
    except Exception as e:
        logger.error(f"Error during headline analysis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during analysis")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("analyze:app", host="0.0.0.0", port=8006, reload=True)
