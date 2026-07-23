# Iris Reference Service

## Train

python -m src/train

## Start MLflow

mlflow ui
python -m mlflow ui 

## Promote Model

Move model to Production using MLflow UI.

## Serve

bentoml serve src.service:Irisservice --reload

## Endpoints

GET /health

POST /predict

POST /predict_batch

python version:3.12.4 support bentoMl prediction servive and aslo MLflow.

## predict_batch  iput
{
  "request": {
    "features": [
    [5.1, 3.5, 1.4, 0.2],
    [6.2, 3.4, 5.4, 2.3],
    [5.9, 3.0, 4.2, 1.5]
  ]
  }
}
## singal predict input
{
  "request": {
    "features": [
      5.1,
      3.5,
      1.4,
      0.2
    ]
  }
}