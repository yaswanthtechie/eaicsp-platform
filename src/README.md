# LSTM Multi-Step Demand Forecasting

## Objective

Predict the next 7 days of demand using an LSTM model.

## Features

- Multi-step forecasting
- Walk-forward validation
- Naive baseline comparison
- MLflow experiment tracking
- MAE, RMSE, MAPE metrics
- Loss curve
- Prediction graph

## Folder Structure

```
src/
output/
requirements.txt
README.md
```

## Installation

```bash
python -m pip install -r requirements.txt
```
##
- cd src
## Train

```bash
python train.py
```

## Evaluate

```bash
python evaluate.py
```

## Predict

```bash
python predict.py
```

## Output

- best_model.pt
- loss_curve.png
- prediction.png

## Metrics

- MAE
- RMSE
- MAPE

## Future Improvements

- Attention LSTM
- Hyperparameter tuning
- Real-world dataset