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


## Today's Changes

The following improvements were completed during this development cycle:

### MLflow Integration
- Created a reusable `mlflow_utils.py` wrapper for MLflow operations.
- Replaced direct MLflow API calls in `train.py` with wrapper functions.
- Added reusable helper functions:
  - `start_run()`
  - `set_experiment()`
  - `log_params()`
  - `log_metrics()`
  - `log_model()`
  - `promote_model()`
  - `set_tags()`
  - `log_artifact()`

### Automatic Model Promotion
- Implemented automatic model registration after training.
- Added automatic promotion of the latest model to the **Production** alias.
- Removed the need for manual promotion through the MLflow UI.

### Dynamic Model Loading
- Updated `predict.py` to load models from the MLflow Model Registry using the **Production** alias.
- Retrieved the actual model version dynamically from MLflow instead of using a hardcoded version.

### Prediction API Improvements
- Updated `/predict` endpoint to return:
  - Predicted class label
  - Confidence score
  - Model version
  - Class probabilities
- Updated `/predict_batch` endpoint to return the same detailed response for each prediction.

### Testing
- Added unit tests for:
  - Valid prediction requests
  - Invalid input validation

### Documentation
- Updated the project documentation.
- Added setup instructions, API usage, project structure, test
## Current Status

 Reusable MLflow wrapper implemented
 Automatic model registration completed
-Automatic Production alias promotion completed
-Dynamic model loading from MLflow Production alias
- Prediction API returns:
  - Predicted class label
  - Confidence score
  - Model version
  - Class probabilities
-  Batch prediction returns detailed prediction results
-  Health endpoint implemented
-  Unit tests added


## Verification

The application has been verified with the following workflow:

1. Train the model using `train.py`.
2. Register the model in the MLflow Model Registry.
3. Automatically promote the latest model to the **Production** alias.
4. Start the BentoML service.
5. Verify that the service loads the latest Production model.
6. Send prediction requests and confirm the API returns:
   - Correct prediction label
   - Confidence score
   - Current model version
   - Class probabilities

The end-to-end workflow has been successfully validated.