FROM python:3.12.4-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

# Create the initial MLflow experiment and production model.
# The Iris dataset is loaded directly from scikit-learn,
# so no local data/ directory is required.
RUN python -m src.train

EXPOSE 3000

CMD ["bentoml", "serve", "src.service:IrisService", "--host", "0.0.0.0", "--port", "3000"]