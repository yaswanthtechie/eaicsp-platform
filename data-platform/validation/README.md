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
python -m src.validate_cli --file data/messy_sales.csv --config configs/sales_rules.yaml --output reports/output.json

Force generation of new synthetic data
python -m src.main --generate
```
## Output

Running the project generates:

- `data/messy_sales.csv`
- `data/cleam_sales.csv`
- `logs/validation_time-stamp.log`


# Rule Versioning (The Contract Update):
- Rule versioning is critical for auditing data drift and understanding pipeline behavior over time. 
- By embedding a version string in your configuration, every validation report explicitly states which rule set was active during execution. 
- This ensures that if a data batch that passed in previous batch fails in present batch, we can quickly trace the discrepancy back to a specific configuration change.

## Configuration (YAML):
- Added a version string at the root level of the rules configuration file.
```yaml
# configs/sales_rules.yaml
version: "1.1.0"
rules:
  - name: date_not_null
    field: date
    type: not_null
    severity: ERROR
```

## Output (JSON Report):
- The CLI and pipeline orchestrator will automatically extract this version from the YAML and inject it into the final ValidationResult payload. 
- This makes it highly trackable for downstream CI/CD jobs 
```json
{
  "config_version": "1.1.0",
  "passed": false,
  "total_rows_affected": 8,
  "errors": [
    {
      "rule": "date_not_null",
      "field": "date",
      "count": 1
    }
  ]
}
```

# Standalone Validation CLI (validate_cli.py):
- The project includes a standalone command-line interface designed to act as a quality gate for CI/CD workflows and automated pipelines. 
- It runs the data validator engine, exports a detailed JSON summary, and returns standard system exit codes based on the validation results.

## CLI Arguments:
- --file: The file path to the input CSV dataset (e.g., data/messy_sales.csv).
- --config: The file path to your YAML configuration rules (e.g., configs/sales_rules.yaml).  
- --output: The destination path where the JSON validation report will be saved (e.g., reports/output.json).

## Integration & Behavior:
- JSON Reporting: The CLI extracts the full ValidationResult (including error counts, rows affected, and the configuration version) and exports it to the path specified in --output
- CI/CD Exit Codes: The script behaves like a standard Unix utility. If the data passes all ERROR-level rules, it exits with code 0 (Success). If validation fails, it exits with code 1 (Failure), automatically halting pipeline runners like GitHub Actions or Jenkins.

## How to Run:
It is recommended to run the CLI as a module from the root directory of the project. Here are standard execution examples:  
```commandline
# Standard validation run
python -m src.validate_cli --file data/messy_sales.csv --config configs/sales_rules.yaml --output reports/output.json

# Running against alternative datasets and rulesets
python -m src.validate_cli --file data/messy_sales_1.csv --config configs/sales_rules_1.yaml --output reports/output_1.json
python -m src.validate_cli --file data/messy_sales_2.csv --config configs/sales_rules_2.yaml --output reports/output_2.json
```
Alternatively, if you prefer not to use the module flag, you can execute using pyproject.toml cofig file:
```commandline
pip install -e .
validate_data --file data/messy_sales.csv --config configs/sales_rules.yaml --output reports/output.json
```

# Configuring pyproject.toml file:
- In true enterprise environments, the standard is to not call python directly at all. 
- Instead, the project is packaged using a pyproject.toml file with defined console_scripts. 
- This installs your CLI tool directly into the virtual environment, allowing you to run it like a native system command from anywhere.

## Step 1: Create pyproject.toml
```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "data-validator"
version = "1.0.0"
description = "A configuration-driven data quality firewall."
readme = "README.md"
requires-python = ">=3.9"
dependencies = [
    "pandas",
    "pydantic",
    "pyyaml"
]

[project.scripts]
# This is the magic line.
# It maps the terminal command 'validate-data' to the 'main' function inside 'src/validate_cli.py'
validate_data = "src.validate_cli:main"

