import os
import joblib
import xgboost as xgb


def prepare_features(df):
    """
    Create numerical features from date.
    """

    data = df.copy()

    data["year"] = data["ds"].dt.year
    data["month"] = data["ds"].dt.month

    # Trend feature
    data["time_index"] = range(len(data))

    X = data[["year", "month", "time_index"]]
    y = data["y"]

    return X, y


def train_xgboost(train_df):
    """
    Train XGBoost model.
    """

    X_train, y_train = prepare_features(train_df)

    model = xgb.XGBRegressor(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=4,
        random_state=42
    )

    model.fit(X_train, y_train)

    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)

    # Save model
    joblib.dump(model, "output/xgb_model.pkl")

    print(" XGBoost model saved: output/xgb_model.pkl")

    return model


def predict_xgboost(model, test_df):
    """
    Predict using XGBoost.
    """

    X_test, _ = prepare_features(test_df)

    predictions = model.predict(X_test)

    return predictions