import os
import torch
import matplotlib.pyplot as plt

from torch.utils.data import TensorDataset, DataLoader
from torch import nn
from torch.optim import Adam

from data import generate_data, scale_data
from features import create_sequences
from model import DemandLSTM

# Create output folder
os.makedirs("output", exist_ok=True)

# -----------------------
# Load data
# -----------------------

df = generate_data()

scaled, scaler = scale_data(df["Demand"])

# -----------------------
# Create sequences
# -----------------------

LOOKBACK = 30
HORIZON = 7

X, y = create_sequences(
    scaled,
    lookback=LOOKBACK,
    horizon=HORIZON
)

X = torch.tensor(X, dtype=torch.float32)
y = torch.tensor(y.squeeze(-1), dtype=torch.float32)

# -----------------------
# DataLoader
# -----------------------

dataset = TensorDataset(X, y)

loader = DataLoader(
    dataset,
    batch_size=32,
    shuffle=True
)

# -----------------------
# Model
# -----------------------

model = DemandLSTM(
    input_size=1,
    hidden_size=64,
    num_layers=2,
    horizon=HORIZON
)

criterion = nn.MSELoss()

optimizer = Adam(
    model.parameters(),
    lr=0.001
)

EPOCHS = 50

losses = []

best_loss = float("inf")

# -----------------------
# Training
# -----------------------

for epoch in range(EPOCHS):

    epoch_loss = 0

    for xb, yb in loader:

        optimizer.zero_grad()

        output = model(xb)

        loss = criterion(output, yb)

        loss.backward()

        optimizer.step()

        epoch_loss += loss.item()

    epoch_loss /= len(loader)

    losses.append(epoch_loss)

    print(
        f"Epoch {epoch+1}/{EPOCHS} "
        f"Loss={epoch_loss:.5f}"
    )

    # Save best model

    if epoch_loss < best_loss:

        best_loss = epoch_loss

        torch.save(
            model.state_dict(),
            "output/best_model.pt"
        )

# -----------------------
# Loss Curve
# -----------------------

plt.figure(figsize=(8,5))

plt.plot(losses)

plt.xlabel("Epoch")

plt.ylabel("Loss")

plt.title("Training Loss")

plt.grid(True)

plt.savefig("output/loss_curve.png")

plt.show()

print("\nTraining Complete!")

print("Best Loss:", best_loss)