# for generating the synthetic data
generate_messy_data = "src.make_messy_data:main"

# for running the complete orchestrator pipeline
run_pipeline = "src.main:main"

[tool.setuptools]
packages = ["src"]
```

## Step 2: Install the Package Locally:
- Ensure your Conda environment (where your app is running) is activated. 
- Then, run the following pip command from your root validation/ directory (where the pyproject.toml file is located):
```commandline
pip install -e .
```
- The -e flag stands for "editable". This means if you change the code inside src/validate_cli.py, you do not have to reinstall the package for the changes to take effect.
- The dot (.) tells pip to install the package located in your current folder.

## Step 3: Run Your Native Command:
- You no longer need to call python, use -m, or worry about file paths. 
- The tool is now installed globally in your Conda environment as an executable command.
- You can run your validation from anywhere on your machine using this exact command:
```commandline
# src.validate_cli:main
validate_data --file data/messy_sales.csv --config configs/sales_rules.yaml --output reports/output.json

# "src.make_messy_data:main"
generate_messy_data

#"src.main:main"
run_pipeline
```

# Performance Benchmarking (perf_test.py):

## Objective:
- To guarantee performance at scale, this project includes a dedicated benchmarking script. 
- This utility allows you to generate a 100,000-row file to stress-test the validation pipeline. 
- The primary goal is to confirm your rules run in vectorized pandas, not Python loops. 
- The script will measure and log the actual time taken to validate the dataset. 
- This ensures that if it's slow, you can profile and fix before moving on.

## Features:
- **Scalable Data Generation:** Dynamically generate hundreds of thousands of rows on the fly to test pipeline limits.
- **Strict Time Thresholds:** Define maximum acceptable execution durations. The script warns if the validation exceeds this threshold, acting as a performance gate in CI/CD.
- **Audit Logging:** Automatically outputs metrics to the console and generates timestamped audit files in the logs/ directory for historical performance tracking.

## CLI Arguments:
- --data-path: Path where test data will be generated and read from (default: data/perf_100k_sales.csv).
- --config-path: Path to the YAML validation rules (default: configs/sales_rules.yaml).
- --n-rows: Number of rows to generate (default: 100000).
- --time-threshold: Maximum acceptable execution duration in seconds (default: 3.0).
- --log-dir: Directory for saving timestamped log files (default: logs).
- --log-level: Set the standard logging level (default: INFO).

## How to Run:
- You can execute the performance test using standard Python execution from the root directory:
```commandline
# Standard 100k row benchmark using defaults
python -m src.perf_test

