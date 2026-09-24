import collections
import copy
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

import pandas as pd
import yaml
from pydantic import BaseModel, Field, model_validator, ConfigDict

logger = logging.getLogger(__name__)


def resolve_env_path(base_path: Union[str, Path], env: Optional[str] = None) -> Path:
    """
    Injects the environment subdirectory into the path if an environment is specified.
    E.g., configs/sales_rules.yaml + env='prod' -> configs/prod/sales_rules.yaml
    """
    path = Path(base_path)
    if not env or env.lower() in ('default', 'local', 'none', ''):
        env = 'dev'

    # Strict validation against allowed environments
    allowed_envs = {'dev', 'staging', 'prod'}
    if env.lower() not in allowed_envs:
        raise ValueError(f"Invalid environment '{env}'. Must be one of: {allowed_envs}")

    # Avoid double-injecting if the environment is already explicitly in the path
    if env in path.parts:
        return path

    return path.parent / env / path.name


def is_comparable(a, b):
    """Helper to guard against comparing strings to None or differing types."""
    if a is None or b is None:
        return False
    return type(a) is type(b) or (isinstance(a, (int, float)) and isinstance(b, (int, float)))


class SecurityError(Exception):
    pass


class RowLevelResult(BaseModel):
    passed: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    info: List[str] = Field(default_factory=list)
    remediations: List[Dict[str, Any]] = Field(default_factory=list)
    skipped_stateful: List[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    config_version: str = 'unknown'
    passed: bool
    batch_rejected: bool = False
    rejection_reasons: List[str] = Field(default_factory=list)
    sla_breached: bool = False
    sla_violations: List[str] = Field(default_factory=list)
    total_rows_affected: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    sample_bad_rows: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    remediations: List[Dict[str, Any]] = Field(default_factory=list)
    sample_remediations: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    rule_timings: Dict[str, float] = Field(default_factory=dict)
    skipped_rules: List[Dict[str, Any]] = Field(default_factory=list)
    total_rows: int = 0
    evaluated_rules: List[str] = []

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
    description: Optional[str] = None
    field: Optional[str] = None
    type: str
    severity: str = "INFO"
    depends_on: Optional[List[str]] = Field(default_factory=list)
    max_fail_pct: Optional[float] = None
    drift_abs_min: Optional[float] = None
    drift_rel_min: Optional[float] = None
    requires_full_dataset: bool = False

    @model_validator(mode='after')
    def validate_function_path(self) -> 'ConfigRule':
        if self.type in ['custom', 'transform']:
            extra = self.model_extra or {}
            func_path = extra.get('function')
            if not func_path:
                raise ValueError(
                    f"Rule '{self.name}' has type '{self.type}' but no 'function' path. "
                    f"Add a 'function:' key naming an entry in the dynamic registry."
                )
            self._load_function(str(func_path))
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
        """Safely loads a function exclusively from the dynamic registry."""
        from src.registry import RULE_REGISTRY
        clean_name = func_path.split('.')[-1]

        if clean_name not in RULE_REGISTRY:
            raise SecurityError(
                f"FATAL: Function '{clean_name}' is not in the active registry. "
                f"Execution denied. Ensure the file is in the configured rules directory."
            )
        return RULE_REGISTRY[clean_name]

    def _execute_dynamic_function(self, df: pd.DataFrame) -> Any:
        """Helper to deduplicate dynamic function execution for custom/transform rules."""
        extra = self.model_extra or {}
        func_path = extra.get('function')

        if not func_path:
            raise ValueError(f"Rule '{self.name}' missing 'function' path.")

        func = self._load_function(str(func_path))
        kwargs = extra.copy()
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

        extra = self.model_extra or {}

        if self.type == "not_null":
            return df[self.field].isna()

        elif self.type == "range":
            min_val = extra.get('min', float('-inf'))
            max_val = extra.get('max', float('inf'))
            s = df[self.field]
            return ~((s >= min_val) & (s <= max_val)) & s.notna()

        elif self.type == "regex":
            pattern = extra.get('pattern')
            if not pattern:
                raise ValueError(f"Regex missing 'pattern' in rule '{self.name}'")
            s = df[self.field]
            return ~s.astype(str).str.match(str(pattern)) & s.notna()

        elif self.type == "unique":
            s = df[self.field]
            return s.duplicated(keep=False) & s.notna()

        elif self.type == "conditional":
            cond_field = extra.get('condition_field')
            cond_val = extra.get('condition_value')
            tgt_type = extra.get('target_type')

            if not cond_field or 'condition_value' not in extra or not tgt_type:
                raise ValueError(f"Rule '{self.name}' missing conditional keys.")
            if str(cond_field) not in df.columns:
                raise ValueError(f"Condition field '{cond_field}' missing from DataFrame.")
            if self.field and self.field not in df.columns:
                raise ValueError(f"Target field '{self.field}' missing from DataFrame.")

            condition_mask = df[str(cond_field)] == cond_val

            target_kwargs = {k: v for k, v in extra.items()
                             if k not in ['condition_field', 'condition_value', 'target_type']}

            target_rule = ConfigRule(
                name=f"{self.name}_target", type=str(tgt_type), field=self.field, **target_kwargs
            )
            return target_rule.evaluate(df) & condition_mask

        elif self.type == "custom":
            return self._execute_dynamic_function(df)

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
                 allow_rule_failures: bool = False, global_max_fail_pct: Optional[float] = None,
                 global_warning_fail_pct: Optional[float] = None, global_max_duration_seconds: Optional[float] = None,
                 global_drift_abs_min: float = 0.01, global_drift_rel_min: float = 0.50):
        self.rules = rules
        self.version = version
        self.allow_rule_failures = allow_rule_failures
        self.global_max_fail_pct = global_max_fail_pct
        self.global_warning_fail_pct = global_warning_fail_pct
        self.global_max_duration_seconds = global_max_duration_seconds
        self._validate_dependencies()
        self._detect_conflicts()
        self.global_drift_abs_min = global_drift_abs_min
        self.global_drift_rel_min = global_drift_rel_min

    def _validate_dependencies(self):
        """Rejects duplicate names, unknown deps, self-deps and forward references."""
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
        """Detects impossible *numeric range* combinations before execution."""
        field_ranges = {}
        for rule in self.rules:
            if rule.type == "range" and rule.field:
                extra = rule.model_extra or {}

                min_val = extra.get('min')
                max_val = extra.get('max')
                exclusive_min = extra.get('exclusive_min', False)
                exclusive_max = extra.get('exclusive_max', False)

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
                    allow_rule_failures: bool = False, rules_dir: Optional[str] = None) -> 'DataValidator':
        """Instantiates the validator from a YAML configuration file and loads custom rules."""
        from src.registry import discover_rules, DEFAULT_RULES_DIR
        discover_rules(rules_dir or DEFAULT_RULES_DIR)

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

            def resolve_profile(prof_name):
                if prof_name not in profiles:
                    raise ValueError(f"Profile '{prof_name}' not found.")
                prof = profiles[prof_name]

                merged_rules = {}
                merged_max_fail = prof.get('global_max_fail_pct')
                merged_warn_fail = prof.get('global_warning_fail_pct')
                merged_max_dur = prof.get('global_max_duration_seconds')
                merged_abs_min = prof.get('global_drift_abs_min')
                merged_rel_min = prof.get('global_drift_rel_min')

                if 'inherits' in prof:
                    parent_rules, p_max, p_warn, p_dur, p_abs, p_rel = resolve_profile(prof['inherits'])
                    merged_rules.update(parent_rules)
                    if merged_max_fail is None: merged_max_fail = p_max
                    if merged_warn_fail is None: merged_warn_fail = p_warn
                    if merged_max_dur is None: merged_max_dur = p_dur
                    if merged_abs_min is None: merged_abs_min = p_abs
                    if merged_rel_min is None: merged_rel_min = p_rel

                for r in prof.get('rules', []):
                    merged_rules[r['name']] = r

                return merged_rules, merged_max_fail, merged_warn_fail, merged_max_dur, merged_abs_min, merged_rel_min

            raw_rules, global_max_fail_pct, global_warning_fail_pct, global_max_duration_seconds, global_drift_abs_min, global_drift_rel_min = resolve_profile(
                profile_name)

            abs_min = 0.01 if global_drift_abs_min is None else global_drift_abs_min
            rel_min = 0.50 if global_drift_rel_min is None else global_drift_rel_min

            rules = [ConfigRule(**r) for r in raw_rules.values()]
            return cls(rules, version, allow_rule_failures=allow_rule_failures,
                       global_max_fail_pct=global_max_fail_pct, global_warning_fail_pct=global_warning_fail_pct,
                       global_max_duration_seconds=global_max_duration_seconds,
                       global_drift_abs_min=abs_min, global_drift_rel_min=rel_min)

        except (FileNotFoundError, yaml.YAMLError) as e:
            raise ValueError(f"Config parse failed: {e}")

    def _validate_schema(self, df: pd.DataFrame):
        """Ensures all fields required by the rules exist in the DataFrame before execution."""
        required_fields = {str(rule.field) for rule in self.rules if rule.field and rule.type != "conditional"}

        for rule in self.rules:
            if rule.type == "conditional":
                extra = rule.model_extra or {}
                cond_f = extra.get('condition_field')
                if cond_f:
                    required_fields.add(str(cond_f))
                if rule.field:
                    required_fields.add(rule.field)

        missing_fields = required_fields - set(df.columns)
        if missing_fields:
            raise ValueError(f"Pipeline failed to start. Missing required columns: {', '.join(missing_fields)}")

    def validate_stream(
            self,
            filepath: str,
            chunksize: int,
            watermark_col: Optional[str] = None,
            current_watermark: Any = None
    ) -> ValidationResult:
        pipeline_start_time = time.perf_counter()

        aggregate_rules = [r.name for r in self.rules if getattr(r, 'requires_full_dataset', False)]
        if aggregate_rules:
            raise RuntimeError(
                f"Streaming validation aborted: Active profile contains aggregate rules that "
                f"require the full dataset in memory. Conflicting rules: {aggregate_rules}. "
                f"Either run in-memory or use a profile without these rules."
            )

        stream_rules = copy.deepcopy(self.rules)

        for i, rule in enumerate(stream_rules):
            if rule.name == 'composite_pk_unique':
                rule_dict = rule.model_dump()
                rule_dict['function'] = "check_composite_unique_stream"
                stream_rules[i] = ConfigRule(**rule_dict)

        original_rules = self.rules
        self.rules = stream_rules
        try:
            return self._validate_stream_impl(
                filepath, chunksize, watermark_col, current_watermark, pipeline_start_time
            )
        finally:
            self.rules = original_rules

    def _composite_keys(self, chunk: pd.DataFrame, composite_subset: List[str]) -> Optional[pd.Series]:
        for r in self.rules:
            if r.type == "transform":
                try:
                    chunk = r.apply_transform(chunk)
                except Exception as e:
                    logger.warning("Transform '%s' failed on a chunk (%s). "
                                   "Duplicate keys for this chunk use untransformed values.", r.name, e)

        if not all(c in chunk.columns for c in composite_subset):
            return None
        return pd.util.hash_pandas_object(chunk[composite_subset].astype("string"), index=False)

    def _validate_stream_impl(
            self,
            filepath: str,
            chunksize: int,
            watermark_col: Optional[str] = None,
            current_watermark: Any = None,
            pipeline_start_time: Optional[float] = None
    ) -> ValidationResult:
        """Executes the validation pipeline sequentially over chunks."""
        logger.info(f"Starting STREAMING validation pass (chunksize={chunksize:,})...")

        # --- PASS 1: Build Global State ---
        logger.info("Pass 1: Identifying global state (duplicates, quantiles)...")

        global_cols = set()
        has_composite = False
        composite_subset = []

        for rule in self.rules:
            if rule.name == 'composite_pk_unique':
                has_composite = True
                extra = rule.model_extra or {}
                composite_subset = extra.get('subset', [])
                global_cols.update(composite_subset)

        seen_keys = set()
        global_duplicates = set()

        use_cols = set(global_cols)
        if watermark_col:
            use_cols.add(watermark_col)

        if has_composite and global_cols:
            for chunk in pd.read_csv(filepath, chunksize=chunksize, usecols=lambda c: c in use_cols):
                if watermark_col and current_watermark is not None:
                    chunk = self.filter_incremental(chunk, watermark_col, current_watermark)
                if chunk.empty:
                    continue

                keys = self._composite_keys(chunk, composite_subset)
                if keys is not None:
                    unique_chunk_keys = set(keys)
                    chunk_dupes = set(keys[keys.duplicated()])

                    # Store only items duplicated within this chunk, or intersecting with previous chunks
                    global_duplicates.update(seen_keys.intersection(unique_chunk_keys))
                    global_duplicates.update(chunk_dupes)

                    seen_keys.update(unique_chunk_keys)
        logger.info(f"Pass 1 Complete. Found {len(global_duplicates):,} cross-chunk composite duplicates.")

        # --- PASS 2: Chunk Validation ---
        logger.info("Pass 2: Validating chunks...")

        agg_total_rows = 0
        agg_total_affected = 0
        agg_errors = collections.defaultdict(int)
        agg_warnings = collections.defaultdict(int)
        agg_sample_bad = collections.defaultdict(list)
        agg_rule_timings = collections.defaultdict(float)
        agg_skipped = []
        agg_remediations = collections.defaultdict(int)
        agg_sample_remed = collections.defaultdict(list)

        chunk_idx = 0

        for chunk in pd.read_csv(filepath, chunksize=chunksize):
            if watermark_col and current_watermark is not None:
                chunk = self.filter_incremental(chunk, watermark_col, current_watermark)
            if chunk.empty:
                continue
            chunk_idx += 1
            logger.info(f"  -> Processing Chunk {chunk_idx}...")

            # Apply global state dynamically
            if has_composite:
                # Build keys from the same columns Pass 1 read, so transforms see identical input
                key_cols = [c for c in chunk.columns if c in use_cols]
                keys = self._composite_keys(chunk[key_cols], composite_subset)
                if keys is not None:
                    chunk['_global_dup_mask'] = keys.isin(global_duplicates).to_numpy()
                else:
                    chunk['_global_dup_mask'] = False

            chunk_report = self.validate(chunk, skip_sla=True)

            agg_total_rows += chunk_report.total_rows
            for k, v in chunk_report.rule_timings.items():
                agg_rule_timings[k] += v
            for error in chunk_report.errors:
                agg_errors[(error['rule'], error['field'])] += error['count']
            for warning in chunk_report.warnings:
                agg_warnings[(warning['rule'], warning['field'])] += warning['count']
            for rule_name, samples in chunk_report.sample_bad_rows.items():
                if len(agg_sample_bad[rule_name]) < 5:
                    agg_sample_bad[rule_name].extend(samples[:5 - len(agg_sample_bad[rule_name])])
            for rem in chunk_report.remediations:
                agg_remediations[(rem['rule'], rem['field'])] += rem['rows_modified']
            for rule_name, samples in chunk_report.sample_remediations.items():
                if len(agg_sample_remed[rule_name]) < 5:
                    agg_sample_remed[rule_name].extend(samples[:5 - len(agg_sample_remed[rule_name])])
            agg_skipped.extend(chunk_report.skipped_rules)
            agg_total_affected += chunk_report.total_rows_affected

        final_errors = [{"rule": k[0], "field": k[1], "count": v} for k, v in agg_errors.items()]
        final_warnings = [{"rule": k[0], "field": k[1], "count": v} for k, v in agg_warnings.items()]
        final_remediations = [{"rule": k[0], "field": k[1], "rows_modified": v} for k, v in agg_remediations.items()]

        rejection_reasons = []
        global_fail_pct = agg_total_affected / agg_total_rows if agg_total_rows > 0 else 0
        if self.global_max_fail_pct is not None and global_fail_pct > self.global_max_fail_pct:
            rejection_reasons.append(
                f"Global failure rate {global_fail_pct:.1%} exceeds threshold ({self.global_max_fail_pct:.1%})")

        per_rule_counts = collections.defaultdict(int)
        for (rule_name, _field), count in agg_errors.items():
            per_rule_counts[rule_name] += count
        for (rule_name, _field), count in agg_warnings.items():
            per_rule_counts[rule_name] += count

        for rule in self.rules:
            if rule.max_fail_pct is None or rule.severity != "ERROR":
                continue
            failed = per_rule_counts.get(rule.name, 0)
            if agg_total_rows > 0:
                fail_pct = failed / agg_total_rows
                if fail_pct > rule.max_fail_pct:
                    rejection_reasons.append(
                        f"Rule '{rule.name}' failed {fail_pct:.1%} of rows "
                        f"(max allowed: {rule.max_fail_pct:.1%})"
                    )

        batch_rejected = len(rejection_reasons) > 0
        passed = len(final_errors) == 0 and not batch_rejected and (self.allow_rule_failures or not agg_skipped)

        # --- Evaluate SLAs for Streaming ---
        sla_violations = []
        pipeline_duration = time.perf_counter() - (pipeline_start_time or time.perf_counter())
        if self.global_max_duration_seconds is not None and pipeline_duration > self.global_max_duration_seconds:
            sla_violations.append(
                f"Execution time ({pipeline_duration:.2f}s) exceeded SLA ({self.global_max_duration_seconds}s)")

        if self.global_warning_fail_pct is not None and global_fail_pct > self.global_warning_fail_pct:
            sla_violations.append(
                f"Global failure rate {global_fail_pct:.1%} exceeds warning SLA ({self.global_warning_fail_pct:.1%})")

        return ValidationResult(
            config_version=self.version,
            passed=passed,
            batch_rejected=batch_rejected,
            rejection_reasons=rejection_reasons,
            sla_breached=len(sla_violations) > 0,
            sla_violations=sla_violations,
            total_rows=agg_total_rows,
            total_rows_affected=agg_total_affected,
            errors=final_errors,
            warnings=final_warnings,
            sample_bad_rows=dict(agg_sample_bad),
            rule_timings=dict(agg_rule_timings),
            skipped_rules=agg_skipped,
            evaluated_rules=[r.name for r in self.rules],
            remediations=final_remediations,
            sample_remediations=dict(agg_sample_remed)
        )

    def validate_row(self, row: Union[dict, str]) -> RowLevelResult:
        if isinstance(row, str):
            try:
                row_dict = json.loads(row)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON string: {e}")
        else:
            row_dict = row

        df_working = pd.DataFrame([row_dict])

        try:
            self._validate_schema(df_working)
        except ValueError as e:
            return RowLevelResult(
                passed=False,
                errors=[f"schema_error: {e}"],
            )

        for rule in self.rules:
            if rule.type == "transform":
                try:
                    df_working = rule.apply_transform(df_working)
                except Exception as e:
                    logger.error(f"Transform '{rule.name}' crashed during real-time setup: {e}")

        errors = []
        warnings = []
        infos = []
        skipped_stateful = []
        rule_failure_masks = {}

        for rule in self.rules:
            if rule.type == "transform":
                continue

            if rule.type == "unique" or getattr(rule, 'requires_full_dataset', False):
                skipped_stateful.append(rule.name)
                rule_failure_masks[rule.name] = pd.Series([False], index=[0])
                continue

            try:
                bad_mask = rule.evaluate(df_working)

                if rule.depends_on:
                    for dep_name in rule.depends_on:
                        if dep_name in rule_failure_masks:
                            bad_mask = bad_mask & ~rule_failure_masks[dep_name]
                        else:
                            logger.warning(f"Dependency '{dep_name}' for rule '{rule.name}' not found.")

                rule_failure_masks[rule.name] = bad_mask

            except Exception as e:
                logger.error(f"Rule '{rule.name}' crashed during real-time validation: {type(e).__name__}: {e}")
                if rule.severity == "ERROR":
                    errors.append(rule.name)
                elif rule.severity == "WARNING":
                    warnings.append(rule.name)
                continue

            if bad_mask.iloc[0]:
                if rule.severity == "ERROR":
                    errors.append(rule.name)
                elif rule.severity == "WARNING":
                    warnings.append(rule.name)
                else:
                    infos.append(rule.name)

        passed = len(errors) == 0

        return RowLevelResult(
            passed=passed,
            errors=errors,
            warnings=warnings,
            info=infos,
            skipped_stateful=skipped_stateful
        )

    def validate(self, df: pd.DataFrame, skip_sla: bool = False) -> ValidationResult:
        """Executes the validation pipeline and generates a report."""
        pipeline_start_time = time.perf_counter()

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
        remediations = []
        sample_remediations = collections.defaultdict(list)
        for rule in self.rules:
            if rule.type == "transform":
                try:
                    series_before = df_working[
                        rule.field].copy() if rule.field and rule.field in df_working.columns else None
                    df_before = df_working.copy() if series_before is None else None

                    df_working = rule.apply_transform(df_working)

                    # Extract the "why" for the audit trail
                    reason = getattr(rule, "description", None) or f"Applied auto-remediation via '{rule.name}'"

                    if series_before is not None:
                        series_after = df_working[rule.field]
                        changed_mask = (series_before != series_after) & ~(series_before.isna() & series_after.isna())
                        changed_count = int(changed_mask.sum())

                        if changed_count > 0:
                            remediations.append({
                                "rule": rule.name,
                                "field": rule.field,
                                "rows_modified": changed_count,
                                "reason": reason
                            })
                            for idx in df_working[changed_mask].head(5).index:
                                sample_remediations[rule.name].append({
                                    "row_index": idx,
                                    "original": series_before.loc[idx],
                                    "remediated": series_after.loc[idx]
                                })

                    elif df_before is not None:
                        if list(df_before.columns) != list(df_working.columns):
                            # A new column was added (e.g., flag_negatives). Do not count as a row modification.
                            changed_count = 0
                        else:
                            changed_mask = (df_before != df_working) & ~(df_before.isna() & df_working.isna())
                            changed_rows = changed_mask.any(axis=1)
                            changed_count = int(changed_rows.sum())

                        if changed_count > 0:
                            remediations.append({
                                "rule": rule.name,
                                "field": "cross_field",
                                "rows_modified": changed_count,
                                "reason": reason
                            })

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

        rejection_reasons = []

        # 1. Per-Rule Thresholds
        for rule in self.rules:
            if rule.name in rule_failure_masks and rule.max_fail_pct is not None and rule.severity == "ERROR":
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

        # --- Evaluate SLAs for Batch ---
        sla_violations = []
        if not skip_sla:
            pipeline_duration = time.perf_counter() - pipeline_start_time
            if self.global_max_duration_seconds is not None and pipeline_duration > self.global_max_duration_seconds:
                sla_violations.append(
                    f"Execution time ({pipeline_duration:.2f}s) exceeded SLA ({self.global_max_duration_seconds}s)")

            if self.global_warning_fail_pct is not None and global_fail_pct > self.global_warning_fail_pct:
                sla_violations.append(
                    f"Global failure rate {global_fail_pct:.1%} exceeds warning SLA ({self.global_warning_fail_pct:.1%})")

        return ValidationResult(
            config_version=self.version,
            passed=passed,
            batch_rejected=batch_rejected,
            rejection_reasons=rejection_reasons,
            sla_breached=len(sla_violations) > 0,
            sla_violations=sla_violations,
            total_rows=total_rows,
            total_rows_affected=len(affected_indices),
            errors=errors,
            warnings=warnings,
            sample_bad_rows=sample_bad,
            rule_timings=rule_timings,
            skipped_rules=skipped,
            evaluated_rules=[r.name for r in self.rules],
            remediations=remediations,
            sample_remediations=dict(sample_remediations)
        )

    def clean(self, df: pd.DataFrame, strict: bool = True, target_rules: Optional[List[str]] = None,
              val_report: Optional[ValidationResult] = None) -> pd.DataFrame:
        if val_report is None:
            val_report = self.validate(df)

        if val_report.batch_rejected:
            raise RuntimeError(
                f"Refusing to clean: Batch exceeded failure thresholds. Reasons:\n" +
                "\n".join([f"- {r}" for r in val_report.rejection_reasons])
            )

        self._validate_schema(df)
        df_clean = df.copy()

        for rule in self.rules:
            if rule.type == "transform":
                try:
                    df_clean = rule.apply_transform(df_clean)
                except Exception as e:
                    logger.error(f"FATAL ERROR: Transform rule '{rule.name}' crashed: {e}. Skipping rule.")
                    continue

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