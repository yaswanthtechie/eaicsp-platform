"""Evaluation gate for CI: compare a candidate MLflow run to a baseline run.

Exit codes (the only thing CI reads):
    0  PASS        candidate is within the allowed regression margin
    1  FAIL        candidate is worse than baseline beyond the margin
    2  NO VERDICT  a verdict could not be reached (bad input, missing run or
                   metric, NaN, unreadable MLflow, unexpected crash)

The gate fails closed: it never passes when it could not actually check.
It is read-only: it only calls MlflowClient.get_run() and never logs,
tags, deletes or modifies anything.
"""
import argparse
import math
import os
import sys

from .metrics import HIGHER_IS_BETTER_METRICS, LOWER_IS_BETTER_METRICS, TARGET_METRICS

EXIT_PASS = 0
EXIT_REGRESSION = 1
EXIT_NO_VERDICT = 2

# Absorbs floating-point noise (e.g. 0.1 + 0.2 vs 0.3) so an identical model
# is never failed at a 0% margin because of representation error.
_TOLERANCE = 1e-12


class GateError(Exception):
    """Raised when the gate cannot reach a verdict (maps to exit code 2).

    Why a dedicated type: it separates "we could not check" from "we checked
    and the model is worse", so callers can never confuse the two.
    """


def parse_max_regression(text) -> float:
    """Parse a margin like '2%' into the fraction 0.02.

    Why: a bare '2' is ambiguous (2% or 200%?), so the '%' sign is mandatory
    rather than guessing. Negative, NaN and infinite margins are rejected.
    """
    if not isinstance(text, str) or not text.strip().endswith("%"):
        raise GateError(
            f"max regression must be a percentage ending in '%' (e.g. '2%'), got {text!r}"
        )
    try:
        pct = float(text.strip()[:-1].strip())
    except ValueError as exc:
        raise GateError(f"max regression is not a number: {text!r}") from exc
    if not math.isfinite(pct) or pct < 0:
        raise GateError(f"max regression must be a finite, non-negative percentage, got {text!r}")
    return pct / 100.0


def resolve_direction(metric: str, higher_is_better=None) -> bool:
    """Return True if a higher value of `metric` is better, False if lower.

    Why: the direction comes from the shared registry so the gate can never
    disagree with the leaderboard. Unknown metrics need an explicit flag,
    a flag contradicting the registry is refused, and target-style metrics
    (e.g. interval_coverage, best when close to a target) cannot be gated
    without a target, so they are refused instead of guessed.
    """
    if metric in TARGET_METRICS:
        raise GateError(
            f"metric '{metric}' is best when close to a target value, not higher or lower; "
            f"the gate cannot judge it without a target. Gate on a directional metric instead."
        )
    if metric in HIGHER_IS_BETTER_METRICS:
        registry = True
    elif metric in LOWER_IS_BETTER_METRICS:
        registry = False
    else:
        registry = None

    if registry is None:
        if higher_is_better is None:
            raise GateError(
                f"metric '{metric}' is not in the registry; pass --higher-is-better "
                f"or --lower-is-better explicitly."
            )
        return higher_is_better
    if higher_is_better is not None and higher_is_better != registry:
        word = "higher" if registry else "lower"
        raise GateError(f"metric '{metric}' is registered as {word}-is-better; the flag contradicts it.")
    return registry


def compare_values(candidate: float, baseline: float, max_regression: float,
                   higher_is_better: bool) -> dict:
    """Decide pass/fail from two numbers.

    Why: regression is measured RELATIVE to the baseline (positive = worse,
    negative = improvement) using abs(baseline) as the denominator, so it
    also works for negative-valued metrics. Landing exactly on the margin
    passes. A zero baseline makes a relative change undefined: equal or
    better still passes, any worsening raises rather than dividing by zero.
    """
    for name, value in (("candidate", candidate), ("baseline", baseline)):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise GateError(f"{name} value must be a finite number, got {value!r}")
    if not math.isfinite(max_regression) or max_regression < 0:
        raise GateError("max_regression must be a finite, non-negative fraction")

    worse_by = (baseline - candidate) if higher_is_better else (candidate - baseline)
    if baseline == 0:
        if worse_by > 0:
            raise GateError(
                "baseline value is 0, so a relative regression is undefined and the "
                "candidate is worse; cannot reach a verdict."
            )
        regression = 0.0
    else:
        regression = worse_by / abs(baseline)

    return {
        "passed": bool(regression <= max_regression + _TOLERANCE),
        "regression": float(regression),
        "max_regression": float(max_regression),
        "candidate_value": float(candidate),
        "baseline_value": float(baseline),
        "higher_is_better": bool(higher_is_better),
    }


def read_run_metric(client, run_id: str, metric: str, role: str) -> float:
    """Read the final logged value of `metric` from one MLflow run (read-only).

    Why: only FINISHED runs are trusted (a FAILED or RUNNING run has partial
    metrics), and a missing metric, NaN or infinity raises instead of
    defaulting, so a broken run can never be waved through. MLflow's
    run.data.metrics holds the latest logged value of each metric.
    """
    try:
        run = client.get_run(run_id)
    except Exception as exc:
        raise GateError(f"cannot read {role} run '{run_id}': {exc}") from exc
    status = run.info.status
    if status != "FINISHED":
        raise GateError(f"{role} run '{run_id}' has status {status}, expected FINISHED")
    metrics = run.data.metrics
    if metric not in metrics:
        raise GateError(
            f"{role} run '{run_id}' has no metric '{metric}'. Logged metrics: {sorted(metrics)}"
        )
    value = metrics[metric]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise GateError(f"{role} run '{run_id}': metric '{metric}' is not a finite number ({value!r})")
    return float(value)