# Stress test with 500k rows and a strict 5-second limit
python -m src.perf_test --n-rows 500000 --time-threshold 5.0
```

### Adding to pyproject.toml:
- To follow your existing enterprise standards, add perf_test.py to [project.scripts] section in pyproject.toml
```toml
# for running the  Performance at scale Generate a 100,000-row file
perf_test = "src.perf_test:main"
```
```commandline
pip install -e .
perf_test --n-rows 100000 --time-threshold 4.5
```

### Performance Benchmark Results

The validation engine uses heavily optimized, vectorized pandas operations. Scaling tests demonstrate that throughput actually rises with volume. 

A standard benchmark run validates over 100,000 rows in less than a quarter of a second:

> **Rows processed:** 103,100 | **Rules evaluated:** 10 | **Total Execution Time:** 0.3106 seconds

**Scaling Performance:**
* 10,310 rows -> 0.0765s (1,34,771 rows/sec)
* 103,100 rows -> 0.3106 (3,31,938 rows/sec)
* 515,500 rows -> 1.4223s (3,62,441 rows/sec)
* 1,000,000 rows -> 2.8406s (3,52,038 rows/sec)

# Batch Folder Validation (validate_folder.py):

## Objective:
- The validate_folder.py script scales the validation engine to handle entire directories of data files at once. 
- It introduces a routing mechanism that dynamically maps specific CSV file patterns to their corresponding YAML configuration rules. 
- This is ideal for processing daily data lake partitions or batch uploads where multiple datasets with different schemas arrive simultaneously.

## Features:
- **Dynamic Routing:** Use a JSON mapping file to route different file patterns (e.g., sales_*.csv vs hr_data.csv) to entirely different YAML rulesets.
- **Automated JSON Reporting:** Optionally export detailed, row-level JSON error reports for every file processed, alongside a master aggregate summary for the batch.
- **Resilient Processing:** Automatically handles corrupt, empty, or unreadable files by logging the failure and safely continuing the batch job
- **Validator Caching:** Optimizes CPU and I/O by parsing YAML configurations only once and caching the validator objects in memory.

## CLI Arguments:
- --folder: The target directory containing the data files to validate.
- --mapping: Path to a JSON file mapping glob patterns to YAML config files (Mutually exclusive with --config).
- --config: Path to a single YAML config file to apply to all discovered files (Mutually exclusive with --mapping).
- --pattern: File pattern to match when using a single config (default: *.csv).
- --save-reports: Flag to enable generating and saving detailed JSON reports to disk.
- --output-dir: Destination folder for JSON reports when --save-reports is active (default: reports).
- --top-n: Number of top error rules to summarize in the final log output (default: 3).

## The Routing Map:
- When dealing with multiple data sources, create a JSON routing file (e.g., routing_map.json) to dictate which rules apply to which files. 
- The engine will match the keys against the files in your folder.
```json
{
  "sales_*.csv": "configs/sales_rules.yaml"
}
```

## How to Run:
- You can execute this module directly from the root directory:
```commandline
# Log-only mode using a mapping file (Fastest)
python -m src.validate_folder --folder data/ --mapping routing_map.json

# Run against a folder using a single config and generate JSON reports
python -m src.validate_folder --folder data/ --config configs/sales_rules.yaml --save-reports --output-dir reports/
```

### Adding to pyproject.toml:
- In true enterprise environments, the standard is to not call python directly at all. 
- We can integrate this batch processor into your existing pyproject.toml file alongside your other commands.
- Add the following line to your [project.scripts] section:
```toml
# for batch validating multiple files and folders
validate_folder = "src.validate_folder:main"
```
- Once added, install the package locally using the editable flag:
```commandline
pip install -e .
```
You can now trigger batch validations from anywhere on your machine as a native system command:
```commandline
validate_folder --folder data/ --mapping .\configs\routing_map.json --save-reports --output-dir .\reports\csv_files_report
```

# Rule Dependencies (depends_on):
- The validation engine supports rule dependencies to prevent "cascading" errors on garbage data. 
- By using the depends_on parameter, you can suppress downstream rule evaluations for a specific row if it has already been flagged by a foundational rule.
- This ensures cleaner logs, prevents redundant error reporting, and guarantees that complex mathematical or pattern-based rules do not waste resources evaluating fundamentally broken data.

## How It Works:
- When a rule evaluates a dataset, it generates a boolean failure mask. 
- If a rule has a depends_on configuration, the engine checks the failure masks of the specified parent rules. 
- It then applies a bitwise AND NOT operation (mask & ~parent_mask) to explicitly ignore any rows that the parent rule already caught.

## Configuration Example:
In your YAML configuration, add the depends_on key as a list of parent rule names.
```yaml
rules:
  # 1. Foundational Rule: Catches completely unparseable strings
  - name: unparseable_dates
    field: date
    type: custom
    function: src.custom_rules.check_unparseable_dates
    severity: ERROR

  # 2. Dependent Rule: Only evaluates rows that passed the 'unparseable_dates' rule
  - name: date_in_range
    field: date
    type: range
    min: '2024-01-01'
    max: '2026-12-31'
    severity: WARNING
    depends_on: ["unparseable_dates"]
