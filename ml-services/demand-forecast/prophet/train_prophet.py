from prophet import Prophet


def train_prophet(train_df):
    """
    Train Prophet model.
    """

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False
    )

    model.fit(train_df)

    return model


def predict_prophet(model, test_df):
    """
    Predict on test data.
    """

    forecast = model.predict(test_df[["ds"]])

    return forecast["yhat"].values