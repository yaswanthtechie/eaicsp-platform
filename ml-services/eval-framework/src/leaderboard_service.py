from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional

from .leaderboard import generate_leaderboard

app = FastAPI(title="Eval Framework Leaderboard Service")


class LeaderboardRequest(BaseModel):
    """
    results: {model_name: {metric_name: value}} -- same shape used
        throughout this framework (compare.py, leaderboard.py)
    metric: which metric to rank by
    lower_is_better: optional override; if not given, inferred automatically
        from the shared HIGHER_IS_BETTER_METRICS set, same as the Python API
    """
    results: Dict[str, Dict[str, float]]
    metric: str
    lower_is_better: Optional[bool] = None


class LeaderboardEntry(BaseModel):
    model: str
    score: float
    rank: int


class LeaderboardResponse(BaseModel):
    metric: str
    leaderboard: List[LeaderboardEntry]


@app.post("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard(request: LeaderboardRequest) -> LeaderboardResponse:
    """
    Ranks all models in the request by the given metric. Returns HTTP 422
    (via a clear error message) if the models' metrics aren't comparable --
    e.g. one model is missing the metric, or a value is non-numeric/NaN --
    rather than forcing a fake ranking. Same refusal philosophy as the
    Python-level generate_leaderboard() function.
    """
    try:
        ranked = generate_leaderboard(request.results, request.metric, request.lower_is_better)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    entries = [
        LeaderboardEntry(model=model, score=score, rank=i + 1)
        for i, (model, score) in enumerate(ranked)
    ]
    return LeaderboardResponse(metric=request.metric, leaderboard=entries)


@app.get("/health")
def health_check() -> dict:
    """Simple liveness check -- confirms the service is up and responding."""
    return {"status": "ok"}