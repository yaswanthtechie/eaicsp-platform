import importlib
import yaml
import logging
import pandas as pd
from typing import Any, Dict, List, Optional, Literal, Callable, Type, ClassVar
from pydantic import BaseModel, ConfigDict, field_validator, model_validator, ValidationError, Field

# Initialize the logger for this module
logger = logging.getLogger(__name__)


class ValidationResult(BaseModel):
    """Wraps validation output to support both attribute (.passed) and dict (['passed']) access."""
    model_config = ConfigDict(extra='allow')

    passed: bool
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    info: List[Dict[str, Any]] = Field(default_factory=list)
    total_rows_affected: int = 0
    sample_bad_rows: Dict[str, Any] = Field(default_factory=dict)

    def __getitem__(self, item):
        # Enables backward compatibility for result["passed"]
        return getattr(self, item)

class ConfigRule(BaseModel):
    model_config = ConfigDict(extra='allow')

    FIELD_BOUND_RULES: ClassVar[set] = {'not_null', 'range', 'regex', 'unique'}
    # Define standard keys so we know which ones to exclude when extracting **kwargs
    STANDARD_KEYS: ClassVar[set] = {'name', 'field', 'type', 'severity', 'function', 'min', 'max', 'pattern'}

    name: str
    field: Optional[str] = None
    type: Literal['not_null', 'range', 'regex', 'unique', 'custom', 'transform']
    severity: Literal['ERROR', 'WARNING', 'INFO'] = 'WARNING'

    @field_validator('severity', mode='before')
    @classmethod
    def uppercase_severity(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.upper()
        return v

    @model_validator(mode='after')
    def check_field_requirement(self) -> 'ConfigRule':
        if self.type in self.FIELD_BOUND_RULES and not self.field:
            raise ValueError(f"Rule '{self.name}' of type '{self.type}' requires a 'field' to be specified.")
        return self

    @property
    def config(self) -> Dict[str, Any]:
        return self.model_dump()

    def _get_custom_kwargs(self) -> Dict[str, Any]:
        """Extracts any non-standard keys from the YAML config to pass as kwargs."""
        return {k: v for k, v in self.config.items() if k not in self.STANDARD_KEYS}

    def _load_function(self) -> Callable[..., Any]:
        func_path: Optional[str] = self.config.get('function')
        if not func_path:
            raise ValueError(f"Rule '{self.name}' missing 'function' path.")

        try:
            mod_name, func_name = func_path.rsplit('.', 1)
            mod = importlib.import_module(mod_name)
            return getattr(mod, func_name)
        except (ModuleNotFoundError, AttributeError, ValueError) as e:
            raise RuntimeError(f"Failed to load function '{func_path}': {e}")

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        if self.field and self.field not in df.columns:
            # Fail loudly instead of silently flagging all rows as invalid
            raise ValueError(
                f"CRITICAL: Rule '{self.name}' expects field '{self.field}', but it is missing from the dataset.")
            # return pd.Series(True, index=df.index, dtype=bool)

        s: Optional[pd.Series] = df[self.field] if self.field else None

        if self.type == 'not_null' and s is not None:
            return s.isna()

        elif self.type == 'range' and s is not None:
            min_val = float(self.config.get('min', float('-inf')))
            max_val = float(self.config.get('max', float('inf')))
            return (s < min_val) | (s > max_val)

        elif self.type == 'regex' and s is not None:
            pattern: Any | None = self.config.get('pattern')
            if not pattern:
                raise ValueError(f"Regex missing 'pattern'.")

            non_nulls = s.dropna()
            bad_strings = ~non_nulls.astype(str).str.match(pattern)
            return bad_strings.reindex(s.index, fill_value=False).astype(bool)

        elif self.type == 'unique' and s is not None:
            return s.duplicated(keep=False) & s.notna()

        elif self.type == 'custom':
            func = self._load_function()
            kwargs = self._get_custom_kwargs()
            # Inject 'field' as a kwarg if it exists
            if hasattr(self, 'field') and self.field is not None:
                kwargs['field'] = self.field
            return pd.Series(func(df, **kwargs), dtype=bool)

        elif self.type == 'transform':
            return pd.Series(False, index=df.index, dtype=bool)

        else:
            raise ValueError(f"Unknown rule type: {self.type}")

    def apply_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.type == 'transform':
            func = self._load_function()
            kwargs = self._get_custom_kwargs()
            # Pass extracted kwargs dynamically
            # Manually inject the 'field' back into kwargs so the transform function receives it!
            if hasattr(self, 'field') and self.field is not None:
                kwargs['field'] = self.field
            return func(df, **kwargs)
        return df


class DataValidator:
    def __init__(self, rules: List[ConfigRule]):
        self.rules = rules

    @classmethod
    def from_config(cls: Type['DataValidator'], config_path: str) -> 'DataValidator':
        try:
            with open(config_path, 'r') as f:
                data: Dict[str, Any] = yaml.safe_load(f)
            # Handle empty files which cause safe_load to return None
            if data is None:
                raise ValueError("YAML file is completely empty.")
        except Exception as e:
            raise ValueError(f"Config parse failed: {e}")

        rules = [ConfigRule(**r) for r in data.get('rules', [])]

        return cls(rules)

    def validate(self, df: pd.DataFrame) -> ValidationResult:
        report: Dict[str, Any] = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "info": [],
            "total_rows_affected": 0,
            "sample_bad_rows": {}
        }

        # Handle Empty Batch
        if df.empty:
            report["warnings"].append({
                "rule": "empty_batch",
                "field": None,
                "count": 0,
                "message": "Received an empty DataFrame."
            })
            return ValidationResult(**report)

        global_bad_mask: pd.Series = pd.Series(False, index=df.index, dtype=bool)

        for rule in self.rules:
            bad_mask: pd.Series = rule.evaluate(df)
            bad_count: int = int(bad_mask.sum())

            if bad_count > 0:
                # Do not count INFO flags towards global severities or row drops
                if rule.severity in ['ERROR', 'WARNING']:
                    global_bad_mask |= bad_mask

                issue: Dict[str, Any] = {
                    "rule": rule.name,
                    "field": rule.field,
                    "count": bad_count
                }

                if rule.severity == 'ERROR':
                    report['passed'] = False
                    report['errors'].append(issue)
                elif rule.severity == 'WARNING':
                    report['warnings'].append(issue)
                elif rule.severity == 'INFO':
                    report['info'].append(issue)

                sample_indices = df[bad_mask].head(5).index
                field_exists: bool = bool(rule.field and rule.field in df.columns)

                report['sample_bad_rows'][rule.name] = [
                    {
                        "row_index": idx,
                        "failed_value": df.at[idx, rule.field] if field_exists else None,
                        "rule_name": rule.name
                    } for idx in sample_indices
                ]

        report['total_rows_affected'] = int(global_bad_mask.sum())
        return ValidationResult(**report)

    def clean(self, df: pd.DataFrame, strict: bool = True, target_rules: Optional[List[str]] = None) -> pd.DataFrame:
        drop_mask: pd.Series = pd.Series(False, index=df.index, dtype=bool)
        target_rules_set: set = set(target_rules or [])

        for rule in self.rules:
            if rule.type == 'transform':
                continue
            if strict and rule.severity != 'ERROR':
                continue
            if not strict and rule.name not in target_rules_set:
                continue

            bad_mask: pd.Series = rule.evaluate(df)
            drop_mask |= bad_mask

        clean_df: pd.DataFrame = df[~drop_mask].copy()

        for rule in self.rules:
            if rule.type == 'transform':
                logger.info(f"Applying transformation rule: {rule.name}")
                clean_df = rule.apply_transform(clean_df)

        return clean_df