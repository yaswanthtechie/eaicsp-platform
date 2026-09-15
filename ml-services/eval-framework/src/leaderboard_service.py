from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional

from .leaderboard import generate_leaderboard
from .metrics import HIGHER_IS_BETTER_METRICS

app = FastAPI(title="Eval Framework Leaderboard Service")


class LeaderboardRequest(BaseModel):
    """
    results: {model_name: {metric_name: value}} -- same shape used
        throughout this framework (compare.py, leaderboard.py)
    metric: which metric to rank by
    metadata: optional {model_name: {"dataset_id": ..., "horizon": ...,
        "units": ...}} -- if provided, ranking is refused when models
        disagree on any key
    """
    results: Dict[str, Dict[str, float]]
    metric: str
    metadata: Optional[Dict[str, Dict[str, str]]] = None


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
    e.g. one model is missing the metric, a value is non-numeric/NaN/
    infinite, or metadata is provided and models disagree on dataset/
    horizon/units -- rather than forcing a fake ranking.

    Note: the direction (higher/lower is better) is always inferred
    automatically from the shared HIGHER_IS_BETTER_METRICS set -- this
    public API intentionally does not expose a lower_is_better override,
    since allowing a caller to contradict a metric's known direction
    (e.g. force MAPE to rank higher-is-better) would defeat the point of
    the safety guard.
    """
    try:
        ranked = generate_leaderboard(request.results, request.metric, metadata=request.metadata)
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