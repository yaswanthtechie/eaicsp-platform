# Sales Data Validation Pipeline

## Objective

This project simulates receiving messy sales data from a client, validates the data quality, 
cleans what can be safely corrected, and reports issues before the data is used for downstream forecasting. 
The data schema aligns perfectly with the target `sales_fact` table (`date`, `sku_id`, `warehouse_id`, `quantity_sold`, `unit_price`).

## Project Structure

```text
.
├── configs/
│   └── sales_rules.yaml       # Defines the data quality rules and severities
├── data/
│   ├── messy_sales.csv        # Auto-generated messy data (Input)
│   └── clean_sales.csv        # Sanitized data ready for the warehouse (Output)
├── logs/
│   └── validation_*.log       # Timestamps logs tracking rule failures and data drift
├── src/
│   ├── main.py                # Pipeline orchestrator and CLI entrypoint
│   ├── make_messy_data.py     # Generates synthetic client data mapped to the sales_fact schema
│   ├── validator.py           # Core Pydantic-powered validation engine (Quality Gate)
│   └── custom_rules.py        # User-defined validation and transformation functions
├── requirements.txt           # Project dependencies
└── README.md                  # This documentation
```

## Pipeline

1. Generate intentionally messy sales data.
2. Validate common data quality issues.
3. Clean recoverable problems.
4. Export cleaned dataset.

## Issues Detected

- Missing quantities
- Duplicate rows
- Negative quantities
- Invalid dates

## Cleaning Performed

- Parsed multiple date formats into a single datetime format.
- Removed exact duplicate rows.
- Standardized product names by:
  - converting to lowercase
  - removing leading/trailing spaces
  - removing hyphens

## Decision on Negative Quantities

Negative quantities are **flagged but not removed or changed**.

### Why?

A negative quantity can represent several business situations:

- customer return
- refund
- data entry error
- inventory correction

Automatically changing negatives to zero or deleting those rows risks losing valid business events.

Instead, this pipeline flags them for manual review while preserving the original data. This approach maintains data integrity and allows domain experts to determine whether each record is legitimate before model training.

This is generally the safest strategy in production data pipelines.

# Data Quality Validator (Vivek's Quality Gate):
- A configuration-driven data quality firewall designed to sit between raw data ingestion and the data warehouse. 
- It evaluates business rules defined in YAML, automatically validating data and dropping bad rows before they reach downstream ML models

## 1. Defining Rules (YAML):
- ERROR severity: Flags the pipeline and drops the offending rows during cleaning.
- WARNING severity: Logs the anomaly to track data drift but allows the row to pass through.
```yaml
  # configs/sales_rules.yaml
#  some of the rules provided here 
rules:
  # --- SIMPLE RULES (Built-in) ---
  - name: date_not_null
    field: date
    type: not_null
    severity: ERROR

  - name: unit_price_valid
    field: unit_price
    type: range
    min: 0.01
    severity: ERROR

  # --- COMPLEX RULES (Custom Escape Hatch) ---  
  - name: composite_pk_unique
    type: custom
    function: src.custom_rules.check_composite_unique
    subset: ['date', 'sku_id', 'warehouse_id']
    severity: ERROR

  - name: flag_negative_quantities
    field: quantity_sold
    type: transform
    function: src.custom_rules.flag_negatives
    severity: INFO
```

## 2. Custom Rules Extensibility
- If you need a validation check that standard YAML properties do not support, use the custom or transform rule types.  
- This allows you to dynamically point to external Python functions while maintaining the separation of configuration and execution.
### Calling Convention: 
- All user-supplied Python functions must accept the Pandas DataFrame as the first positional argument. 
- All other configuration properties (including field) are injected dynamically as keyword arguments.

## 3. Integrating with Pipelines
- The DataValidator acts as a drop-in quality gate for orchestrators like Airflow, Prefect, or Dagster.
- The validate() method returns a Pydantic ValidationResult object, offering clean attribute access for pipeline branching.
- Empty data batches will automatically register as a WARNING
- Here is the standard implementation pattern to plug it into your pipeline:

```Python
import pandas as pd
from src.validator import DataValidator

def quality_gate(df: pd.DataFrame, config_path: str):
    """
    Pipeline Node: Validates incoming data batches before warehouse ingestion.
    """
    # 1. Initialize validator from YAML config
    validator = DataValidator.from_config(config_path)
    
    # 2. Evaluate dataset against all rules
    result = validator.validate(df)
    
    # 3. Handle pipeline errors and alert using standard attribute access
    if not result.passed:
        print(f"GATE FAILED: {result.total_rows_affected} rows affected.")
        
        for err in result.errors:
            print(f"  -> Rule: {err['rule']} | Field: {err['field']} | Count: {err['count']} rows failed")
                
        # Return payload for Dead Letter Queue (DLQ) processing
        return "REJECT_BATCH", result.errors
        
    # 4. Return strictly cleaned dataset if valid
    # strict=True drops any rows that triggered an ERROR-level rule
    clean_df = validator.clean(df, strict=True)
    print(f"GATE PASSED: {len(clean_df)} valid rows ready for ingestion.")
    
    return "PROCEED", clean_df

```

## 3. How to run main.py
```commandline
id ../data/messy_
Standard run
python -m src.main --input data/messy_sales.csv --config configs/sales_rules.yaml

Force generation of new synthetic data
python -m src.main --generate
```
## Output

Running the project generates:

- `data/messy_sales.csv`
- `data/cleam_sales.csv`
- `logs/validation_time-stamp.log`
