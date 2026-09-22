"""
Loads pipeline_config.yaml and exposes it as simple, typed-ish objects.

This is the single place that knows how to read the YAML - the DAG and the
generic pipeline engine both build on top of this, so adding a new source to
the pipeline is a YAML edit here, not a code change in either of those.
"""

from dataclasses import dataclass, field
from pathlib import Path
import os

import yaml


CONFIG_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = CONFIG_ROOT / "pipeline_config.yaml"
SUPPORTED_ENVIRONMENTS = {"dev", "staging", "prod"}

def environment_config_path(environment=None):
    env = (environment or os.getenv("ETL_ENV", "dev")).strip().lower()
    if env not in SUPPORTED_ENVIRONMENTS:
        raise ValueError(
            f"Unsupported ETL_ENV '{env}'. Expected one of: "
            f"{', '.join(sorted(SUPPORTED_ENVIRONMENTS))}"
        )
    filename = "pipeline_config.yaml" if env == "dev" else f"pipeline_config.{env}.yaml"
    return CONFIG_ROOT / filename


@dataclass
class SourceConfig:
    name: str
    path: str
    table: str
    date_column: str
    conflict_keys: list
    columns: dict
    depends_on: str = None
    integer_columns: list = field(default_factory=list)
    numeric_columns: list = field(default_factory=list)
    quality_check_column: str = None
    null_rate_threshold: float = 0.10
    negative_rate_threshold: float = 0.05
    min_rows: int = 1
    max_rows: int = 1_000_000
    history_table: str = None
    schema_evolution: str = "quarantine"


@dataclass
class ArchiveConfig:
    table: str
    archive_table: str
    date_column: str
    cutoff_days: int


@dataclass
class PipelineConfig:
    schedule: str
    sources: list
    archive: ArchiveConfig
    environment: str = "dev"
    quality_sla_min_pass_rate: float = 0.95

    def source_names(self):
        return [s.name for s in self.sources]

    def get_source(self, name):
        for s in self.sources:
            if s.name == name:
                return s
        raise KeyError(f"No source named '{name}' in pipeline config")


def validate_dependency_order(sources):
    """Reject dependencies that point to a later source or create duplicates/cycles."""
    seen = set()
    names = {s.name for s in sources}
    if len(names) != len(sources):
        raise ValueError("Duplicate source names are not allowed")
    for source in sources:
        if source.depends_on:
            if source.depends_on not in names:
                raise ValueError(f"Source '{source.name}' depends on unknown source '{source.depends_on}'")
            if source.depends_on not in seen:
                raise ValueError(
                    f"Source '{source.name}' depends on '{source.depends_on}', "
                    "but the dependency must appear earlier in the sources list"
                )
        seen.add(source.name)
    return True


def load_pipeline_config(config_path=None):

    # An explicitly supplied path remains authoritative for backwards compatibility
    # and for replay/tests. Environment selection applies only when no path is supplied.
    path = Path(config_path) if config_path else environment_config_path()

    if not path.exists():
        raise FileNotFoundError(f"pipeline config not found at {path}")

    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    sources = []
    for raw_source in raw.get("sources", []):
        sources.append(
            SourceConfig(
                name=raw_source["name"],
                path=raw_source["path"],
                table=raw_source["table"],
                date_column=raw_source.get("date_column", "date"),
                conflict_keys=raw_source["conflict_keys"],
                columns=raw_source["columns"],
                depends_on=raw_source.get("depends_on"),
                integer_columns=raw_source.get("integer_columns", []),
                numeric_columns=raw_source.get("numeric_columns", []),
                quality_check_column=raw_source.get("quality_check_column"),
                null_rate_threshold=raw_source.get("null_rate_threshold", 0.10),
                negative_rate_threshold=raw_source.get("negative_rate_threshold", 0.05),
                min_rows=raw_source.get("min_rows", 1),
                max_rows=raw_source.get("max_rows", 1_000_000),
                history_table=raw_source.get("history_table"),
                schema_evolution=raw_source.get("schema_evolution", "quarantine"),
            )
        )

    archive_raw = raw.get("archive", {})
    archive = ArchiveConfig(
        table=archive_raw.get("table", "sales_fact"),
        archive_table=archive_raw.get("archive_table", "sales_fact_archive"),
        date_column=archive_raw.get("date_column", "date"),
        cutoff_days=archive_raw.get("cutoff_days", 730),
    )

    config = PipelineConfig(
        schedule=raw.get("schedule", "0 2 * * *"),
        sources=sources,
        archive=archive,
        environment=raw.get("environment", "dev"),
        quality_sla_min_pass_rate=float(raw.get("quality_sla_min_pass_rate", 0.95)),
    )
    validate_dependency_order(config.sources)
    return config
