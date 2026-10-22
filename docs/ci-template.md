# CI template: adopting the Platform workflow for your service

Reference workflow: `.github/workflows/platform-ci.yml`

## Copy it and change four things

```bash
cp .github/workflows/platform-ci.yml .github/workflows/<service>-ci.yml
```

| # | What | Example for inventory |
|---|---|---|
| 1 | `on.pull_request.paths` (GitHub does not allow env vars here) | `"services/inventory/**"` and `".github/workflows/inventory-ci.yml"` |
| 2 | `env.SERVICE_DIR` | `services/inventory` |
| 3 | `env.IMAGE_NAME` | `inventory-service` |
| 4 | `working-directory` in each job | Replace `services/platform` with `services/inventory` |

Also rename `name:` at the top, for example `Inventory Service CI`.

The workflow uses literal paths for `working-directory` because job-level default working directories cannot use expressions. Update all three occurrences when copying the template.

## Then keep or delete jobs

| Job | Keep? |
|---|---|
| `quality-security-unit` | **Always keep.** Ruff, mypy, bandit, pip-audit, unit tests + coverage. |
| `docker-trivy` | **Always keep.** Needs a `Dockerfile` in `SERVICE_DIR`. |
| `integration` (Redis + Kafka) | **Platform-specific.** Keep only the containers your service uses, and point the pytest steps at your integration test files. Delete the job if you have none. |
| `http-integration` | **Platform-specific.** Replace the seed command, port and test file, or delete it. |

## What your service needs for this to work

- `requirements.txt` (runtime) and `requirements-dev.txt` (starts with `-r requirements.txt`, then ruff, mypy, bandit, pip-audit, pytest, pytest-cov)
- `pytest.ini` with `pythonpath = .` and the `integration` marker
- `pyproject.toml` with `[tool.ruff]` and `[tool.mypy]` sections (copy Platform's)
- A `Dockerfile` that runs as a non-root user
- No passwords or keys in test files. Read them from `os.environ`, and let CI generate them.

## Rules for every service

- Trivy fails on **CRITICAL** vulnerabilities that have a fix available (`ignore-unfixed: true`). Changing that needs team approval.
- Coverage floor is `--cov-fail-under=85`. Set yours to just below your current number and only raise it.
- Integration tests must **fail, not skip**, when `CI_REQUIRE_SERVICES=1`.
- Pin third-party actions to a commit SHA.

## Reading a failure

- **Ruff:** the error appears as an annotation on the changed line in the PR diff.
- **Tests:** `-ra --tb=short` prints one short traceback per failure, plus a summary of every failed or skipped test at the end.
- **HTTP integration:** the API log is printed automatically when the job fails.
- **Coverage:** shown as a table on the run's Summary page.

## Pull Request Acceptance Checklist

- [x] Open a real pull request that triggers the workflow.
- [x] Introduce a temporary lint violation and verify that the lint job fails with a readable message.
- [x] Introduce a temporary failing test and verify that the test job fails with a useful assertion or traceback.
- [x] Remove the deliberate failures and restore the intended implementation.
- [x] Confirm the Docker image builds successfully.
- [x] Confirm Trivy scans the image and handles qualifying CRITICAL vulnerabilities as configured.
- [x] Review coverage results, security findings, integration-test failures, and Trivy output before merging.
- [x] Confirm the final pull-request workflow run is green.

### Fix 10 Evidence

- Ruff failure: https://github.com/yaswanthtechie/eaicsp-platform/actions/runs/39730800033
- Unit-test failure: https://github.com/yaswanthtechie/eaicsp-platform/actions/runs/39732243873
- PR checks: https://github.com/yaswanthtechie/eaicsp-platform/pull/247/checks

The lint and unit-test failures were temporary verification changes and were reverted after their respective runs.
