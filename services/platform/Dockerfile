<<<<<<< HEAD
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY services/platform/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/platform/ ./

EXPOSE 8005
=======
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --system --no-create-home --uid 10001 app \
    && chown app:app /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app app ./app

USER app

EXPOSE 8005

>>>>>>> origin/develop
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