```

## Important Behaviors & Best Practices:
- **Sequential Execution:** The validation engine processes rules top-to-bottom as they appear in the YAML file. Parent rules must be defined before the rules that depend on them.
- **Missing Dependencies:** If a rule specifies a dependency that has not been executed yet (or does not exist), the engine will gracefully log a WARNING and evaluate the rule normally without suppression.
- **Cleaning Phase:** Dependencies are fully respected during the clean() phase as well. If a row is targeted for removal by a parent rule, it will not be double-counted or redundantly processed by dependent rules.


# 1. Secure Custom Rule Registry

- Security is paramount when allowing configuration-driven code execution. 
- To prevent malicious actors from injecting arbitrary system commands via the YAML configuration, the dynamic import engine is locked behind a strict allow-list.

## How It Works:
- The pipeline does not blindly use `eval()` or `importlib` on the string provided in the `function` key.
- All user-defined functions must be explicitly mapped in the `SAFE_FUNCTION_REGISTRY` inside `src/validator.py`.
- **Provable Safety:** If a configuration file attempts to load an unregistered or malicious function (e.g., `os.system`), the validator immediately raises a `SecurityError` and halts execution before any data is processed.

# 2. Rule Conflict Detection

- To prevent wasted compute cycles on validation checks that can never pass, the engine evaluates the logical integrity of your YAML configuration at load time.

## How It Works:
- When the `DataValidator` initializes, it maps out the boundaries of all numerical constraints (like `range` rules).
- **Intra-rule Conflicts:** If a single rule is impossible (e.g., `min: 100`, `max: 10`), it immediately raises a `ValueError`.
- **Inter-rule Conflicts:** If two separate rules mathematically contradict each other on the same field (e.g., one requires `quantity > 0` and another requires `quantity < -1`), the engine detects the overlap and aborts pipeline startup.

# 3. The Golden Regression Suite

- As custom rules evolve, there is a risk that tweaking a Python function might accidentally alter its baseline behavior (a regression). 
- To prevent this, the project includes a fixed "Golden Regression" suite.

## How It Works:
- A static, "known messy" dataset (`data/messy_sales_500.csv`) is paired with a strictly controlled test script (`tests/test_regression.py`).
- The test asserts exact, hardcoded expectations—down to the specific number of rows each rule is expected to flag.
- Executing `pytest` automatically runs this suite, acting as a strict safety net when refactoring code. If a rule's logic breaks, the regression test fails instantly.

# 4. Performance Profiling Per Rule

When a pipeline runs slowly, aggregate execution times are not enough to find the bottleneck. The validation engine tracks and logs the exact execution duration of every individual rule down to the microsecond.

## How It Works:
- High-resolution timers wrap the evaluation logic for each rule.
- The `ValidationResult` object now includes a `rule_timings` dictionary and a `slowest_rule` property.
- When executing via `main.py` or `perf_test.py`, the CLI automatically prints a sorted performance breakdown so data engineers can target the exact rule that needs optimization.

```text
--- RULE TIMINGS (Slowest First) ---
  • unparseable_dates              : 0.114520s
  • composite_pk_unique            : 0.082140s
  • sku_format                     : 0.045230s
  • unit_price_valid               : 0.002130s
```
# 5. Incremental Validation (Watermarking)
- For large datasets, re-validating the entire historical file every day is inefficient. 
- The incremental validation feature allows the pipeline to process only the newly arrived rows (the delta).

## How It Works:
- **State Tracking:** The engine requires a monotonic identifier, such as a sequential transaction_id or an updated_at timestamp.
- **Pre-Filtering:** Upon execution, the pipeline reads the previous high-water mark from a hidden state file (e.g., .watermark.json). It strictly filters the incoming data (df = df[df['id'] > last_watermark]) before validation begins.
- **Append Mode:** If validation passes, the engine intelligently appends the new rows to the existing output file (skipping headers) and updates the local state file to the new maximum ID.

## CLI Arguments:
- --incremental: Enables the watermarking engine.
- --watermark-col: Defines the column to track (e.g., transaction_id).

### without pyproject.toml config:
```commandline
# Standard incremental run
python -m src.main --incremental --watermark-col "transaction_id"

