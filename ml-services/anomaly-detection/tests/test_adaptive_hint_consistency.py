"""
Fix 6: the root-cause hint and the explanation must follow the FINAL
(adaptive) alert decision, not the base model's own decision.
"""

import src.predict as predict

READING = {"temperature": 30.0, "humidity": 40.0, "stock_count": 100.0}
HINT = {
    "incident_type": "temperature_spike",
    "similarity": 0.95,
    "description": "Looks like a temperature spike.",
    "similar_past_incidents": 4,
}


class _Details(dict):
    """Model details where any key the test doesn't care about is None."""

    def __missing__(self, key):
        return None


def _base_model(is_anomaly):
    return _Details(
        model="lof",
        score=0.9,
        is_anomaly=is_anomaly,
        primary_reason={"feature": "temperature", "contribution": 0.8},
        root_cause_hint=None,
        explanation="from the base model",
    )


def _patch_common(monkeypatch, base_is_anomaly):
    monkeypatch.setattr(
        predict, "_get_prediction_details", lambda reading, model: _base_model(base_is_anomaly)
    )
    monkeypatch.setattr(predict, "get_incident_library", lambda: {"fake": "library"})
    monkeypatch.setattr(predict, "match_incident", lambda reading, library: HINT)


class _Engine:
    def __init__(self, alert):
        self.alert = alert

    def process(self, **kwargs):
        return {"alert": self.alert, "threshold": 0.5}


class _Manager:
    def __init__(self, alert):
        self.alert = alert

    def is_anomaly(self, score):
        return self.alert, 0.5


def test_engine_alert_gets_a_hint_even_if_base_model_said_normal(monkeypatch):
    _patch_common(monkeypatch, base_is_anomaly=False)
    monkeypatch.setattr(predict, "adaptive_engine_manager", _Engine(alert=True))

    out = predict.adaptive_engine_predict(READING, "lof")

    assert out["is_anomaly"] is True
    assert out["root_cause_hint"] == HINT
    assert "temperature spike" in out["explanation"]


def test_engine_no_alert_has_no_hint_even_if_base_model_flagged(monkeypatch):
    _patch_common(monkeypatch, base_is_anomaly=True)
    monkeypatch.setattr(predict, "adaptive_engine_manager", _Engine(alert=False))

    out = predict.adaptive_engine_predict(READING, "lof")

    assert out["is_anomaly"] is False
    assert out["root_cause_hint"] is None
    assert out["explanation"] == "Reading is within normal operating behaviour."


def test_adaptive_predict_hint_follows_the_adaptive_alert(monkeypatch):
    _patch_common(monkeypatch, base_is_anomaly=False)
    monkeypatch.setattr(predict, "initialize_adaptive_thresholds", lambda: None)
    monkeypatch.setattr(predict, "get_adaptive_threshold", lambda name: _Manager(alert=True))

    out = predict.adaptive_predict(READING, "lof")

    assert out["root_cause_hint"] == HINT
    assert "temperature spike" in out["explanation"]