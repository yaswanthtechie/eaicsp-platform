# Sales Data Validation Pipeline

## Objective

This project simulates receiving messy sales data from a client, validates the data quality, cleans what can be safely corrected, and reports issues before the data is used for forecasting.

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