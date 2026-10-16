# Platform Service CI Template

## Purpose

The Platform Service CI workflow validates code quality, type safety, security, automated tests, and Docker image vulnerabilities before changes are merged.

**Workflow file:** `.github/workflows/platform-ci.yml`

## Trigger

The workflow runs for pull requests that modify files under `services/platform/**` or change the CI workflow itself.

## Pipeline jobs

| Job | Checks performed |
|---|---|
| Quality, security and unit tests | Ruff linting, mypy type checking, Bandit security checks, pip-audit dependency scanning, and pytest with coverage |
| Redis and Kafka integration tests | Cross-instance token revocation and Kafka event publishing and account-lock event integration |
| HTTP integration tests | Starts the Platform API on port 8005 and runs HTTP integration tests against a seeded test database |
| Docker and Trivy | Builds the service image and fails the scan when Trivy finds CRITICAL vulnerabilities that are not excluded by the configured policy |

## Performance and readable failures

- **pip caching:** GitHub Actions caches pip dependencies to reduce repeated downloads and speed up subsequent workflow runs.
- **Named steps:** Each major check runs in a clearly named step so the failed operation is easy to identify.
- **Readable test output:** pytest reports failed tests, assertions, and tracebacks. Use concise traceback output where appropriate.
- **Debugging integration failures:** When an integration test fails, inspect its job logs and the relevant service or API logs.
- **Security failures:** Review Bandit, pip-audit, and Trivy output to identify the affected code, dependency, or image vulnerability.

A failing required check must cause its job to fail. Do not ignore genuine lint, test, or security failures just to make the workflow green.

## Local validation

Run these commands from `services/platform` with the project's virtual environment activated.

```powershell
python -m ruff check app/core app/services

python -m mypy app/core app/services

python -m bandit -r app -ll

python -m pip_audit -r requirements.txt

python -m pytest -o addopts= -m "not integration" --tb=short -ra --cov=app --cov-report=term-missing --cov-report=xml:coverage.xml
```

Integration tests require the appropriate services and environment variables. Follow the repository's development setup instructions for Redis, Kafka, and the Platform API.

## Adopting this template for another service

To reuse the workflow for another EAICSP service, copy `.github/workflows/platform-ci.yml` and update these three areas:

### 1. Service paths

Update the pull-request path filters, working directories, and file paths to match the target service's directory.

### 2. Dependencies and checks

Update the dependency installation commands, requirements files, Ruff and mypy targets, test paths, and coverage configuration to match the service's technology stack.

### 3. Integration and container configuration

Update the required service containers, environment variables, health checks, startup commands, Dockerfile path, and image name. Keep only the integration dependencies required by the target service.

Preserve pip caching, clear step names, useful failure output, and the applicable security checks. Keep the configured Trivy CRITICAL vulnerability failure threshold unless the team explicitly approves a policy change.

## Pull request acceptance

A pull request is ready for review when all required CI jobs pass.

Before accepting the workflow as complete, verify the following:

- [ ] Open a real pull request that triggers the workflow.
- [ ] Confirm pip caching is configured and the workflow executes the expected jobs.
- [ ] Introduce a temporary lint violation and verify that the lint job fails with a readable message.
- [ ] Introduce a temporary failing test and verify that the test job fails with a useful assertion or traceback.
- [ ] Remove the deliberate failures and confirm the normal checks pass.
- [ ] Confirm the Docker image builds successfully.
- [ ] Confirm Trivy scans the image and fails the job for qualifying CRITICAL vulnerabilities.
- [ ] Review coverage results, security findings, integration-test failures, and Trivy output before merging.
- [ ] Confirm the final pull-request workflow run is green.

## Security notes

Use CI-only test credentials and secrets. Never commit production credentials or real secret keys. Keep dependency and container vulnerability scans enabled to detect known risks before merging.

## Maintenance

The Platform Service owner maintains this reference workflow. When the template changes, review this document and communicate relevant updates to other service owners before the next CI adoption round.