# validate_cli run
python -m src.validate_cli --file data/messy_sales.csv --config configs/sales_rules.yaml --output reports/cli_report.json --incremental --watermark-col "transaction_id"

# Batch processing multiple files incrementally
python -m src.validate_folder --folder data/ --config configs/sales_rules.yaml --save-reports --output-dir reports/ --incremental --watermark-col "transaction_id"
```

### with pyproject.toml config:
```commandline
pip install -e .

# Standard incremental run
run_pipeline --incremental --watermark-col ""transaction_id"

# validate_cli run
validate_data --file data/messy_sales.csv --config configs/sales_rules.yaml --output reports/cli_report.json --incremental --watermark-col "transaction_id"

# Batch processing multiple files incrementally
validate_folder --folder data/ --config configs/sales_rules.yaml --save-reports --output-dir reports/op --incremental --watermark-col "transaction_id"
```

# Known Limitations
* **Watermark Advancement:** The incremental pipeline advances the watermark based on the incoming dataset, *including rows that fail validation*. Failed rows are not automatically queued for reprocessing.
* **Date Sorting:** String-based watermark columns (like dates) are compared lexicographically. ISO-8601 (`YYYY-MM-DD`) works flawlessly; localized formats (`MM/DD/YYYY`) will filter incorrectly.
* **Incremental Write Amplification:** Append mode rewrites the entire output file each run (read_csv → concat → drop_duplicates → to_csv), which is O(total rows) per run rather than O(new rows). This is deliberate: the drop_duplicates pass makes the pipeline crash-safe if a run dies between writing data and writing the watermark. A plain to_csv(mode='a') would be cheaper but would double-write rows on a mid-run failure.
* **Deduplication:** Incremental append mode deduplicates based on full-row identity. Updates to existing records require a genuine Primary Key configuration (currently unsupported).
* **Conflict Detection Boundaries:** The _detect_conflicts method only catches impossible range vs range bounds. Contradictions between not_null + strict regex, or unique + custom duplicate checks on the same field currently pass through undetected.




# Validation Profiles

## Feature Description
The **Validation Profiles** feature allows you to define multiple named rule-sets (e.g., `default`, `strict`, `lenient`, `sales`, `finance`) inside a **single YAML configuration file**. 

Previously, if you needed to change a single threshold for a specific pipeline run, you had to duplicate the entire YAML file, leading to a maintenance nightmare. With Validation Profiles, you can apply the **DRY (Don't Repeat Yourself)** principle by defining core rules once and creating specialized profiles that inherit and override those rules as needed.

## ⚙️ How It Works
The engine dynamically builds a tailored rule-set in memory just before execution based on your CLI arguments.

1. **Hierarchical Structure:** The YAML configuration now uses a `profiles:` key.
2. **Single-Level Inheritance:** A profile can use the `inherits: <profile_name>` key to pull in all rules from a parent profile (usually `default`).
3. **Smart Overrides:** If a child profile defines a rule with the *same name* as a rule in its parent profile, the child's version completely overwrites the parent's version. 
4. **Loud Fallbacks:** If you do not specify a profile via the CLI, the system will automatically look for and run the `default` profile, logging this action clearly so you always know what rules were applied.
5. **Fail-Fast Security:** If you specify a profile that does not exist (e.g., a typo like `--profile strct`), the pipeline will immediately halt and throw an error to prevent you from accidentally validating data against the wrong rules.

### Configuration Example
```yaml
version: "1.0.0"
profiles:
  default:
    rules:
      - name: date_not_null
        field: date
        type: not_null
        severity: ERROR
      - name: quantity_positive
        field: quantity_sold
        type: range
        min: 0
        severity: WARNING  # Warns on negative numbers

  strict:
    inherits: default
    rules:
      - name: quantity_positive  # Overrides the parent rule
        field: quantity_sold
        type: range
        min: 1
        severity: ERROR    # Fails and drops rows with 0 or negative numbers
