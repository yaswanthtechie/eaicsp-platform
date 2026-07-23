import numpy as np
import torch
import joblib

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    mean_absolute_percentage_error
)

from data import generate_data, scale_data
from features import create_sequences
from model import DemandLSTM


LOOKBACK = 30
HORIZON = 7

# -----------------------
# Load Data
# -----------------------

df = generate_data()

scaled, scaler = scale_data(df["Demand"])

X, y = create_sequences(
    scaled,
    LOOKBACK,
    HORIZON
)

split = int(len(X) * 0.8)

X_train = X[:split]
X_test = X[split:]

y_train = y[:split]
y_test = y[split:]

# -----------------------
# Load Model
# -----------------------

model = DemandLSTM(
    horizon=HORIZON
)

model.load_state_dict(
    torch.load("output/best_model.pt")
)

model.eval()

# -----------------------
# Walk Forward Validation
# -----------------------

predictions = []

for i in range(len(X_test)):

    sample = torch.tensor(
        X_test[i:i+1],
        dtype=torch.float32
    )

    with torch.no_grad():

        pred = model(sample)

    predictions.append(
        pred.numpy()[0]
    )

predictions = np.array(predictions)

# -----------------------
# Inverse Scaling
# -----------------------

pred_inv = scaler.inverse_transform(
    predictions.reshape(-1,1)
).reshape(predictions.shape)

actual_inv = scaler.inverse_transform(
    y_test.reshape(-1,1)
).reshape(y_test.shape)

# -----------------------
# Metrics
# -----------------------

mae = mean_absolute_error(
    actual_inv.flatten(),
    pred_inv.flatten()
)

rmse = np.sqrt(
    mean_squared_error(
        actual_inv.flatten(),
        pred_inv.flatten()
    )
)

mape = mean_absolute_percentage_error(
    actual_inv.flatten(),
    pred_inv.flatten()
)

print("\nLSTM RESULTS")

print("MAE :", mae)

print("RMSE:", rmse)

print("MAPE:", mape)

# -----------------------
# Naive Baseline
# -----------------------

naive = []

for row in X_test:

    last = row[-1]

    naive.append(
        np.repeat(last, HORIZON)
    )

naive = np.array(naive)

naive = scaler.inverse_transform(
    naive.reshape(-1,1)
).reshape(naive.shape)

naive_mae = mean_absolute_error(
    actual_inv.flatten(),
    naive.flatten()
)

naive_rmse = np.sqrt(
    mean_squared_error(
        actual_inv.flatten(),
        naive.flatten()
    )
)

print("\nNAIVE BASELINE")

print("MAE :", naive_mae)

print("RMSE:", naive_rmse)