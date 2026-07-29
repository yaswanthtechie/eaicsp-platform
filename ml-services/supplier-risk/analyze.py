import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Set
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import pipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for response validation
class HeadlineDetail(BaseModel):
    headline: str
    sentiment: str
    score: float
    keywords: List[str]

class SupplierSummary(BaseModel):
    headlines_analyzed: int
    positive: int
    negative: int
    neutral: int
    average_confidence: float
    detected_keywords: List[str]
    details: List[HeadlineDetail]

class AnalysisResponse(BaseModel):
    supplier_summary: Dict[str, SupplierSummary]

# Define the keywords to detect globally
KEYWORDS = ["bankruptcy", "strike", "recall", "fraud", "sanction"]

# Global pipeline state
ml_models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model on startup
    logger.info("Loading ProsusAI/finbert model... (this may take a moment)")
    try:
        ml_models["nlp"] = pipeline("text-classification", model="ProsusAI/finbert")
        logger.info("Model loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        # In a real app we might raise the error or handle it, here we let it start and handle errors during requests
    yield
    # Clean up on shutdown
    ml_models.clear()

app = FastAPI(title="Supplier Risk Service", lifespan=lifespan)

@app.get("/api/v1/supplier-risk/analyze", response_model=AnalysisResponse)
def analyze_headlines():
    nlp = ml_models.get("nlp")
    if not nlp:
        logger.error("NLP model is not initialized.")
        raise HTTPException(status_code=503, detail="Model not initialized")

    # 15 real company news headlines
    headlines = [
        {"supplier": "TechCorp", "headline": "TechCorp files for bankruptcy after massive fraud scandal."},
        {"supplier": "AutoMaker Inc", "headline": "AutoMaker Inc announces major recall of 1 million vehicles due to brake failure."},
        {"supplier": "Logistics Co", "headline": "Logistics Co workers go on strike demanding better pay and conditions."},
        {"supplier": "Global Trade", "headline": "Global Trade faces severe sanction from international regulatory bodies."},
        {"supplier": "TechCorp", "headline": "TechCorp appoints new CEO to restructure the company."},
        {"supplier": "AutoMaker Inc", "headline": "AutoMaker Inc reports record profits for the third quarter."},
        {"supplier": "FoodSupplies", "headline": "FoodSupplies investigates alleged fraud in their accounting department."},
        {"supplier": "Logistics Co", "headline": "Logistics Co resolves strike, operations return to normal."},
        {"supplier": "Global Trade", "headline": "Global Trade expands operations into the Asian market."},
        {"supplier": "MetalWorks", "headline": "MetalWorks hit with unexpected sanction over environmental violations."},
        {"supplier": "MetalWorks", "headline": "MetalWorks secures a large government contract for infrastructure."},
        {"supplier": "FoodSupplies", "headline": "Massive recall of FoodSupplies products due to contamination fears."},
        {"supplier": "BuildIt", "headline": "BuildIt declares bankruptcy amidst rising interest rates and falling demand."},
        {"supplier": "BuildIt", "headline": "BuildIt receives a bailout package from investors to stay afloat."},
        {"supplier": "TechCorp", "headline": "TechCorp shares plummet as fraud investigation deepens."}
    ]

    supplier_summary: Dict[str, Dict[str, Any]] = {}

    try:
        for item in headlines:
            supplier = item["supplier"]
            headline = item["headline"]
            
            # Use the loaded pipeline
            result = nlp(headline)[0]
            sentiment_label = result['label']
            confidence_score = result['score']
            
            # Detect keywords
            headline_lower = headline.lower()
            detected_keywords = [kw for kw in KEYWORDS if kw in headline_lower]

            if supplier not in supplier_summary:
                supplier_summary[supplier] = {
                    "headlines_analyzed": 0,
                    "positive": 0,
                    "negative": 0,
                    "neutral": 0,
                    "total_confidence": 0.0,
                    "detected_keywords": set(),
                    "details": []
                }
            
            summary = supplier_summary[supplier]
            summary["headlines_analyzed"] += 1
            summary[sentiment_label.lower()] += 1
            summary["total_confidence"] += confidence_score
            summary["detected_keywords"].update(detected_keywords)
            
            summary["details"].append({
                "headline": headline,
                "sentiment": sentiment_label,
                "score": round(confidence_score, 4),
                "keywords": detected_keywords
            })

        # Calculate averages and format output
        response_data = {}
        for supplier, data in supplier_summary.items():
            avg_confidence = data["total_confidence"] / data["headlines_analyzed"]
            response_data[supplier] = {
                "headlines_analyzed": data["headlines_analyzed"],
                "positive": data["positive"],
                "negative": data["negative"],
                "neutral": data["neutral"],
                "average_confidence": round(avg_confidence, 4),
                "detected_keywords": list(data["detected_keywords"]),
                "details": data["details"]
            }

        return {"supplier_summary": response_data}
    except Exception as e:
        logger.error(f"Error during headline analysis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during analysis")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("analyze:app", host="0.0.0.0", port=8006, reload=True)