```

## How to Run:
* All core CLI scripts have been updated to support the --profile and --list-profiles arguments.

### 1. List Available Profiles:
* Don't want to open the YAML file? You can ask the CLI to list all available profiles in a given config file. This intercepts the script and exits cleanly without running any data processing.
```commandline
python -m src.main --list-profiles
python -m src.validate_cli --config configs/sales_rules.yaml --list-profiles
python -m src.validate_folder --config configs/sales_rules.yaml --list-profiles
```

### 2. Standard Pipeline (main.py)
* Run your end-to-end simulation and validation flow.
```commandline
# Automatically falls back to the 'default' profile
python -m src.main

# Explicitly run the 'strict' profile
python -m src.main --profile strict
```

### 3. CI/CD Pipeline Gate (validate_cli.py)
* Run the strict validation gate designed for automated environments.
```commandline
python -m src.validate_cli --file data/messy_sales.csv --config configs/sales_rules.yaml --profile strict --output reports/report.json
```

### 4. Batch Folder Validation (validate_folder.py)
* Apply profiles across an entire directory of CSV files.

#### Single Profile for the Whole Folder:
```commandline
python -m src.validate_folder --folder data/ --config configs/sales_rules.yaml --profile strict --save-reports
```

#### Hybrid Mapping (Advanced):
* If you are using a mapping.json file to route different data to different configs, you can now define specific profiles directly inside the JSON mapping!
```json
{
  "sales_data/*.csv": "configs/sales_rules.yaml", 
  "finance_data/*.csv": {
    "config": "configs/finance_rules.yaml",
    "profile": "strict"
  }
}
```
```commandline
python validate_folder.py --folder data/ --mapping configs/mapping.json
```


# Config-Driven Data Validation Pipeline

This project is a robust, config-driven data validation and cleaning pipeline. It allows data analysts to define strict quality gates in a declarative YAML file, without needing to write or edit Python code. 

Recently, the pipeline was upgraded with two major capabilities: **Cross-Field (Conditional) Rules** and **Aggregate Thresholds**. 

---

## New Features

### 1. Cross-Field (Conditional) Rules
**Description:**
Real-world data rules often depend on multiple columns. For example, "If the country is US, the zip code must be 5 digits." Previously, these cross-column checks required writing custom Python functions. Now, you can define them entirely in the YAML configuration using the `conditional` rule type. This keeps the configuration accessible to non-engineers.

**How It Works:**
When the validator engine encounters a `conditional` rule, it performs a clever two-step intersection:
1. It looks at the `condition_field` and creates a hidden mask of rows where the condition is met (e.g., `warehouse_id == "WH-01"`).
2. It mocks a temporary rule and evaluates the `target_type` against the target `field` across the entire dataset.
3. It combines the two masks: a row is only flagged as a failure if it matches the condition *and* fails the target rule check.

**YAML Configuration Example:**
```yaml
- name: wh_01_minimum_price
  type: conditional
  condition_field: warehouse_id
  condition_value: "WH-01"
  field: unit_price
  target_type: range
  min: 15.0
  severity: WARNING
