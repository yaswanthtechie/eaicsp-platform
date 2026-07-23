import sys
from pathlib import Path

import joblib
import pandas as pd

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.isolation_forest_model import IsolationForestModel
from src.lof_model import LOFModel
from src.one_class_svm_model import OneClassSVMModel

data_path = project_root / "output" / "sensor_readings_with_anomalies.csv"
models_dir = project_root / "models"
models_dir.mkdir(parents=True, exist_ok=True)

if not data_path.exists():
    raise FileNotFoundError(f"Training data not found at {data_path}")


df = pd.read_csv(data_path)
features = df[["temperature", "humidity", "stock_count"]].to_numpy()

# Isolation Forest Model
model1 = IsolationForestModel()
model1.train(features)
joblib.dump(model1.model, models_dir / "isolation_forest_model.joblib")

print("Isolation Forest model is trained")
print("=" * 50)

# One-Class SVM Model
model2 = OneClassSVMModel()
model2.train(features)
joblib.dump(model2.model, models_dir / "one_class_svm_model.joblib")

print("One-Class SVM model is trained")
print("=" * 50)

# Local Outlier Factor Model
model3 = LOFModel()
model3.train(features)
joblib.dump(model3.model, models_dir / "lof_model.joblib")

print("Local Outlier Factor model is trained")
