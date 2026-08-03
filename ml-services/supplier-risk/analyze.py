import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Set, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from data import load_headlines
from sentiment import init_model, analyze_sentiment
from predict import predict

# Define the keywords to detect globally from API-Gateway
KEYWORDS = ["bankruptcy", "strike", "recall", "fraud", "sanction"]

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
    signals: Optional[List[SignalDetail]] = []
    keywords: Optional[List[str]] = []

class SupplierSummary(BaseModel):
    # From HEAD
    supplier: str
    risk_score: float
    sentiment_breakdown: SentimentBreakdown
    signals: List[SignalDetail]
    top_worst_3: List[HeadlineDetail]
    
    # From API-Gateway
    headlines_analyzed: int
    positive: int
    negative: int
    neutral: int
    average_confidence: float
    detected_keywords: List[str]
    details: List[HeadlineDetail]

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

app = FastAPI(title="Supplier Risk Service", lifespan=lifespan)

@app.get("/api/v1/supplier-risk/analyze", response_model=AnalysisResponse)
def analyze_headlines():
    """
    Endpoint to analyze supplier headlines and return a risk summary.
    """
    try:
        # Load grouped headlines
        grouped_headlines = load_headlines()
        
        response_data: Dict[str, Any] = {}
        
        # Analyze each supplier
        for supplier, headlines in grouped_headlines.items():
            # 1. Run HEAD's prediction logic
            summary = predict(supplier, headlines)
            
            # 2. Run API-Gateway's additional logic
            total_confidence = 0.0
            details = []
            detected_keywords = set()
            
            for headline in headlines:
                res = analyze_sentiment(headline)
                sentiment_label = res["label"]
                confidence_score = res["confidence"]
                
                headline_lower = headline.lower()
                kw_found = [kw for kw in KEYWORDS if kw in headline_lower]
                detected_keywords.update(kw_found)
                
                total_confidence += confidence_score
                
                details.append({
                    "headline": headline,
                    "sentiment": sentiment_label,
                    "score": round(confidence_score, 4),
                    "keywords": kw_found,
                    "signals": []
                })
            
            headlines_count = len(headlines)
            avg_confidence = total_confidence / headlines_count if headlines_count > 0 else 0.0
            
            # 3. Merge both results
            response_data[supplier] = {
                "supplier": summary["supplier"],
                "risk_score": summary["risk_score"],
                "sentiment_breakdown": summary["sentiment_breakdown"],
                "signals": summary["signals"],
                "top_worst_3": summary["top_worst_3"],
                
                "headlines_analyzed": headlines_count,
                "positive": summary["sentiment_breakdown"]["positive"],
                "negative": summary["sentiment_breakdown"]["negative"],
                "neutral": summary["sentiment_breakdown"]["neutral"],
                "average_confidence": round(avg_confidence, 4),
                "detected_keywords": list(detected_keywords),
                "details": details
            }


        return {"supplier_summary": response_data}
    except Exception as e:
        logger.error(f"Error during headline analysis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during analysis")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("analyze:app", host="0.0.0.0", port=8006, reload=True)
