FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY services/supplier-portal/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/supplier-portal/ ./

RUN mkdir -p /app/data
EXPOSE 8004
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
