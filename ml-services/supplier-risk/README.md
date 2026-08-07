# Supplier Risk NLP Service

A FastAPI application that analyzes news headlines about suppliers to calculate a comprehensive risk score based on NLP sentiment analysis (FinBERT) and keyword detection (weighted signals for financial, operational, and reputational risks).

## Setup

1. Create and activate a virtual environment (example using venv):
   ```bash
   python -m venv .venv
   # macOS / Linux
   source .venv/bin/activate
   # Windows (PowerShell)
   .\.venv\Scripts\Activate.ps1
   ```

2. Install pinned requirements:
   ```bash
   python -m pip install -r requirements.txt
   ```

3. Run tests (note: tests mock the heavy FinBERT download by default):
   ```bash
   pytest tests/
   ```

4. Start the API Server (optional):
   ```bash
   cd src
   uvicorn analyze:app --reload --port 8006
   ```

View documentation at `http://localhost:8006/docs` when the server is running.

## Project Structure
- `data.py`: Loads the raw headlines dataset.
- `preprocess.py`: Contains text cleaning logic.
- `sentiment.py`: Encapsulates FinBERT pipeline and provides sentiment breakdown.
- `signals.py`: Detects domain-specific keywords and assigns risk weights.
- `predict.py`: Orchestrates the pipeline and returns the required summary schema.
- `analyze.py`: Exposes a FastAPI endpoint to invoke the pipeline over the dataset.
- `evaluate.py`: A standalone evaluation script against the 50-headline dataset.
- `supplier_headlines.json`: The 50-headline evaluation dataset (5 suppliers × 10 headlines).

## Scoring Methodology Note

The overall risk score for a supplier is calculated as the mean of all individual headline scores and is capped at 100. This normalizes for differing news volumes across suppliers so that coverage frequency doesn't unfairly dominate the score.

## Limitations and Notes

- Keyword detection is intentionally simple (word/phrase matching with weights). This can lead to false positives when a headline contains a keyword in a negated context (e.g., "denies fraud"). We document this limitation and recommend adding basic negation handling or phrase-level context as a next improvement.
- Unit tests are configured to mock the FinBERT sentiment pipeline to avoid large downloads in CI. An optional integration test against the real model can be added separately and gated behind an environment variable.

## Human Assessment

The evaluation dataset includes 5 suppliers with hand-picked headlines. The README contains a short human-level summary for each supplier describing whether the model's outputs align with a quick human read. See `supplier_headlines.json` and `evaluate.py` for details on running the evaluation locally.
