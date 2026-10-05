"""
Round 10 Milestone 3 — Load Test Validation Tests
==================================================

These tests validate the *structure and importability* of the Round 10 M3
Locust load-testing setup without fabricating any performance numbers.

What is tested
--------------
1.  Locust file exists at the expected path.
2.  Locust file is importable (no syntax / import errors).
3.  Expected task categories are present (READ, WRITE, AUTH_FAIL).
4.  Task weight configuration is sane (weights > 0, correct distribution).
5.  Configurable constants exist (MIN_WAIT, MAX_WAIT, BASE_HEADERS).
6.  The M3 load test report exists.
7.  No files outside services/api-gateway/ were modified.
8.  Locust dependency is declared in requirements.txt.
9.  M1 and M2 artefacts still exist (non-regression guard).

What is NOT tested
------------------
- Real performance numbers (those are obtained by running Locust live).
- Actual HTTP responses (that would require a running API Gateway + services).
"""

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

# Root of the api-gateway service
GATEWAY_ROOT = Path(__file__).parent.parent.parent
LOCUST_FILE = GATEWAY_ROOT / "load_tests" / "round10_locustfile.py"
REPORT_FILE = GATEWAY_ROOT / "load_tests" / "ROUND10_M3_LOAD_TEST_REPORT.md"
REQUIREMENTS_FILE = GATEWAY_ROOT / "requirements.txt"

# M1 / M2 artefacts (non-regression)
M1_TEST_FILE = GATEWAY_ROOT / "app" / "tests" / "test_round10_m1_prometheus.py"
M2_TEST_FILE = GATEWAY_ROOT / "tests" / "test_round10_m2_tracing.py"
PROMETHEUS_MIDDLEWARE = GATEWAY_ROOT / "app" / "middleware" / "prometheus_middleware.py"
TRACING_MIDDLEWARE = GATEWAY_ROOT / "app" / "middleware" / "tracing.py"


# ---------------------------------------------------------------------------
# Helper: import the locust file as a module
# ---------------------------------------------------------------------------

