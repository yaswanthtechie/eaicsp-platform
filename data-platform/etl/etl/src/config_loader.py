"""
Loads pipeline_config.yaml and exposes it as simple, typed-ish objects.

This is the single place that knows how to read the YAML - the DAG and the
generic pipeline engine both build on top of this, so adding a new source to
the pipeline is a YAML edit here, not a code change in either of those.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "pipeline_config.yaml"


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

    def source_names(self):
        return [s.name for s in self.sources]

    def get_source(self, name):
        for s in self.sources:
            if s.name == name:
                return s
        raise KeyError(f"No source named '{name}' in pipeline config")


def load_pipeline_config(config_path=None):

    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

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
            )
        )

    archive_raw = raw.get("archive", {})
    archive = ArchiveConfig(
        table=archive_raw.get("table", "sales_fact"),
        archive_table=archive_raw.get("archive_table", "sales_fact_archive"),
        date_column=archive_raw.get("date_column", "date"),
        cutoff_days=archive_raw.get("cutoff_days", 730),
    )

    return PipelineConfig(
        schedule=raw.get("schedule", "0 2 * * *"),
        sources=sources,
        archive=archive,
    )
