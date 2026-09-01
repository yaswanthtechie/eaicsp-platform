from xgboost import XGBRegressor

from .config import XGBOOST_PARAMS


class XGBoostModel:

    def __init__(self):
        self.model = XGBRegressor(
            **XGBOOST_PARAMS
        )

    def fit(self, X, y):

        self.model.fit(X,y)

        return self

    def predict(self, X):

        return self.model.predict(X)