from fastapi import FastAPI, UploadFile, File
from src.profiler import Profiler
import pandas as pd

from src.profile import profile


app = FastAPI(
    title="Data Profiling API",
    description="API for profiling datasets",
    version="1.0.0"
)


@app.post("/profile")
async def profile_dataset(file: UploadFile = File(...)):
    df = pd.read_csv(file.file)
    report = profile(df)

    return Profiler()._make_json_serializable(report)