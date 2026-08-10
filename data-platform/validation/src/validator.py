import importlib
import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, model_validator, Field

# Initialize the logger for this module
logger = logging.getLogger(__name__)


class ValidationResult(BaseModel):
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

    def _load_function(self, func_path: str):
        """Dynamically loads a Python function from a string path (e.g., 'src.module.func')."""
        try:
            module_name, func_name = func_path.rsplit('.', 1)
            module = importlib.import_module(module_name)
            return getattr(module, func_name)
        except Exception as e:
            raise RuntimeError(f"Failed to load function {func_path}: {e}")

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        """Returns a boolean mask where True indicates a row FAILED the rule."""
        if df.empty:
            return pd.Series(dtype=bool, index=df.index)

        # Standard missing value check
        if self.type == "not_null":
            if self.field not in df.columns:
                return pd.Series([True] * len(df), index=df.index)
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
            func_path = self.model_extra.get('function')
            if not func_path:
                raise ValueError(f"Custom rule '{self.name}' missing 'function' path.")

            func = self._load_function(func_path)

            # Pass all extra YAML keys as kwargs to the custom function
            kwargs = self.model_extra.copy()
            kwargs.pop('function', None)

            if self.field:
                return func(df, field=self.field, **kwargs)
            else:
                return func(df, **kwargs)

        # Transform rules do not evaluate failures; they return an empty mask
        elif self.type == "transform":
            return pd.Series([False] * len(df), index=df.index)

        else:
            raise ValueError(f"Unknown rule type: {self.type}")

    def apply_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies data transformation logic if the rule type is 'transform'."""
        if self.type != "transform":
            return df

        func_path = self.model_extra.get('function')
        if not func_path:
            raise ValueError(f"Transform rule '{self.name}' missing 'function' path.")

        func = self._load_function(func_path)

        # Pass all extra YAML keys as kwargs to the transform function
        kwargs = self.model_extra.copy()
        kwargs.pop('function', None)

        if self.field:
            return func(df, field=self.field, **kwargs)
        else:
            return func(df, **kwargs)


class DataValidator:
    def __init__(self, rules: List[ConfigRule]):
        self.rules = rules

    @classmethod
    def from_config(cls, yaml_path: str) -> 'DataValidator':
        """Instantiates the validator directly from a YAML configuration file."""
        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)

            # Edge Case Fix: Prevent NoneType exceptions on empty files
            if data is None:
                raise ValueError("YAML file is completely empty.")

            rules_data = data.get('rules', [])
            rules = [ConfigRule(**r) for r in rules_data]
            return cls(rules)

        except (FileNotFoundError, yaml.YAMLError) as e:
            raise ValueError(f"Config parse failed: {e}")
        # Note: Pydantic ValidationErrors bubble up natively without being caught here.

    def validate(self, df: pd.DataFrame) -> ValidationResult:
        """Executes the validation pipeline and generates a report."""
        errors = []
        warnings = []
        sample_bad = {}
        affected_indices = set()

        for rule in self.rules:
            # Skip evaluation for transform rules
            if rule.type == "transform":
                continue

            # --- Fail-Safe Implementation ---
            try:
                bad_mask = rule.evaluate(df)
            except Exception as e:
                logger.error(f"FATAL ERROR: Rule '{rule.name}' crashed during validation: {e}. Skipping rule.")
                continue

            bad_count = int(bad_mask.sum())

            if bad_count > 0:
                bad_rows = df[bad_mask]
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
                # Note: INFO severity records issues but does not count them as "affected rows"

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
        If strict=True, all rows with ERRORs are dropped.
        If strict=False, only rows failing 'target_rules' are dropped.
        """
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
        for rule in self.rules:
            if rule.type == "transform":
                continue

            # --- Fail-Safe Implementation for Cleaning ---
            try:
                if strict and rule.severity == "ERROR":
                    mask = rule.evaluate(df_clean)
                    drop_indices.update(df_clean[mask].index.tolist())
                elif not strict and target_rules and rule.name in target_rules:
                    mask = rule.evaluate(df_clean)
                    drop_indices.update(df_clean[mask].index.tolist())
            except Exception as e:
                logger.error(f"FATAL ERROR: Rule '{rule.name}' crashed during cleaning: {e}. Skipping rule.")
                continue

        if drop_indices:
            df_clean = df_clean.drop(index=list(drop_indices))

        return df_clean