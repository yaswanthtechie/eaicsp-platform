from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from typing import Dict, List, Optional, Any

from .leaderboard import generate_leaderboard
from .metrics import HIGHER_IS_BETTER_METRICS

app = FastAPI(title="Eval Framework Leaderboard Service")


class LeaderboardRequest(BaseModel):
    """
    results: {model_name: {metric_name: value}} -- same shape used
        throughout this framework (compare.py, leaderboard.py)
    metric: which metric to rank by
    metadata: optional {model_name: {key: value}}, e.g. {"dataset_id": "x",
        "horizon": 7, "units": "percent"} -- values may be strings,
        numbers, or booleans; if provided, ranking is refused when models
        disagree on any key.

    model_config forbids any field not listed above (e.g. a stray
    lower_is_better) -- FastAPI/Pydantic reject the request with a clear
    422 instead of silently accepting and ignoring an unrecognized field,
    which would otherwise look like a 200 success while quietly doing
    something the caller didn't expect.
    """
    model_config = ConfigDict(extra="forbid")

    results: Dict[str, Dict[str, float]]
    metric: str
    metadata: Optional[Dict[str, Dict[str, Any]]] = None


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
    infinite, the metric is unrecognized, or metadata is provided and
    models disagree on dataset/horizon/units -- rather than forcing a fake
    ranking.

    Note: the direction (higher/lower is better) is always inferred
    automatically from the shared HIGHER_IS_BETTER_METRICS / KNOWN_METRICS
    sets -- this public API intentionally does not expose a
    lower_is_better override, since allowing a caller to contradict a
    metric's known direction (e.g. force MAPE to rank higher-is-better)
    would defeat the point of the safety guard. A request containing a
    stray lower_is_better field (or any other unrecognized field) is
    rejected with 422 rather than silently ignored.
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