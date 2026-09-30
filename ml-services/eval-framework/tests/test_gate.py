import subprocess
import sys
from types import SimpleNamespace

import pytest
from mlflow.tracking import MlflowClient

from eval_framework import gate
from eval_framework.gate import (
    GateError, compare_values, main, parse_max_regression, resolve_direction, run_gate,
)


# ---------- helpers ----------
@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    uri = f"sqlite:///{tmp_path}/gate.db"
    client = MlflowClient(tracking_uri=uri)
    exp = client.create_experiment("gate-exp")
    return SimpleNamespace(uri=uri, client=client, exp=exp)


def make_run(env, metrics, status="FINISHED"):
    run = env.client.create_run(env.exp)
    rid = run.info.run_id
    for k, v in metrics.items():
        env.client.log_metric(rid, k, v, step=0)
    env.client.set_terminated(rid, status)
    return rid


class FakeClient:
    def __init__(self, runs):
        self.runs = runs

    def get_run(self, run_id):
        status, metrics = self.runs[run_id]
        return SimpleNamespace(info=SimpleNamespace(status=status),
                               data=SimpleNamespace(metrics=metrics))


# ---------- parse_max_regression ----------
def test_parse_max_regression_ok():
    assert parse_max_regression("2%") == pytest.approx(0.02)
    assert parse_max_regression("0%") == 0.0
    assert parse_max_regression(" 2.5 % ") == pytest.approx(0.025)


@pytest.mark.parametrize("bad", ["2", "0.02", "abc%", "-1%", "nan%", "inf%", "", "%", None, 2])
def test_parse_max_regression_rejects(bad):
    with pytest.raises(GateError):
        parse_max_regression(bad)


# ---------- resolve_direction ----------
def test_resolve_direction_registry():
    assert resolve_direction("mae") is False
    assert resolve_direction("f1") is True
    assert resolve_direction("mae", False) is False


def test_resolve_direction_unknown_needs_flag():
    with pytest.raises(GateError):
        resolve_direction("r2")
    assert resolve_direction("r2", True) is True
    assert resolve_direction("r2", False) is False


def test_resolve_direction_conflict_and_target():
    with pytest.raises(GateError):
        resolve_direction("mae", True)
    with pytest.raises(GateError):
        resolve_direction("interval_coverage")
    with pytest.raises(GateError):
        resolve_direction("interval_coverage", True)


# ---------- compare_values ----------
def test_lower_is_better_boundaries():
    assert compare_values(101, 100, 0.02, False)["passed"] is True
    r = compare_values(102, 100, 0.02, False)          # exactly on the margin passes
    assert r["passed"] is True and r["regression"] == pytest.approx(0.02)
    assert compare_values(103, 100, 0.02, False)["passed"] is False


def test_improvement_passes_with_negative_regression():
    r = compare_values(90, 100, 0.0, False)
    assert r["passed"] is True and r["regression"] == pytest.approx(-0.10)


def test_higher_is_better():
    assert compare_values(0.79, 0.80, 0.02, True)["passed"] is True    # 1.25% worse
    assert compare_values(0.78, 0.80, 0.02, True)["passed"] is False   # 2.5% worse
    assert compare_values(0.90, 0.80, 0.0, True)["passed"] is True


def test_floating_point_noise_does_not_fail_zero_margin():
    assert compare_values(0.1 + 0.2, 0.3, 0.0, False)["passed"] is True


def test_negative_baseline_uses_abs_denominator():
    assert compare_values(-9.8, -10.0, 0.02, False)["passed"] is True
    assert compare_values(-9.7, -10.0, 0.02, False)["passed"] is False


def test_zero_baseline():
    assert compare_values(0, 0, 0.02, False)["passed"] is True
    assert compare_values(-1, 0, 0.02, False)["passed"] is True
    with pytest.raises(GateError):
        compare_values(1, 0, 0.02, False)


@pytest.mark.parametrize("c,b", [(float("nan"), 1), (1, float("nan")),
                                 (float("inf"), 1), (1, float("-inf")), (None, 1), ("1", 1)])
def test_compare_values_rejects_non_finite(c, b):
    with pytest.raises(GateError):
        compare_values(c, b, 0.02, False)


# ---------- run_gate against real MLflow (sqlite) ----------
def test_good_candidate_passes(env):
    base = make_run(env, {"mae": 10.0})
    cand = make_run(env, {"mae": 10.1})   # 1% worse, 2% allowed
    r = run_gate(cand, base, "mae", "2%", tracking_uri=env.uri)
    assert r["passed"] is True and r["metric"] == "mae"


def test_deliberately_worse_candidate_fails(env):
    base = make_run(env, {"mae": 10.0})
    cand = make_run(env, {"mae": 11.0})   # 10% worse
    r = run_gate(cand, base, "mae", "2%", tracking_uri=env.uri)
    assert r["passed"] is False and r["regression"] == pytest.approx(0.10)


def test_higher_is_better_metric_from_registry(env):
    base = make_run(env, {"f1": 0.80})
    cand = make_run(env, {"f1": 0.70})
    assert run_gate(cand, base, "f1", "2%", tracking_uri=env.uri)["passed"] is False


def test_uses_final_logged_value_not_first(env):
    run = env.client.create_run(env.exp).info.run_id
    env.client.log_metric(run, "mae", 9.0, step=0)
    env.client.log_metric(run, "mae", 4.0, step=1)
    env.client.set_terminated(run, "FINISHED")
    base = make_run(env, {"mae": 5.0})
    assert run_gate(run, base, "mae", "0%", tracking_uri=env.uri)["candidate_value"] == 4.0


