import torch
import joblib
import matplotlib.pyplot as plt

from data import generate_data, scale_data
from model import DemandLSTM

LOOKBACK = 30
HORIZON = 7

df = generate_data()

scaled, scaler = scale_data(df["Demand"])

model = DemandLSTM(
    horizon=HORIZON
)

model.load_state_dict(
    torch.load("output/best_model.pt")
)

model.eval()

last_sequence = scaled[-LOOKBACK:]

X = torch.tensor(
    last_sequence.reshape(
        1,
        LOOKBACK,
        1
    ),
    dtype=torch.float32
)

with torch.no_grad():

    pred = model(X)

prediction = scaler.inverse_transform(
    pred.numpy().reshape(-1,1)
)

print("\nNext 7 Days Forecast\n")

for i,value in enumerate(prediction):

    print(
        f"Day {i+1}: {value[0]:.2f}"
    )

plt.figure(figsize=(8,4))

plt.plot(
    range(1,8),
    prediction,
    marker="o"
)

plt.title("Next 7 Day Forecast")

plt.xlabel("Day")

plt.ylabel("Demand")

plt.grid(True)

plt.savefig(
    "output/prediction.png"
)

plt.show()