```
### 2. Aggregate Thresholds (Batch Rejection)

#### Description:
Data cleaning pipelines should not silently process garbage data. If a dataset is heavily corrupted (e.g., 90% of the rows are missing critical IDs), the pipeline shouldn't just filter out the 90% and pass along a tiny, mangled dataset. Aggregate thresholds act as a "circuit breaker," refusing to clean a batch if the failure rate is too high.

#### How It Works:
The validator keeps a running tally of failures:

* **Per-Rule Thresholds (max_fail_pct):** Different rules have different tolerances. You can define a maximum acceptable failure rate for a specific rule. If breached, the batch is rejected.

* **Global Profile Thresholds (global_max_fail_pct):** Acts as a final safety net. If the total percentage of bad rows in the entire dataset exceeds this limit, the batch is rejected.

* **The Safeguard:** If thresholds are breached during validation, the batch_rejected flag is flipped to True. If you attempt to call .clean() on a rejected batch, the pipeline throws a hard error and refuses to touch the data.

#### YAML Configuration Example:
```yaml
profiles:
  default:
    global_max_fail_pct: 0.20  # Rejects if >20% of ALL rows fail anything
    rules:
      - name: sku_format
        field: sku_id
        type: regex
        pattern: "^SKU-[0-9]{4}$"
        severity: ERROR
        max_fail_pct: 0.05     # Rejects if >5% of rows fail THIS specific rule
