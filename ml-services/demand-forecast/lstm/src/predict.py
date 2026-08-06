import os
import torch
import matplotlib.pyplot as plt

from data import generate_data, load_scaler
from model import DemandLSTM


def predict(model_path="output/best_model.pt", scaler_path="output/scaler.pkl", lookback=30, horizon=7):
    """
    Loads trained model and scaler, processes the most recent observation window,
    and returns a forecast for the next `horizon` days.
    """
    # -----------------------
    # 1. Load Data & Persisted Scaler
    # -----------------------
    df = generate_data()
    raw_series = df["Demand"].values

    scaler = load_scaler(scaler_path)

    # Scale using the existing scaler (DO NOT RE-FIT)
    scaled_series = scaler.transform(raw_series.reshape(-1, 1))

    # Extract the latest lookback window
    last_sequence = scaled_series[-lookback:]

    X = torch.tensor(
        last_sequence.reshape(1, lookback, 1),
        dtype=torch.float32
    )

    # -----------------------
    # 2. Load Model & Predict
    # -----------------------
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found at {model_path}")

    model = DemandLSTM(
        input_size=1,
        hidden_size=64,
        num_layers=2,
        horizon=horizon
    )
    model.load_state_dict(torch.load(model_path))
    model.eval()

    with torch.no_grad():
        pred = model(X)

    # -----------------------
    # 3. Inverse Transform Forecast
    # -----------------------
    prediction = scaler.inverse_transform(
        pred.numpy().reshape(-1, 1)
    ).flatten()

    return prediction


def run_pipeline():
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    prediction = predict()

    print("\nNext 7 Days Forecast\n")
    for i, value in enumerate(prediction):
        print(f"Day {i+1}: {value:.2f}")

    # -----------------------
    # Plot Forecast
    # -----------------------
    plt.figure(figsize=(8, 4))
    plt.plot(range(1, 8), prediction, marker="o", linestyle="-", color="b")
    plt.title("Next 7 Days Demand Forecast")
    plt.xlabel("Day Ahead")
    plt.ylabel("Demand")
    plt.grid(True)

    plot_path = os.path.join(output_dir, "prediction.png")
    plt.savefig(plot_path)
    plt.show()


if __name__ == "__main__":
    run_pipeline()