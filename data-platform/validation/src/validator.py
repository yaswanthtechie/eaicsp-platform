import importlib
import logging
from typing import List, Dict, Any, Optional

import pandas as pd
import yaml
from pydantic import BaseModel, Field, model_validator, ConfigDict

logger = logging.getLogger(__name__)


class ValidationResult(BaseModel):
    config_version: str = 'unknown' # <-- Added version tracking
    passed: bool
    total_rows_affected: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    sample_bad_rows: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)

    def __getitem__(self, item):
        """Allows dictionary-style access to the model's attributes (e.g., result['passed'])."""
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)


class ConfigRule(BaseModel):
    # Allow extra kwargs from the YAML (like 'min', 'max', 'pattern', 'subset', etc.)
    model_config = ConfigDict(extra='allow')

    name: str
    field: Optional[str] = None
    type: str
    severity: str = "INFO"
    depends_on: Optional[List[str]] = Field(default_factory=list)  # <-- Added dependency tracking

    @model_validator(mode='before')
    @classmethod
    def uppercase_severity(cls, values: Any) -> Any:
        """Ensures severity is always uppercase (ERROR, WARNING, INFO)."""
        if isinstance(values, dict) and isinstance(values.get('severity'), str):
            values['severity'] = values['severity'].upper()
        return values

    @model_validator(mode='after')
    def check_field_requirement(self) -> 'ConfigRule':
        """Ensures standard rules have a target field specified."""
        if self.type not in ['custom', 'transform'] and self.field is None:
            raise ValueError(f"Rule '{self.name}' requires a 'field' to be specified.")
        return self

    @staticmethod
    def _load_function(func_path: str):
        """Dynamically loads a Python function from a string path (e.g., 'src.module.func')."""
        try:
            module_name, func_name = func_path.rsplit('.', 1)
            module = importlib.import_module(module_name)
            return getattr(module, func_name)
        except Exception as e:
            raise RuntimeError(f"Failed to load function {func_path}: {e}")

    def _execute_dynamic_function(self, df: pd.DataFrame) -> Any:
        """Helper to deduplicate dynamic function execution for custom/transform rules."""
        func_path = self.model_extra.get('function')
        if not func_path:
            raise ValueError(f"Rule '{self.name}' missing 'function' path.")

        func = self._load_function(func_path)

        kwargs = (self.model_extra or {}).copy()
        kwargs.pop('function', None)

        if self.field:
            return func(df, field=self.field, **kwargs)
        return func(df, **kwargs)

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        """Returns a boolean mask where True indicates a row FAILED the rule."""
        if df.empty:
            return pd.Series(dtype=bool, index=df.index)

        # Fail-fast if the target field is entirely missing from the dataframe
        if self.field and self.field not in df.columns:
            raise ValueError(f"Target field '{self.field}' missing from DataFrame.")

        # Standard missing value check
        if self.type == "not_null":
            return df[self.field].isna()

        # Standard range check
        elif self.type == "range":
            min_val = self.model_extra.get('min', float('-inf'))
            max_val = self.model_extra.get('max', float('inf'))
            s = df[self.field]
            # Flag if OUTSIDE the range (only check non-nulls)
            return ~((s >= min_val) & (s <= max_val)) & s.notna()

        # Standard Regex check
        elif self.type == "regex":
            pattern = self.model_extra.get('pattern')
            if not pattern:
                raise ValueError(f"Regex missing 'pattern' in rule '{self.name}'")
            s = df[self.field]
            return ~s.astype(str).str.match(pattern) & s.notna()

        # Standard Uniqueness check
        elif self.type == "unique":
            s = df[self.field]
            return s.duplicated(keep=False) & s.notna()

        # Dynamic Custom Evaluation (Returns boolean mask)
        elif self.type == "custom":
            # Fix: Replaced duplicated code with helper
            return self._execute_dynamic_function(df)

        # Transform rules do not evaluate failures; they return an empty mask
        elif self.type == "transform":
            return pd.Series([False] * len(df), index=df.index)

        else:
            raise ValueError(f"Unknown rule type: {self.type}")

    def apply_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies data transformation logic if the rule type is 'transform'."""
        if self.type != "transform":
            return df

        # Fix: Replaced duplicated code with helper
        return self._execute_dynamic_function(df)


class DataValidator:
    def __init__(self, rules: List[ConfigRule]):
        self.rules = rules

    @classmethod
    def from_config(cls, yaml_path: str) -> 'DataValidator':
        """Instantiates the validator directly from a YAML configuration file."""
        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)

            if data is None:
                raise ValueError("YAML file is completely empty.")

            rules_data = data.get('rules', [])
            rules = [ConfigRule(**r) for r in rules_data]
            return cls(rules)

        except (FileNotFoundError, yaml.YAMLError) as e:
            raise ValueError(f"Config parse failed: {e}")

    def _validate_schema(self, df: pd.DataFrame):
        """Ensures all fields required by the rules exist in the DataFrame before execution."""
        required_fields = {str(rule.field) for rule in self.rules if rule.field}
        missing_fields = required_fields - set(df.columns)
        if missing_fields:
            raise ValueError(f"Pipeline failed to start. Missing required columns: {', '.join(missing_fields)}")

    def validate(self, df: pd.DataFrame) -> ValidationResult:
        """Executes the validation pipeline and generates a report."""
        self._validate_schema(df)

        # NEW: Apply transforms to a working copy so validation rules evaluate clean data
        df_working = df.copy()
        for rule in self.rules:
            if rule.type == "transform":
                try:
                    df_working = rule.apply_transform(df_working)
                except Exception as e:
                    logger.error(f"FATAL ERROR: Transform '{rule.name}' crashed during validation setup: {e}")

        errors = []
        warnings = []
        sample_bad = {}
        affected_indices = set()

        # Dictionary to track boolean failure masks by rule name
        rule_failure_masks = {}

        for rule in self.rules:
            # Skip evaluation for transform rules
            if rule.type == "transform":
                continue

            # --- Fail-Safe Implementation ---
            try:
                # IMPORTANT: Evaluate against df_working, not the raw df
                # 1. Evaluate the rule independently
                bad_mask = rule.evaluate(df_working)
                # bad_mask = rule.evaluate(df)

                # 2. Suppress failures if a dependency already failed this row
                if rule.depends_on:
                    for dep_name in rule.depends_on:
                        if dep_name in rule_failure_masks:
                            # Flips the dependency's True (failed) to False (ignore)
                            bad_mask = bad_mask & ~rule_failure_masks[dep_name]
                        else:
                            logger.warning(
                                f"Dependency '{dep_name}' for rule '{rule.name}' not found or not executed yet.")

                # 3. Store the final evaluated mask for future dependencies
                rule_failure_masks[rule.name] = bad_mask
            except Exception as e:
                logger.error(f"FATAL ERROR: Rule '{rule.name}' crashed during validation: {e}. Skipping rule.")
                continue

            bad_count = int(bad_mask.sum())

            if bad_count > 0:
                bad_rows = df_working[bad_mask]
                sample = []

                # Gather samples for debugging
                for idx, row in bad_rows.head(5).iterrows():
                    failed_val = row[rule.field] if rule.field and rule.field in df.columns else None
                    sample.append({
                        "row_index": idx,
                        "failed_value": failed_val,
                        "rule_name": rule.name
                    })
                sample_bad[rule.name] = sample

                report_item = {
                    "rule": rule.name,
                    "field": rule.field,
                    "count": bad_count
                }

                if rule.severity == "ERROR":
                    errors.append(report_item)
                    affected_indices.update(bad_rows.index.tolist())
                elif rule.severity == "WARNING":
                    warnings.append(report_item)
                    affected_indices.update(bad_rows.index.tolist())

        passed = len(errors) == 0
        return ValidationResult(
            passed=passed,
            total_rows_affected=len(affected_indices),
            errors=errors,
            warnings=warnings,
            sample_bad_rows=sample_bad
        )

    def clean(self, df: pd.DataFrame, strict: bool = True, target_rules: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Cleans the dataset by applying transforms and removing invalid rows.
        """
        self._validate_schema(df)
        df_clean = df.copy()

        # 1. First Pass: Apply Transforms
        for rule in self.rules:
            if rule.type == "transform":
                # --- Fail-Safe Implementation for Transforms ---
                try:
                    df_clean = rule.apply_transform(df_clean)
                except Exception as e:
                    logger.error(f"FATAL ERROR: Transform rule '{rule.name}' crashed: {e}. Skipping rule.")
                    continue

        # 2. Second Pass: Filter rows
        drop_indices = set()
        # NEW: Track failures to support rule dependencies during cleaning
        rule_failure_masks = {}
        for rule in self.rules:
            if rule.type == "transform":
                continue

            # --- Fail-Safe Implementation for Cleaning ---
            try:
                # 1. Evaluate the rule independently (Must evaluate all to maintain dependency chain)
                mask = rule.evaluate(df_clean)

                # 2. Suppress failures if a dependency already failed this row
                if rule.depends_on:
                    for dep_name in rule.depends_on:
                        if dep_name in rule_failure_masks:
                            mask = mask & ~rule_failure_masks[dep_name]
                        else:
                            logger.warning(f"Dependency '{dep_name}' for rule '{rule.name}' not found/executed.")

                # 3. Store the final evaluated mask for future dependencies
                rule_failure_masks[rule.name] = mask

                # 4. Filter the rows based on strictness settings using the correctly suppressed mask
                if strict and rule.severity == "ERROR":
                    drop_indices.update(df_clean[mask].index.tolist())
                elif not strict and target_rules and rule.name in target_rules:
                    drop_indices.update(df_clean[mask].index.tolist())
            except Exception as e:
                logger.error(f"FATAL ERROR: Rule '{rule.name}' crashed during cleaning: {e}. Skipping rule.")
                continue

        if drop_indices:
            df_clean = df_clean.drop(index=list(drop_indices))

        return df_clean