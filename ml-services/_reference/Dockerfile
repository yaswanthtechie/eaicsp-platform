
FROM python:3.12.4-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY scripts ./scripts

# Build the training data the same way `dvc repro` does
# (fetch -> prepare), then create the initial MLflow
# experiment and standalone model.
RUN python -m scripts.create_reference_dataset \
    && python -m scripts.dvc_prepare \
    && python -m src.train

# BentoML runtime configuration
ARG MODEL_BUILD_VERSION=dev
ENV MODEL_BUILD_VERSION=${MODEL_BUILD_VERSION}
ENV BENTO_BUNDLED_MODEL=true

EXPOSE 3000

CMD ["bentoml","serve","src.service:IrisService","--host","0.0.0.0","--port","3000"]
  