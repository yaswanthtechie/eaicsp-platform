import logging
from typing import List, Dict, Any, Optional

import time
import pandas as pd
import yaml
from pydantic import BaseModel, Field, model_validator, ConfigDict

import src.custom_rules as custom_rules

logger = logging.getLogger(__name__)

# The Explicit Registry: Only functions listed here can be executed.
SAFE_FUNCTION_REGISTRY = {
    "src.custom_rules.check_composite_unique": custom_rules.check_composite_unique,
    "src.custom_rules.check_unparseable_dates": custom_rules.check_unparseable_dates,
    "src.custom_rules.check_outliers": custom_rules.check_outliers,
    "src.custom_rules.check_negatives": custom_rules.check_negatives,
    "src.custom_rules.check_duplicate_rows": custom_rules.check_duplicate_rows,
    "src.custom_rules.standardize_products": custom_rules.standardize_products,
    "src.custom_rules.flag_negatives": custom_rules.flag_negatives,
    "src.custom_rules.standardize_dates": custom_rules.standardize_dates,
    "src.custom_rules.drop_duplicate_rows": custom_rules.drop_duplicate_rows,
}


def is_comparable(a, b):
    """Helper to guard against comparing strings to None or differing types."""
    if a is None or b is None:
        return False
    return type(a) is type(b) or (isinstance(a, (int, float)) and isinstance(b, (int, float)))


class SecurityError(Exception):
    pass


class ValidationResult(BaseModel):
    config_version: str = 'unknown'
    passed: bool
    batch_rejected: bool = False  # <-- NEW: Threshold breaker flag
    rejection_reasons: List[str] = Field(default_factory=list)  # <-- NEW: Details for threshold breaches
    total_rows_affected: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    sample_bad_rows: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    rule_timings: Dict[str, float] = Field(default_factory=dict)
    skipped_rules: List[Dict[str, Any]] = Field(default_factory=list)

    def __getitem__(self, item):
        """Allows dictionary-style access to the model's attributes (e.g., result['passed'])."""
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    @property
    def slowest_rule(self) -> Optional[Dict[str, Any]]:
        """Returns the single slowest rule evaluated and its duration."""
        if not self.rule_timings:
            return None
        slowest_name = max(self.rule_timings, key=lambda k: self.rule_timings[k])
        return {"rule": slowest_name, "duration_seconds": self.rule_timings[slowest_name]}


