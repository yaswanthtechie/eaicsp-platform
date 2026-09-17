from fastapi import FastAPI, UploadFile, File, HTTPException
import pandas as pd

from src.profile import profile
from src.profiler import make_json_serializable


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


app = FastAPI(
    title="Data Profiling API",
    description="API for profiling datasets",
    version="1.0.0"
)


@app.post("/profile")
async def profile_dataset(file: UploadFile = File(...)):
    if file.content_type not in {"text/csv", "application/csv"}:
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are allowed."
        )

    try:
        contents = await file.read()

        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail="File size exceeds the 10 MB limit."
            )

        if not contents:
            raise HTTPException(
                status_code=400,
                detail="Uploaded CSV file is empty."
            )

        from io import BytesIO

        df = pd.read_csv(BytesIO(contents))

    except HTTPException:
        raise

    except (
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
        UnicodeDecodeError
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid CSV file."
        )

    report = profile(df)

    return make_json_serializable(report)