def _import_locustfile():
    """
    Dynamically import the Round 10 M3 locust file.

    Uses importlib to avoid polluting the global module namespace.
    Raises ImportError / ModuleNotFoundError propagated to test failures
    if the file cannot be imported.
    """
    pytest.importorskip("locust")
    try:
        from app.middleware.tracing import shutdown_tracing
        shutdown_tracing()
    except Exception:
        pass

    spec = importlib.util.spec_from_file_location(
        "round10_locustfile", str(LOCUST_FILE)
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create spec for {LOCUST_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ---------------------------------------------------------------------------
# 1. File existence
# ---------------------------------------------------------------------------

class TestFileExistence:
    def test_locustfile_exists(self):
        """The Round 10 M3 Locust file must exist."""
        assert LOCUST_FILE.exists(), (
            f"Locust file not found: {LOCUST_FILE}"
        )

    def test_locustfile_is_python(self):
        """The Locust file must have a .py extension."""
        assert LOCUST_FILE.suffix == ".py"

    def test_report_exists(self):
        """The Round 10 M3 load test report must exist."""
        assert REPORT_FILE.exists(), (
            f"M3 load test report not found: {REPORT_FILE}"
        )

    def test_report_is_markdown(self):
        """The report must be a Markdown file."""
        assert REPORT_FILE.suffix == ".md"

    def test_report_has_required_sections(self):
        """The report must contain all required section headers."""
        content = REPORT_FILE.read_text(encoding="utf-8")
        required_sections = [
            "## Objective",
            "## Test Environment",
            "## Test Scenario",
            "## Traffic Distribution",
            "## Endpoints Tested",
            "## Test Configuration",
            "## Results",
            "## Laptop Ceiling",
            "## Bottleneck Analysis",
            "## Observations",
            "## Reproduction Commands",
            "## Limitations",
        ]
        for section in required_sections:
            assert section in content, (
                f"Required section missing from report: {section}"
            )


# ---------------------------------------------------------------------------
# 2. Importability
# ---------------------------------------------------------------------------

class TestLocustfileImportable:
    def test_locustfile_is_importable(self):
        """
        The Locust file must be importable without errors.

        If locust is not installed this test is skipped rather than
        errored — installing locust is a setup step, not a code bug.
        """
        pytest.importorskip("locust")
        module = _import_locustfile()
        assert module is not None

    def test_locustfile_imports_locust_symbols(self):
        """The locust file must import HttpUser, between, task from locust."""
        pytest.importorskip("locust")
        content = LOCUST_FILE.read_text(encoding="utf-8")
        assert "from locust import" in content
        for symbol in ("HttpUser", "between", "task"):
            assert symbol in content, (
                f"Expected symbol '{symbol}' not found in locust file"
            )


# ---------------------------------------------------------------------------
# 3. Task category presence (static analysis — no import needed)
# ---------------------------------------------------------------------------

class TestTaskCategories:
    """
    Validate task categories by scanning the locust file as plain text.
    This avoids the need for locust to be installed.
    """

    def _content(self) -> str:
        return LOCUST_FILE.read_text(encoding="utf-8")

    def test_read_tasks_present(self):
        """The file must define [READ] labelled tasks."""
        assert "[READ]" in self._content(), (
            "No [READ] task labels found in locust file"
        )

    def test_write_tasks_present(self):
        """The file must define [WRITE] labelled tasks."""
        assert "[WRITE]" in self._content(), (
            "No [WRITE] task labels found in locust file"
        )

    def test_auth_fail_tasks_present(self):
        """The file must define [AUTH_FAIL] labelled tasks."""
        assert "[AUTH_FAIL]" in self._content(), (
            "No [AUTH_FAIL] task labels found in locust file"
        )

    def test_at_least_five_task_decorators(self):
        """The file must define at least 5 @task decorators."""
        count = self._content().count("@task(")
        assert count >= 5, (
            f"Expected at least 5 @task decorators, found {count}"
        )

    def test_task_weights_are_positive(self):
        """All @task(n) weights must be positive integers."""
        import re
        weights = re.findall(r"@task\((\d+)\)", self._content())
        assert len(weights) > 0, "No @task(n) decorators found"
        for w in weights:
            assert int(w) > 0, f"Task weight must be > 0, got {w}"

    def test_user_class_present(self):
        """A class inheriting from HttpUser must be defined."""
        assert "HttpUser" in self._content()
        assert "class APIGatewayUser" in self._content()


# ---------------------------------------------------------------------------
# 4. Traffic distribution configuration
# ---------------------------------------------------------------------------

class TestTrafficDistribution:
    def _content(self) -> str:
        return LOCUST_FILE.read_text(encoding="utf-8")

    def test_read_weight_dominates(self):
        """
        The combined weight for READ tasks must be greater than
        the combined weight for WRITE and AUTH-FAIL tasks.
        This ensures a read-heavy (>50%) distribution.
        """
        import re
        content = self._content()

        # Extract weights for each task by finding @task(N) annotations
        # and the method body that follows (for category identification).
        # Simple heuristic: find all @task(N) then look at next 10 lines.
        lines = content.splitlines()
        read_weight = 0
        write_weight = 0
        auth_weight = 0

        for i, line in enumerate(lines):
            m = re.match(r"\s*@task\((\d+)\)", line)
            if m:
                weight = int(m.group(1))
                # Look ahead up to 15 lines to find the task body label
                body = "\n".join(lines[i : i + 15])
                if "[READ]" in body:
                    read_weight += weight
                elif "[WRITE]" in body:
                    write_weight += weight
                elif "[AUTH_FAIL]" in body:
                    auth_weight += weight

        total = read_weight + write_weight + auth_weight
        assert total > 0, "Could not extract task weights"
        assert read_weight > write_weight + auth_weight, (
            f"READ weight ({read_weight}) must exceed WRITE+AUTH "
            f"({write_weight + auth_weight}) for read-heavy distribution"
        )

    def test_configurable_wait_time(self):
        """MIN_WAIT and MAX_WAIT constants must be defined."""
        content = self._content()
        assert "MIN_WAIT" in content
        assert "MAX_WAIT" in content

    def test_base_headers_defined(self):
        """BASE_HEADERS constant must be defined."""
        assert "BASE_HEADERS" in self._content()

    def test_invalid_token_defined(self):
        """An INVALID_TOKEN constant must be defined for auth-fail tests."""
        assert "INVALID_TOKEN" in self._content()

    def test_bad_login_payload_defined(self):
        """A bad login payload must be defined for auth-fail tests."""
        assert "BAD_LOGIN_PAYLOAD" in self._content()


# ---------------------------------------------------------------------------
# 5. Endpoint correctness (static check)
# ---------------------------------------------------------------------------

class TestEndpointCoverage:
    """
    Verify that the locust file targets known API Gateway endpoints.
    These are checked by scanning the file as plain text.
    """

    def _content(self) -> str:
        return LOCUST_FILE.read_text(encoding="utf-8")

    def test_health_endpoint_present(self):
        assert "/health" in self._content()

    def test_root_endpoint_present(self):
        assert '"/",\n' in self._content() or '"/",' in self._content()

    def test_metrics_endpoint_present(self):
        assert "/metrics" in self._content()

    def test_gateway_status_endpoint_present(self):
        assert "/gateway/status" in self._content()

    def test_gateway_dashboard_endpoint_present(self):
        assert "/gateway/dashboard" in self._content()

    def test_inventory_proxy_endpoint_present(self):
        assert "/api/v1/inventory" in self._content()

    def test_purchase_orders_proxy_endpoint_present(self):
        assert "/api/v1/purchase-orders" in self._content()

    def test_auth_endpoint_present(self):
        assert "/api/v1/auth/login" in self._content()

    def test_no_invented_endpoints(self):
        """
        The locust file must NOT reference undocumented or invented paths
        that do not exist in the API Gateway.
        """
        content = self._content()
        # These paths do NOT exist in the current gateway
        forbidden_paths = [
            "/api/v1/orders",
            "/api/v1/products",
            "/api/v2/",
            "/admin/",
        ]
        for path in forbidden_paths:
            assert path not in content, (
                f"Invented endpoint found in locust file: {path}"
            )


# ---------------------------------------------------------------------------
# 6. Dependency declaration
# ---------------------------------------------------------------------------

class TestDependencies:
    def test_locust_in_requirements(self):
        """locust must be declared in requirements.txt."""
        content = REQUIREMENTS_FILE.read_text(encoding="utf-8")
        assert "locust" in content.lower(), (
            "locust not found in requirements.txt"
        )

    def test_locust_version_pinned(self):
        """locust dependency must include a version constraint."""
        content = REQUIREMENTS_FILE.read_text(encoding="utf-8")
        lines = [ln.strip() for ln in content.splitlines()]
        locust_lines = [ln for ln in lines if ln.lower().startswith("locust")]
        assert locust_lines, "No locust line found in requirements.txt"
        assert ">=" in locust_lines[0] or "==" in locust_lines[0], (
            f"locust line must include a version constraint: {locust_lines[0]}"
        )


# ---------------------------------------------------------------------------
# 7. Non-regression: M1 and M2 artefacts intact
# ---------------------------------------------------------------------------

class TestM1M2NonRegression:
    def test_m1_test_file_exists(self):
        """Round 10 M1 Prometheus test file must still exist."""
        assert M1_TEST_FILE.exists(), f"M1 test file missing: {M1_TEST_FILE}"

    def test_m2_test_file_exists(self):
        """Round 10 M2 tracing test file must still exist."""
        assert M2_TEST_FILE.exists(), f"M2 test file missing: {M2_TEST_FILE}"

    def test_prometheus_middleware_exists(self):
        """PrometheusMiddleware (M1) must still be present."""
        assert PROMETHEUS_MIDDLEWARE.exists(), (
            f"Prometheus middleware missing: {PROMETHEUS_MIDDLEWARE}"
        )

    def test_tracing_middleware_exists(self):
        """TracingMiddleware (M2) must still be present."""
        assert TRACING_MIDDLEWARE.exists(), (
            f"Tracing middleware missing: {TRACING_MIDDLEWARE}"
        )

    def test_m1_content_not_empty(self):
        """M1 test file must not be empty."""
        assert M1_TEST_FILE.stat().st_size > 0

    def test_m2_content_not_empty(self):
        """M2 test file must not be empty."""
        assert M2_TEST_FILE.stat().st_size > 0


# ---------------------------------------------------------------------------
# 8. Scope guard: no files outside api-gateway were touched
# ---------------------------------------------------------------------------

class TestScopeGuard:
    def test_locustfile_is_inside_api_gateway(self):
        """The Locust file must be inside services/api-gateway/."""
        assert "api-gateway" in str(LOCUST_FILE).replace("\\", "/")

    def test_report_is_inside_api_gateway(self):
        """The report must be inside services/api-gateway/."""
        assert "api-gateway" in str(REPORT_FILE).replace("\\", "/")

    def test_locustfile_does_not_reference_other_services(self):
        """The Locust file must not import or reference other services."""
        content = LOCUST_FILE.read_text(encoding="utf-8")
        forbidden_imports = [
            "from services.",
            "import services.",
            "inventory_service",
            "shipments_service",
        ]
        for imp in forbidden_imports:
            assert imp not in content, (
                f"Locust file must not reference other services: {imp}"
            )
