from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
import pandas as pd

from src.profile import profile
from src.profiler import make_json_serializable


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Browsers and HTTP clients label CSV uploads inconsistently.
# Windows browsers send application/vnd.ms-excel when Excel is installed,
# and many clients send application/octet-stream for any file.
ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "text/plain",
    "application/vnd.ms-excel",
    "application/octet-stream",
}


app = FastAPI(
    title="Data Profiling API",
    description="API for profiling datasets",
    version="1.0.0"
)


def _is_csv_upload(file: UploadFile) -> bool:
    # "text/csv; charset=utf-8" -> "text/csv"
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    has_csv_extension = Path(file.filename or "").suffix.lower() == ".csv"

    return has_csv_extension and content_type in ALLOWED_CONTENT_TYPES


@app.post("/profile")
async def profile_dataset(file: UploadFile = File(...)):
    if not _is_csv_upload(file):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are allowed."
        )

    # Read one byte past the limit so an oversized file is detected
    # without loading the whole upload into memory.
    contents = await file.read(MAX_FILE_SIZE + 1)

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

    try:
        df = pd.read_csv(BytesIO(contents))
    except (
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
        UnicodeDecodeError,
        ValueError,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid CSV file."
        )

    # pandas does not raise when data rows have MORE fields than the
    # header; it silently moves the extra values into a MultiIndex.
    if isinstance(df.index, pd.MultiIndex):
        raise HTTPException(
            status_code=400,
            detail="Invalid CSV file: rows have more fields than the header."
        )

    report = profile(df)

    return make_json_serializable(report)