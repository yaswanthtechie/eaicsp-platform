import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import joblib


def generate_data(days=1000):
    """
    Generate synthetic demand data
    """

    np.random.seed(42)

    t = np.arange(days)

    trend = t * 0.03

    yearly = 20 * np.sin(2 * np.pi * t / 365)

    weekly = 8 * np.sin(2 * np.pi * t / 7)

    noise = np.random.normal(0, 2, days)

    demand = 100 + trend + yearly + weekly + noise

    df = pd.DataFrame({
        "Day": t,
        "Demand": demand
    })

    return df


def scale_data(series):

    scaler = MinMaxScaler()

    scaled = scaler.fit_transform(series.values.reshape(-1,1))

    joblib.dump(scaler,"output/scaler.pkl")

    return scaled, scaler