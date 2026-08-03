# Supplier Risk

The Supplier Risk microservice evaluates supplier risks based on news headlines and various signals using Machine Learning models.

## Features

- **Sentiment Analysis**: Uses HuggingFace's `ProsusAI/finbert` to analyze the sentiment of supplier-related text and headlines.
- **Risk Prediction**: Evaluates overall supplier risk scores.
- **FastAPI Integration**: Can be integrated directly into the API gateway.

## Setup

Ensure you have the required dependencies installed:

```bash
python -m pip install -r requirements.txt
```

## Usage

```python
from sentiment import analyze_sentiment, init_model

# Initialize the model on startup
init_model()

# Analyze text
result = analyze_sentiment("The supplier announced a major breakthrough in logistics.")
print(result) # {"label": "positive", "confidence": 0.95}
```