```

# Data Validation Pipeline: Drift Detection & Observability

## Feature Description

The pipeline now includes stateful **Drift Detection (Data Observability)**. Instead of evaluating data quality in a vacuum where batches merely pass or fail, the system now possesses a "memory." It tracks the failure rates of specific validation rules over time to detect gradual degradation (the "boiling frog" effect) or sudden spikes in bad data.

To prevent alert fatigue, the drift detection utilizes a **Dual-Threshold Alarm System** configured in the YAML ruleset:
*   **Relative Jump (`drift_rel_min`):** The failure rate must increase by a significant percentage compared to its historical baseline (e.g., doubling).
*   **Absolute Floor (`drift_abs_min`):** The raw failure rate must also increase by a meaningful percentage of the total dataset (e.g., a flat 5% increase) to ensure tiny blips are ignored.

These thresholds can be defined globally per profile or overridden on a per-rule basis.

## How It Works

The drift detection logic is decoupled from the core validation engine to ensure that historical trends do not forcefully reject an otherwise internally valid batch. The execution flow follows these steps:

*   **Validation:** The `DataValidator` evaluates the incoming batch against the defined rules and compiles a `ValidationResult` report containing the `total_rows` and failure counts.
*   **History Retrieval:** The `ReportComparator` accesses the hidden `.history/` directory to load past JSON validation reports.
*   **Baseline Computation:** The comparator establishes two baselines for every rule: the immediate previous run and a rolling average of the last 10 runs.
*   **Threshold Evaluation:** The current failure rate is mathematically compared against both baselines. An alert is only prepared if **both** the relative and absolute thresholds are breached. 
*   **Non-Blocking Alerts:** Any triggered drift alerts are logged directly to the console and log files as `WARNING` level messages, leaving the batch's actual pass/fail status untouched.
*   **State Preservation:** The current `ValidationResult` is securely serialized to a JSON string and saved into the `.history/` directory to act as a baseline for future runs.

# Scalable Streaming Engine (Chunked Validation)

## Feature Description
The Streaming Engine is a high-performance architectural upgrade designed to process massive datasets (e.g., 5+ million rows, multiple gigabytes) that are too large to fit into active system memory (RAM). 

Instead of attempting to load an entire CSV file into a single Pandas DataFrame—which causes systems to freeze or crash with Out-Of-Memory (OOM) errors—the Streaming Engine processes the file sequentially in bite-sized chunks. It seamlessly tracks global error thresholds, aggregates rule performance, and handles cross-row validation without losing the big picture.

## How It Works: The "Two-Pass" Architecture
Validating chunks in isolation creates a unique challenge: *How do you know if a row in Chunk 10 is an exact duplicate of a row in Chunk 1 if Chunk 1 has already been cleared from memory?* 

To solve this while keeping memory usage near zero, the `validate_stream` engine uses a highly efficient Two-Pass approach:

*   **Pass 1: The Global Scout** 
    The engine rapidly skims the file chunk-by-chunk, loading *only* the specific columns required for global rules (like `date`, `sku_id`, and `warehouse_id` for composite key checks). It uses vectorized string concatenation to build a lightweight, global "cheat sheet" (a hash set) of all duplicate keys across the entire file.
*   **Pass 2: The Deep Validation**
    The engine streams through the file a second time, processing all standard configuration rules (Regex, Ranges, Null checks) on each chunk. For global rules, instead of looking at the whole file, it instantly cross-references the current row against the "cheat sheet" generated in Pass 1.
*   **Aggregation & Thresholds**
    As each chunk finishes, its error counts, warnings, and execution timings are aggregated into a running tally. Once the final chunk completes, the global failure rate is calculated against your profile's thresholds (e.g., `global_max_fail_pct: 0.25`), and a single, unified JSON report is produced.

---

## How to Run
The chunking feature is fully integrated into the existing Command Line Interfaces and is strictly opt-in. If you do not provide a chunk size, the application will default to the standard, fully in-memory execution.

### 1. Generate Massive Test Data Safely
* The data generator has been upgraded to write data to disk in batches, preventing OOM crashes during the creation of massive test files.
```commandline
# Generate 5 million rows in safe batches of 500,000
python -m src,make_messy_data --n-base 5000000 --chunk-size 500000 --output data/large_messy_sales.csv
```

### 2. Execute Streaming Validation
* To trigger the Streaming Engine, simply add the --chunk-size flag to your standard validation command.
```commandline
# Validate the massive dataset using 500,000 row chunks
python src.validate_cli --file data/large_messy_sales.csv --config configs/sales_rules.yaml --profile bulk --output reports/stream_report.json --chunk-size 500000
```


# Auto-Generated Data Quality Contracts

## Feature Description
The **Auto-Generated Documentation** feature bridges the gap between data engineering and business stakeholders. Instead of expecting non-technical users to read complex YAML configurations or Python code, this tool automatically translates your validation rules into human-readable Markdown (`.md`) files. 

These generated files act as **Data Contracts**, providing a clear, scannable definition of what constitutes a "valid" row in your dataset, alongside the operational SLAs (Service Level Agreements) that govern your pipeline's drift and rejection limits.

## How It Works
The generator uses a "Documentation-as-Code" architecture to ensure your documentation never drifts from your actual code:

1. **Profile Flattening:** If you use environment profiles (e.g., a `strict` profile that inherits from a `default` profile), the generator automatically resolves the inheritance tree. It outputs a fully flattened view of exactly what runs in that specific environment.
2. **Two-Tiered Structure:**
    * **Section 1: Data Shape & Business Rules:** Details the fields, allowed ranges, regex patterns, and nullability for stakeholders.
    * **Section 2: SLAs & Thresholds:** Extracts pipeline-halting limits (`max_fail_pct`) and anomaly detection bounds (`drift_abs_min`, `drift_rel_min`) for DataOps teams.
3. **Smart Descriptions:** 
    * It looks for a human-readable `description` field directly in your YAML rule.
    * If missing, it auto-generates a description based on standard rule types (e.g., translating `type: range` to "Value must be between X and Y").
    * For `custom` or `transform` rules, it dynamically inspects `src/custom_rules.py` and extracts the Python docstrings to explain the logic.

## How to Run

You can generate the documentation using the standalone CLI script. By default, it will read your configuration and output the markdown files into a `docs/` directory.

### Basic Command
Run the script from your project root, pointing it to your target YAML configuration:

```commandline
python -m src.generate_docs --config configs/sales_rules.yaml
```

### Advanced Usage
You can customize the output directory using the --output-dir flag:
```commandline
python -m src.generate_docs --config configs/sales_rules.yaml --output-dir custom_docs_folder/
```

### Expected Output
When you run the command, the script will discover all profiles in your configuration and generate a separate Markdown file for each. For example:
```text
Found profiles: default, strict
Successfully generated: docs\data_contract_default.md
Successfully generated: docs\data_contract_strict.md
```

* You can then push these Markdown files to GitHub, GitLab, or integrate them into your internal wiki (like MkDocs or Confluence) for stakeholders to review!
