FROM python:3.12-slim

WORKDIR /app/ml-services/eta-prediction

COPY ml-services/feature-lib /app/ml-services/feature-lib
COPY ml-services/eta-prediction/requirements.txt requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY ml-services/eta-prediction/src src
COPY ml-services/eta-prediction/models models
COPY ml-services/eta-prediction/data data

RUN useradd --create-home --uid 10001 app
USER app

CMD ["python", "-m", "src.stream_consumer"]