# Changelog

All notable changes to the EAICSP Shared Feature Engineering Library
are documented in this file.

## [0.1.0] - 2026-10-06

### Added

- Installable Python package structure using `src/feature_lib`.
- Explicit public API for feature engineering, feature quality,
  feature usefulness, feature catalog, drift detection, and feature storage.
- Point-in-time `asof_join` functionality for leakage-safe historical
  feature attachment.
- Leakage-safe sensor feature engineering built on `asof_join`, including
  rolling z-score, rate of change, rolling minimum/maximum, and
  cross-sensor ratio features.
- Leakage-safe ETA feature engineering built on `asof_join`, including
  historical carrier, route, carrier-route, departure weekday, and
  departure season statistics.
- Optional service dependencies for FastAPI and Uvicorn.
- Development dependencies for pytest and HTTPX.

### Notes

- Package version `0.1.0` is independent of feature-definition
  versions such as `v1` and `v2`.
- Historical sensor and ETA features are designed to use only information
  available strictly before the observation or departure time.
- Existing feature-generation behavior is intended to remain unchanged
  except for the leakage-safe historical feature additions required by
  the current milestone.