def _build_client(tracking_uri):
    """Create a read-only MLflow client from an explicit tracking URI.

    Why: with no URI MLflow silently falls back to a local ./mlruns folder,
    and a mistyped sqlite path would make MLflow CREATE an empty database.
    Both are silent guesses, so a URI is required and a missing sqlite file
    is refused.
    """
    uri = tracking_uri or os.environ.get("MLFLOW_TRACKING_URI")
    if not uri:
        raise GateError(
            "no MLflow tracking URI: pass --tracking-uri or set MLFLOW_TRACKING_URI"
        )
    prefix = "sqlite:///"
    if uri.startswith(prefix) and not os.path.isfile(uri[len(prefix):]):
        raise GateError(f"sqlite database not found: {uri[len(prefix):]}")
    try:
        from mlflow.tracking import MlflowClient
    except ImportError as exc:
        raise GateError("mlflow is not installed; run: pip install eval-framework[mlflow]") from exc
    return MlflowClient(tracking_uri=uri)


def run_gate(candidate_run_id, baseline_run_id, metric, max_regression,
             tracking_uri=None, higher_is_better=None, client=None) -> dict:
    """Run the full gate and return the result dict (raises GateError if no verdict).

    Why: all cheap input checks happen BEFORE touching MLflow so bad
    arguments fail fast. Comparing a run with itself always passes, which is
    almost certainly a CI misconfiguration, so it is refused.
    `client` may be injected (tests); otherwise one is built from the URI.
    """
    for name, value in (("candidate", candidate_run_id), ("baseline", baseline_run_id),
                        ("metric", metric)):
        if not isinstance(value, str) or not value.strip():
            raise GateError(f"{name} must be a non-empty string")
    if candidate_run_id == baseline_run_id:
        raise GateError("candidate and baseline are the same run; nothing to compare")
    margin = parse_max_regression(max_regression)
    direction = resolve_direction(metric, higher_is_better)

    if client is None:
        client = _build_client(tracking_uri)
    candidate = read_run_metric(client, candidate_run_id, metric, "candidate")
    baseline = read_run_metric(client, baseline_run_id, metric, "baseline")

    result = compare_values(candidate, baseline, margin, direction)
    result.update(metric=metric, candidate_run_id=candidate_run_id, baseline_run_id=baseline_run_id)
    return result


def format_result(result: dict) -> str:
    """One human-readable line for CI logs.

    Why: the exit code is the verdict, but whoever opens the failed check
    needs the numbers without re-running anything.
    """
    verdict = "PASS" if result["passed"] else "FAIL"
    return (
        f"eval-gate: {verdict} metric={result['metric']} "
        f"candidate={result['candidate_value']:g} baseline={result['baseline_value']:g} "
        f"regression={result['regression'] * 100:+.2f}% "
        f"(positive = worse, allowed {result['max_regression'] * 100:.2f}%)"
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Why: every input that changes the verdict is a required, explicit
    argument, so nothing is defaulted silently. Bad usage exits with code 2,
    which matches "no verdict".
    """
    parser = argparse.ArgumentParser(
        prog="eval-gate",
        description="Exit non-zero when a candidate MLflow run is worse than a baseline run.",
    )
    parser.add_argument("--candidate", required=True, help="MLflow run id of the new model")
    parser.add_argument("--baseline", required=True, help="MLflow run id of the current model")
    parser.add_argument("--metric", required=True, help="metric name, e.g. mae")
    parser.add_argument("--max-regression", required=True,
                        help="allowed relative worsening vs baseline, e.g. 2%%")
    parser.add_argument("--tracking-uri", default=None,
                        help="MLflow tracking URI (or set MLFLOW_TRACKING_URI)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--higher-is-better", action="store_true",
                       help="required for metrics not in the registry")
    group.add_argument("--lower-is-better", action="store_true",
                       help="required for metrics not in the registry")
    return parser


def main(argv=None) -> int:
    """CLI entry point; returns the process exit code.

    Why: EVERY failure path returns 2. An uncaught exception would make
    Python exit with 1, which CI would read as "model regressed" instead of
    "gate could not run", so unexpected errors are caught and mapped to 2.
    """
    args = build_parser().parse_args(argv)
    override = True if args.higher_is_better else (False if args.lower_is_better else None)
    try:
        result = run_gate(args.candidate, args.baseline, args.metric, args.max_regression,
                          tracking_uri=args.tracking_uri, higher_is_better=override)
    except GateError as exc:
        print(f"eval-gate: NO VERDICT - {exc}", file=sys.stderr)
        return EXIT_NO_VERDICT
    except Exception as exc:  # fail closed on anything unexpected
        print(f"eval-gate: NO VERDICT - unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_NO_VERDICT
    print(format_result(result))
    return EXIT_PASS if result["passed"] else EXIT_REGRESSION


if __name__ == "__main__":
    sys.exit(main())