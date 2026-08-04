# Supplier Risk NLP Service

A FastAPI application that analyzes news headlines about suppliers to calculate a comprehensive risk score based on NLP sentiment analysis (FinBERT) and keyword detection (weighted signals for financial, operational, and reputational risks).

## Setup

<<<<<<< HEAD
1. Ensure you are installing into the right virtual environment (PowerShell):
   ```bash
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install requirements:
   ```bash
   python -m pip install -r requirements.txt
   ```

3. Run tests:
=======
1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```

2. Run tests:
>>>>>>> 062c2fc (Restore Supplier Risk ML service)
   ```bash
   pytest tests/
   ```

<<<<<<< HEAD
4. Start the API Server:
=======
3. Start the API Server:
>>>>>>> 062c2fc (Restore Supplier Risk ML service)
   ```bash
   uvicorn analyze:app --reload --port 8006
   ```

<<<<<<< HEAD
5. View documentation at `http://localhost:8006/docs`.
=======
4. View documentation at `http://localhost:8006/docs`.
>>>>>>> 062c2fc (Restore Supplier Risk ML service)

## Project Structure
- `data.py`: Loads the raw headlines dataset.
- `preprocess.py`: Contains text cleaning logic.
- `sentiment.py`: Encapsulates FinBERT pipeline and provides sentiment breakdown.
- `signals.py`: Detects domain-specific keywords and assigns risk weights.
- `analyze.py`: Exposes a FastAPI endpoint to invoke the pipeline over the dataset.
- `evaluate.py`: A standalone evaluation script against the realistic 50-headline dataset.

## Supplier Evaluation

The model was tested against a realistic dataset containing 10 headlines each for 5 major companies. Below are human observations regarding the model's performance:

**Boeing**
High risk because several headlines explicitly mention lawsuits, a strike, recalls, and regulatory investigations. The model accurately captures this high risk and the score seems reasonable.

**Intel**
Mixed news, including expansions and positive earnings, but also layoffs and a downgrade. The model's score reflects a moderate-to-high risk, which appears slightly conservative given the severity of a 15% layoff, but is balanced by the positive headlines.

**Tesla**
A highly volatile mix of recalls, lawsuits, and layoffs versus record earnings and expansions. The model penalizes Tesla heavily for the layoffs and recall keywords, potentially overestimating the overall business risk despite strong financial performance.

**Nissan**
Mostly operational disruptions (shortages, recalls) and restructuring efforts. The model captures the operational risk well, accurately balancing it against their new EV partnerships and positive earnings.

**Foxconn**
The model exhibits a clear limitation here. It assigns a very high risk score because headlines contain keywords like "fraud" and "sanction". However, the actual context of the headlines is "Foxconn *denies* allegations of fraud" and "Foxconn *avoids* sanction". The keyword-based model overestimates risk because it lacks contextual comprehension for negations.
