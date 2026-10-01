# Changelog

All notable changes to the EAICSP Shared Feature Engineering Library
are documented in this file.

## [0.1.0] - Initial package release

### Added
- Installable Python package structure using `src/feature_lib`.
- Explicit public API for feature engineering, feature quality,
  feature usefulness, feature catalog, drift detection, and feature storage.
- Optional service dependencies for FastAPI and Uvicorn.
- Development dependencies for pytest and HTTPX.

### Notes
- Package version `0.1.0` is independent of feature-definition
  versions such as `v1` and `v2`.
- Existing feature-generation behavior is intended to remain unchanged.
