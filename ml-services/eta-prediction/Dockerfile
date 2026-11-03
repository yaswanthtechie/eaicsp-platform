FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    NUMBA_CACHE_DIR=/tmp/numba_cache \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app/ml-services/eta-prediction

COPY ml-services/feature-lib /app/ml-services/feature-lib
COPY ml-services/eta-prediction/requirements.txt requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY ml-services/eta-prediction/src src
COPY ml-services/eta-prediction/models models

# Fallback route table. Compose mounts the full seed over ETA_SEED_DIR.
COPY data-platform/seed/samples /app/data-platform/seed/samples

RUN useradd --create-home --uid 10001 app
USER app

CMD ["python", "-m", "src.stream_consumer"]