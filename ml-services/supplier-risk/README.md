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

<<<<<<< Updated upstream
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
=======
# Analyze text
result = analyze_sentiment("The supplier announced a major breakthrough in logistics.")
print(result) # {"label": "positive", "confidence": 0.95}
```

## Scoring Methodology Note

The overall risk score for a supplier is calculated as the average (mean) of all individual headline scores. An average is used instead of a sum to prevent large suppliers with high news volume from being unfairly penalized simply due to the quantity of coverage. It normalizes the risk score, providing a more balanced comparison between suppliers regardless of how frequently they appear in the news.

## Human Assessment

Below are the summarized risk assessments for 5 major suppliers based on recent news headlines.

### 1. Boeing
Boeing is facing significant challenges, including a strike by machinists, a lawsuit over safety violations, and an investigation into manufacturing processes. A recall of aircraft parts further highlights operational risks. Although there is a positive note with a massive partnership and positive earnings amidst delays, the threat of an FAA sanction keeps the risk level elevated.

### 2. Intel
Intel is undergoing a restructuring to focus on its foundry business alongside a $20 billion expansion. However, a massive layoff affecting 15% of its workforce and an EU antitrust investigation signal severe operational and reputational risks. A lawsuit and a supply chain disruption delaying a processor launch add to the concerns, culminating in a stock downgrade.

### 3. Tesla
Tesla is navigating a mix of operational and reputational challenges, including a major recall of 2 million vehicles and an investigation into battery fires. A class-action lawsuit and another round of layoffs impacting global sales teams underscore elevated risks. A stock downgrade and a supply chain shortage causing production disruption in Shanghai further amplify concerns, despite record earnings.

### 4. Nissan
Nissan's outlook involves a sweeping restructuring plan and a massive recall affecting over 1 million vehicles. Operational hurdles include a parts shortage and supply chain disruption leading to factory closures. Reputational risks arise from a lawsuit by former executives and a stock downgrade, though the conclusion of a past financial investigation offers a silver lining.

### 5. Foxconn
Foxconn is grappling with severe production disruption and a worker strike protesting conditions. An investigation into labor practices and a component shortage add to operational strains. The company is pursuing corporate restructuring to diversify and has denied allegations of fraud, successfully avoiding trade sanctions.
>>>>>>> Stashed changes
