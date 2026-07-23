import pandas as pd
import json

from src.make_messy_data import generate_messy_data
from validator import DataValidator
from rules import check_missing, check_duplicates, check_dates, check_negatives, check_strings

# 1. Simulate the client
generate_messy_data("../data/messy_sales.csv")

# Load data
data = pd.read_csv("../data/messy_sales.csv")

# THE FIX: Order matters!
# Put date and string standardizers BEFORE duplicates
my_ordered_rules = [
    check_dates,       # 1st: Converts '15/01/2024' -> '2024-01-15'
    check_strings,     # 2nd: Converts 'IPHONE-15' -> 'iphone 15'
    check_duplicates,  # 3rd: NOW it can catch all the newly unmasked duplicates!
    check_missing,     # 4th: Drops rows missing quantities
    check_negatives    # 5th: Flags negative quantities
]

dv = DataValidator(rules=my_ordered_rules)

# 1. First Validation
report = dv.validate(data)
print("--- INITIAL VALIDATION REPORT ---")
print(json.dumps(report, indent=2))

# 2. Clean Data (Executes cleaners in the order of my_ordered_rules)
clean_df = dv.clean(data)
print("\n--- CLEANED DATA ---")
print(clean_df.head(3).to_string())
# Save output
clean_df.to_csv("../data/clean_sales.csv", index=False)

# 3. Second Validation
clean_report = dv.validate(clean_df)
print("\n--- POST-CLEANING VALIDATION REPORT ---")
print(json.dumps(clean_report, indent=2, default=str))