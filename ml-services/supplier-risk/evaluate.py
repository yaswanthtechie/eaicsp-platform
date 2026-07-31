"""
Evaluation script for the Supplier Risk NLP pipeline.
"""
import json
from collections import defaultdict
from predict import predict
from sentiment import init_model

def load_dataset(filepath: str):
    """Load the evaluation dataset from a JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def run_evaluation():
    """Run the evaluation script and print the summary for each supplier."""
    print("Initializing NLP model...")
    init_model()
    
    dataset = load_dataset("supplier_headlines.json")
    
    # Group by supplier
    grouped_headlines = defaultdict(list)
    for item in dataset:
        grouped_headlines[item['supplier']].append(item['headline'])
        
    print("\n--- Evaluation Results ---\n")
    
    for supplier, headlines in grouped_headlines.items():
        summary = predict(supplier, headlines)
        
        print(f"Supplier: {summary['supplier']}")
        print(f"Risk Score: {summary['risk_score']}")
        
        print("Signals:")
        if not summary['signals']:
            print("- None")
        else:
            for signal in summary['signals']:
                print(f"- {signal['keyword']}")
                
        print("\nSentiment:")
        print(f"Positive: {summary['sentiment_breakdown']['positive']}")
        print(f"Neutral: {summary['sentiment_breakdown']['neutral']}")
        print(f"Negative: {summary['sentiment_breakdown']['negative']}")
        
        print("\nWorst Headlines:")
        for idx, headline_info in enumerate(summary['top_worst_3'], 1):
            print(f"{idx}. {headline_info['headline']}")
            
        print("\n" + "="*40 + "\n")

if __name__ == "__main__":
    run_evaluation()