class ConfigRule(BaseModel):
    model_config = ConfigDict(extra='allow')

    name: str
    field: Optional[str] = None
    type: str
    severity: str = "INFO"
    depends_on: Optional[List[str]] = Field(default_factory=list)
    max_fail_pct: Optional[float] = None  # <-- NEW: Per-rule threshold

    @model_validator(mode='after')
    def validate_function_path(self) -> 'ConfigRule':
        if self.type in ['custom', 'transform']:
            func_path = (self.model_extra or {}).get('function')
            if not func_path:
                raise ValueError(
                    f"Rule '{self.name}' has type '{self.type}' but no 'function' path. "
                    f"Add a 'function:' key naming an entry in SAFE_FUNCTION_REGISTRY."
                )
            self._load_function(func_path)
        return self

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
        if self.type not in ['custom', 'transform', 'conditional'] and self.field is None:
            raise ValueError(f"Rule '{self.name}' requires a 'field' to be specified.")
        return self

    @staticmethod
    def _load_function(func_path: str):
        """Safely loads a function exclusively from the explicit registry."""
        if func_path not in SAFE_FUNCTION_REGISTRY:
            raise SecurityError(
                f"FATAL: Function '{func_path}' is not in the safe registry. Execution denied."
            )
        return SAFE_FUNCTION_REGISTRY[func_path]

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

        # --- NEW: Declarative Cross-Field Conditional ---
        elif self.type == "conditional":
            cond_field = self.model_extra.get('condition_field')
            cond_val = self.model_extra.get('condition_value')
            tgt_type = self.model_extra.get('target_type')

            if not cond_field or 'condition_value' not in self.model_extra or not tgt_type:
                raise ValueError(f"Rule '{self.name}' missing conditional keys.")
            if cond_field not in df.columns:
                raise ValueError(f"Condition field '{cond_field}' missing from DataFrame.")
            if self.field and self.field not in df.columns:
                raise ValueError(f"Target field '{self.field}' missing from DataFrame.")

            condition_mask = df[cond_field] == cond_val

            target_kwargs = {k: v for k, v in self.model_extra.items()
                             if k not in ['condition_field', 'condition_value', 'target_type']}

            target_rule = ConfigRule(
                name=f"{self.name}_target", type=tgt_type, field=self.field, **target_kwargs
            )

            # Apply target rule, but ONLY fail rows that ALSO match the condition
            return target_rule.evaluate(df) & condition_mask

        # Dynamic Custom Evaluation
        elif self.type == "custom":
            return self._execute_dynamic_function(df)

        # Transform rules do not evaluate failures
        elif self.type == "transform":
            return pd.Series([False] * len(df), index=df.index)

        else:
            raise ValueError(f"Unknown rule type: {self.type}")

    def apply_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies data transformation logic if the rule type is 'transform'."""
        if self.type != "transform":
            return df
        return self._execute_dynamic_function(df)


class DataValidator:
    def __init__(self, rules: List[ConfigRule], version: str = 'unknown',
                 allow_rule_failures: bool = False, global_max_fail_pct: Optional[float] = None):
        self.rules = rules
        self.version = version
        self.allow_rule_failures = allow_rule_failures
        self.global_max_fail_pct = global_max_fail_pct
        self._validate_dependencies()
        self._detect_conflicts()

    def _validate_dependencies(self):
        """
            Rejects duplicate names, unknown deps, self-deps and forward references.
            Requiring every dependency to be declared *before* the rule that uses it
            makes cycles impossible and matches what validate()/clean() assume at runtime.
        """
        names = [r.name for r in self.rules]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"Config Error: duplicate rule names: {duplicates}")

        known = set(names)
        declared = set()
        for rule in self.rules:
            for dep in (rule.depends_on or []):
                if dep == rule.name:
                    raise ValueError(f"Config Error: rule '{rule.name}' depends on itself.")
                if dep not in known:
                    raise ValueError(
                        f"Config Error: rule '{rule.name}' depends on '{dep}', "
                        f"which is not defined in this config."
                    )
                if dep not in declared:
                    raise ValueError(
                        f"Config Error: rule '{rule.name}' depends on '{dep}', which is "
                        f"declared later. Move '{dep}' above '{rule.name}' in the config."
                    )
            declared.add(rule.name)

    def _detect_conflicts(self):
        """
            Detects impossible *numeric range* combinations before execution.
            Accumulates the tightest min/max across every range rule on a field and
            rejects contradictory bounds at config-load time.

            Not covered yet: cross-type conflicts (e.g. not_null + an unsatisfiable
            regex, or unique + a custom duplicate-check on the same field).
        """
        field_ranges = {}
        for rule in self.rules:
            if rule.type == "range" and rule.field:
                min_val = rule.model_extra.get('min')
                max_val = rule.model_extra.get('max')
                exclusive_min = rule.model_extra.get('exclusive_min', False)
                exclusive_max = rule.model_extra.get('exclusive_max', False)

                if is_comparable(min_val, max_val) and min_val > max_val:
                    raise ValueError(f"Config Error: Rule '{rule.name}' is impossible.")

                if rule.field in field_ranges:
                    prev_min, prev_max, prev_excl_min, prev_excl_max = field_ranges[rule.field]

                    if is_comparable(prev_min, min_val):
                        if min_val > prev_min:
                            cum_min, cum_excl_min = min_val, exclusive_min
                        elif min_val == prev_min:
                            cum_min, cum_excl_min = min_val, prev_excl_min or exclusive_min
                        else:
                            cum_min, cum_excl_min = prev_min, prev_excl_min
                    else:
                        cum_min = min_val if min_val is not None else prev_min
                        cum_excl_min = exclusive_min if min_val is not None else prev_excl_min

                    if is_comparable(prev_max, max_val):
                        if max_val < prev_max:
                            cum_max, cum_excl_max = max_val, exclusive_max
                        elif max_val == prev_max:
                            cum_max, cum_excl_max = max_val, prev_excl_max or exclusive_max
                        else:
                            cum_max, cum_excl_max = prev_max, prev_excl_max
                    else:
                        cum_max = max_val if max_val is not None else prev_max
                        cum_excl_max = exclusive_max if max_val is not None else prev_excl_max

                    if is_comparable(cum_min, cum_max):
                        if cum_min > cum_max or (cum_min == cum_max and (cum_excl_min or cum_excl_max)):
                            raise ValueError(f"Config Error: Field '{rule.field}' has contradictory range rules.")

                    field_ranges[rule.field] = (cum_min, cum_max, cum_excl_min, cum_excl_max)
                else:
                    field_ranges[rule.field] = (min_val, max_val, exclusive_min, exclusive_max)

    @staticmethod
    def filter_incremental(df: pd.DataFrame, watermark_col: str, current_watermark: Any) -> pd.DataFrame:
        """Filters a DataFrame to only include rows strictly greater than the current watermark."""
        if current_watermark is None or df.empty:
            return df

        if watermark_col not in df.columns:
            raise ValueError(f"Incremental column '{watermark_col}' missing from DataFrame.")

        col_type = df[watermark_col].dtype
        if pd.api.types.is_numeric_dtype(col_type):
            cast_watermark = type(df[watermark_col].iloc[0])(current_watermark)
        else:
            cast_watermark = str(current_watermark)

        return df[df[watermark_col] > cast_watermark]

    @staticmethod
    def list_profiles(yaml_path: str) -> List[str]:
        """Reads a configuration file and returns a list of available profiles."""
        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)

            if data is None or 'profiles' not in data:
                return []

            return list(data['profiles'].keys())
        except (FileNotFoundError, yaml.YAMLError) as e:
            logger.error(f"Failed to parse config while listing profiles: {e}")
            return []

    @classmethod
    def from_config(cls, yaml_path: str, profile_name: Optional[str] = None,
                    allow_rule_failures: bool = False) -> 'DataValidator':
        """Instantiates the validator from a YAML configuration file."""
        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)

            if data is None:
                raise ValueError("YAML file is completely empty.")

            version = data.get('version', 'unknown')

            if 'profiles' not in data:
                if 'rules' in data:
                    logger.warning("Config uses deprecated flat 'rules' list. Please migrate to 'profiles'.")
                    rules = [ConfigRule(**r) for r in data['rules']]
                    return cls(rules, version, allow_rule_failures=allow_rule_failures)
                else:
                    raise ValueError("YAML config must contain a 'profiles' or 'rules' key.")

            profiles = data['profiles']

            if not profile_name:
                if 'default' in profiles:
                    logger.info("No --profile specified, using 'default' profile.")
                    profile_name = 'default'
                else:
                    raise ValueError("No profile specified and no 'default' profile found.")

            if profile_name not in profiles:
                raise ValueError(f"Profile '{profile_name}' not found.")

            target_profile = profiles[profile_name]
            raw_rules = {}

            # Retrieve global threshold, respecting inheritance
            global_max_fail_pct = target_profile.get('global_max_fail_pct')

            if 'inherits' in target_profile:
                parent = target_profile['inherits']
                if parent not in profiles:
                    raise ValueError(f"Parent profile '{parent}' not found.")

                if global_max_fail_pct is None:
                    global_max_fail_pct = profiles[parent].get('global_max_fail_pct')

                for r in profiles[parent].get('rules', []):
                    raw_rules[r['name']] = r

            for r in target_profile.get('rules', []):
                raw_rules[r['name']] = r

            rules = [ConfigRule(**r) for r in raw_rules.values()]
            return cls(rules, version, allow_rule_failures=allow_rule_failures, global_max_fail_pct=global_max_fail_pct)

        except (FileNotFoundError, yaml.YAMLError) as e:
            raise ValueError(f"Config parse failed: {e}")

    def _validate_schema(self, df: pd.DataFrame):
        """Ensures all fields required by the rules exist in the DataFrame before execution."""
        required_fields = {str(rule.field) for rule in self.rules if rule.field and rule.type != "conditional"}

        # Also validate conditional rule fields
        for rule in self.rules:
            if rule.type == "conditional":
                cond_f = rule.model_extra.get('condition_field')
                if cond_f:
                    required_fields.add(cond_f)
                if rule.field:
                    required_fields.add(rule.field)

        missing_fields = required_fields - set(df.columns)
        if missing_fields:
            raise ValueError(f"Pipeline failed to start. Missing required columns: {', '.join(missing_fields)}")

    def validate(self, df: pd.DataFrame) -> ValidationResult:
        """Executes the validation pipeline and generates a report."""
        if df.empty:
            return ValidationResult(
                config_version=getattr(self, 'version', 'unknown'),
                passed=False,
                total_rows_affected=0,
                errors=[{"rule": "empty_dataframe", "field": None, "count": 1}],
                rule_timings={}
            )
        self._validate_schema(df)

        df_working = df.copy()
        for rule in self.rules:
            if rule.type == "transform":
                try:
                    df_working = rule.apply_transform(df_working)
                except Exception as e:
                    logger.error(f"FATAL ERROR: Transform '{rule.name}' crashed during validation setup: {e}")

        errors = []
        warnings = []
        skipped = []
        sample_bad = {}
        affected_indices = set()

        rule_failure_masks = {}
        rule_timings = {}
        total_rows = len(df_working)

        for rule in self.rules:
            if rule.type == "transform":
                continue

            start_time = time.perf_counter()

            try:
                bad_mask = rule.evaluate(df_working)

                if rule.depends_on:
                    for dep_name in rule.depends_on:
                        if dep_name in rule_failure_masks:
                            bad_mask = bad_mask & ~rule_failure_masks[dep_name]
                        else:
                            logger.warning(
                                f"Dependency '{dep_name}' for rule '{rule.name}' not found or not executed yet.")

                rule_failure_masks[rule.name] = bad_mask
            except Exception as e:
                logger.error(f"Rule '{rule.name}' crashed and DID NOT RUN: {type(e).__name__}: {e}")
                skipped.append({
                    "rule": rule.name,
                    "field": rule.field,
                    "reason": f"{type(e).__name__}: {e}",
                })
                continue
            finally:
                duration = time.perf_counter() - start_time
                rule_timings[rule.name] = round(duration, 6)

            bad_count = int(bad_mask.sum())

            if bad_count > 0:
                bad_rows = df_working[bad_mask]
                sample = []

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

        # --- NEW: ENFORCE THRESHOLDS ---
        rejection_reasons = []

        # 1. Per-Rule Thresholds
        for rule in self.rules:
            if rule.name in rule_failure_masks and rule.max_fail_pct is not None:
                fail_pct = int(rule_failure_masks[rule.name].sum()) / total_rows
                if fail_pct > rule.max_fail_pct:
                    rejection_reasons.append(
                        f"Rule '{rule.name}' failed {fail_pct:.1%} of rows (max allowed: {rule.max_fail_pct:.1%})"
                    )

        # 2. Global Profile Threshold
        global_fail_pct = len(affected_indices) / total_rows if total_rows > 0 else 0
        if self.global_max_fail_pct is not None and global_fail_pct > self.global_max_fail_pct:
            rejection_reasons.append(
                f"Global failure rate {global_fail_pct:.1%} exceeds threshold ({self.global_max_fail_pct:.1%})"
            )

        batch_rejected = len(rejection_reasons) > 0
        passed = len(errors) == 0 and not batch_rejected and (self.allow_rule_failures or not skipped)

        return ValidationResult(
            config_version=self.version,
            passed=passed,
            batch_rejected=batch_rejected,
            rejection_reasons=rejection_reasons,
            total_rows_affected=len(affected_indices),
            errors=errors,
            warnings=warnings,
            sample_bad_rows=sample_bad,
            rule_timings=rule_timings,
            skipped_rules=skipped
        )

    def clean(self, df: pd.DataFrame, strict: bool = True, target_rules: Optional[List[str]] = None) -> pd.DataFrame:
        """
            Cleans the dataset by applying transforms and removing invalid rows.
        """
        # --- NEW: THRESHOLD SAFEGUARD ---
        # Run validate strictly to ensure we don't try to clean a hopelessly broken batch
        val_report = self.validate(df)
        if val_report.batch_rejected:
            raise RuntimeError(
                f"Refusing to clean: Batch exceeded failure thresholds. Reasons:\n" +
                "\n".join([f"- {r}" for r in val_report.rejection_reasons])
            )

        self._validate_schema(df)
        df_clean = df.copy()

        # 1. First Pass: Apply Transforms
        for rule in self.rules:
            if rule.type == "transform":
                try:
                    df_clean = rule.apply_transform(df_clean)
                except Exception as e:
                    logger.error(f"FATAL ERROR: Transform rule '{rule.name}' crashed: {e}. Skipping rule.")
                    continue

        # 2. Second Pass: Filter rows
        drop_indices = set()
        skipped = []
        rule_failure_masks = {}
        for rule in self.rules:
            if rule.type == "transform":
                continue

            try:
                mask = rule.evaluate(df_clean)

                if rule.depends_on:
                    for dep_name in rule.depends_on:
                        if dep_name in rule_failure_masks:
                            mask = mask & ~rule_failure_masks[dep_name]
                        else:
                            logger.warning(f"Dependency '{dep_name}' for rule '{rule.name}' not found/executed.")

                rule_failure_masks[rule.name] = mask

                if strict and rule.severity == "ERROR":
                    drop_indices.update(df_clean[mask].index.tolist())
                elif not strict and target_rules and rule.name in target_rules:
                    drop_indices.update(df_clean[mask].index.tolist())
            except Exception as e:
                logger.error(
                    f"Rule '{rule.name}' crashed and DID NOT RUN during cleaning: "
                    f"{type(e).__name__}: {e}")
                skipped.append(rule.name)
                continue

        if skipped and not self.allow_rule_failures:
            raise RuntimeError(
                f"Cleaning aborted: {len(skipped)} rule(s) failed to execute, so their bad "
                f"rows were NOT removed: {skipped}. Fix the rule, or construct the validator "
                f"with allow_rule_failures=True to accept partially-cleaned data."
            )

        if drop_indices:
            df_clean = df_clean.drop(index=list(drop_indices))

        return df_clean