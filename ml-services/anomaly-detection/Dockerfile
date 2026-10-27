FROM python:3.12-slim

WORKDIR /app/ml-services/anomaly-detection

COPY ml-services/eval-framework /app/ml-services/eval-framework
COPY ml-services/anomaly-detection/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ml-services/anomaly-detection/src src
COPY ml-services/anomaly-detection/config config

RUN useradd --create-home --uid 10001 app
USER app

CMD ["python", "-m", "src.stream_consumer"]