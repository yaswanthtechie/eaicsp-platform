"""
The sales anomaly detector as an MLflow model (R15-K6).

Registering this model in the MLflow model registry records the chosen
configuration as a version: the registered artifacts hold a copy of the
service code (code_paths, including src/config.py with every threshold) and
the thresholds as config.json. The z_spike threshold is applied from
config.json. Load the version in a fresh process (not one that has already
imported this service's own `src`), or predict() runs the live code with the
live thresholds instead of the registered copy.

predict() takes a sales frame (sale_date or date, sku_id or product_code,
warehouse_id or warehouse, quantity_sold) and returns the scored days, as
src.sales_anomaly.detect does.

mlflow is only imported where this module is used (registration and loading),
so the detector itself does not need it.
"""

import json

from mlflow.pyfunc import PythonModel


class SalesAnomalyModel(PythonModel):
    def load_context(self, context):

        with open(context.artifacts["config"], encoding="utf-8") as handle:
            self.config = json.load(handle)

    def predict(self, context, model_input, params=None):

        # src comes from the code_paths copy stored with the model version.
        from src.sales_anomaly import detect

        scores, _ = detect(model_input, z_spike=self.config["z_spike"])

        return scores