def test_gate_is_read_only(env):
    base = make_run(env, {"mae": 10.0})
    cand = make_run(env, {"mae": 11.0})
    before = (env.client.get_run(cand).data.metrics, env.client.get_run(base).data.metrics,
              len(env.client.search_runs([env.exp])))
    run_gate(cand, base, "mae", "2%", tracking_uri=env.uri)
    after = (env.client.get_run(cand).data.metrics, env.client.get_run(base).data.metrics,
             len(env.client.search_runs([env.exp])))
    assert before == after


def test_missing_run_fails_closed(env):
    base = make_run(env, {"mae": 10.0})
    with pytest.raises(GateError, match="cannot read"):
        run_gate("doesnotexist", base, "mae", "2%", tracking_uri=env.uri)


def test_missing_metric_fails_closed(env):
    base = make_run(env, {"mae": 10.0})
    cand = make_run(env, {"rmse": 1.0})
    with pytest.raises(GateError, match="no metric"):
        run_gate(cand, base, "mae", "2%", tracking_uri=env.uri)


def test_failed_run_fails_closed(env):
    base = make_run(env, {"mae": 10.0})
    cand = make_run(env, {"mae": 1.0}, status="FAILED")
    with pytest.raises(GateError, match="FINISHED"):
        run_gate(cand, base, "mae", "2%", tracking_uri=env.uri)


def test_same_run_refused(env):
    base = make_run(env, {"mae": 10.0})
    with pytest.raises(GateError, match="same run"):
        run_gate(base, base, "mae", "2%", tracking_uri=env.uri)


def test_unknown_metric_needs_flag_then_works(env):
    base = make_run(env, {"r2": 0.90})
    cand = make_run(env, {"r2": 0.50})
    with pytest.raises(GateError):
        run_gate(cand, base, "r2", "2%", tracking_uri=env.uri)
    r = run_gate(cand, base, "r2", "2%", tracking_uri=env.uri, higher_is_better=True)
    assert r["passed"] is False


def test_target_metric_refused(env):
    base = make_run(env, {"interval_coverage": 0.9})
    cand = make_run(env, {"interval_coverage": 0.95})
    with pytest.raises(GateError):
        run_gate(cand, base, "interval_coverage", "2%", tracking_uri=env.uri)


def test_no_tracking_uri_refused(env):
    with pytest.raises(GateError, match="tracking URI"):
        run_gate("a", "b", "mae", "2%")


def test_missing_sqlite_file_refused_and_not_created(tmp_path, monkeypatch):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    with pytest.raises(GateError, match="not found"):
        run_gate("a", "b", "mae", "2%", tracking_uri=f"sqlite:///{tmp_path}/nope.db")
    assert not (tmp_path / "nope.db").exists()


def test_tracking_uri_from_environment(env, monkeypatch):
    base = make_run(env, {"mae": 10.0})
    cand = make_run(env, {"mae": 10.0})
    monkeypatch.setenv("MLFLOW_TRACKING_URI", env.uri)
    assert run_gate(cand, base, "mae", "2%")["passed"] is True


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_metric_fails_closed(bad):
    client = FakeClient({"c": ("FINISHED", {"mae": bad}), "b": ("FINISHED", {"mae": 1.0})})
    with pytest.raises(GateError, match="finite"):
        run_gate("c", "b", "mae", "2%", client=client)


@pytest.mark.parametrize("args", [("", "b", "mae", "2%"), ("c", "b", "", "2%"),
                                  ("c", "b", "mae", "2")])
def test_bad_arguments_refused_before_mlflow(args):
    with pytest.raises(GateError):
        run_gate(*args)


# ---------- CLI ----------
def cli(env, cand, base, *extra, metric="mae", margin="2%"):
    return main(["--candidate", cand, "--baseline", base, "--metric", metric,
                 "--max-regression", margin, "--tracking-uri", env.uri, *extra])


def test_cli_exit_codes(env, capsys):
    base = make_run(env, {"mae": 10.0})
    good = make_run(env, {"mae": 10.1})
    worse = make_run(env, {"mae": 11.0})
    no_metric = make_run(env, {"rmse": 1.0})

    assert cli(env, good, base) == 0
    assert "PASS" in capsys.readouterr().out
    assert cli(env, worse, base) == 1
    assert "FAIL" in capsys.readouterr().out
    assert cli(env, no_metric, base) == 2
    assert "NO VERDICT" in capsys.readouterr().err


def test_cli_bad_usage_exits_2():
    with pytest.raises(SystemExit) as e:
        main([])
    assert e.value.code == 2
    with pytest.raises(SystemExit) as e:
        main(["--candidate", "a", "--baseline", "b", "--metric", "mae",
              "--max-regression", "2%", "--higher-is-better", "--lower-is-better"])
    assert e.value.code == 2


def test_cli_unexpected_crash_is_exit_2_not_1(monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(gate, "run_gate", boom)
    code = main(["--candidate", "a", "--baseline", "b", "--metric", "mae",
                 "--max-regression", "2%", "--tracking-uri", "x"])
    assert code == 2 and "unexpected RuntimeError" in capsys.readouterr().err


def test_real_process_exit_codes(env):
    base = make_run(env, {"mae": 10.0})
    good = make_run(env, {"mae": 10.1})
    worse = make_run(env, {"mae": 11.0})

    def run(cand):
        return subprocess.run(
            [sys.executable, "-m", "eval_framework.gate", "--candidate", cand,
             "--baseline", base, "--metric", "mae", "--max-regression", "2%",
             "--tracking-uri", env.uri],
            capture_output=True, text=True).returncode

    assert run(good) == 0
    assert run(worse) == 1
    assert run("doesnotexist") == 2