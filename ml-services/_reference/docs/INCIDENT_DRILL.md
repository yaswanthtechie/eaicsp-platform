# Incident Drill

## 1. Purpose

This document records an end-to-end incident drill for the unified ML serving layer.

The drill follows `docs/INCIDENT_RUNBOOK.md` through the real FastAPI serving API instead of directly testing an exception-throwing function.

The drill validates:

* Baseline model prediction
* Failure injection
* Incident detection
* Model/service inspection
* Failure containment
* Service recovery
* Post-recovery verification

---

## 2. Drill Scenario

A simulated model-serving failure was injected into the forecast prediction path.

The objective was to verify that the serving layer could:

1. Successfully serve a prediction before the incident.
2. Detect a prediction failure through the real API.
3. Inspect the model-serving state.
4. Contain the failure.
5. Restore a known-good serving path.
6. Verify successful predictions after recovery.

The failure was simulated and did not modify the actual model artifact.

---

## 3. Execution

The drill was executed from the `_reference` directory using:

```powershell
python scripts\incident_drill.py
```

The drill exercised the following real API endpoints:

```text
POST /models/batch-predict
GET  /models
```

The forecast model was used for the prediction request.

---

## 4. Timeline

The following timeline is the actual output from the incident drill.

| t (s) | Step                                  | Result | Detail                                                                     |
| ----: | ------------------------------------- | ------ | -------------------------------------------------------------------------- |
|  0.04 | Baseline prediction                   | OK     | Forecast prediction completed successfully.                                |
|  0.06 | Detection via `/models/batch-predict` | OK     | Prediction failed with `SIMULATED_MODEL_SERVING_FAILURE`.                  |
|  0.07 | Runbook detection: `GET /models`      | OK     | API returned 200 and reported forecast production version `v1` as `ready`. |
|  0.08 | Containment: restored known-good path | OK     | Prediction succeeded after restoring the original prediction path.         |
|  0.10 | Verification prediction               | OK     | Forecast prediction succeeded after recovery.                              |

### Drill Result

```text
DRILL RESULT: PASSED
```

---

## 5. What Worked

* The baseline prediction successfully passed before failure injection.
* The drill used the real `/models/batch-predict` API instead of directly invoking a test stub.
* The simulated serving failure propagated through the actual batch prediction path.
* The API correctly returned a failed prediction result.
* The failure contained the expected error:

```text
SIMULATED_MODEL_SERVING_FAILURE
```

* The `/models` endpoint remained available during the simulated incident.
* The known-good prediction path was restored successfully.
* A post-recovery prediction completed successfully.
* The drill verified the complete failure → containment → recovery flow.
* The `finally` block restored the original prediction function even if the drill encountered an unexpected error.

---

## 6. What Didn't Work / Gaps Found

### 6.1 Model health did not reflect the prediction failure

During the simulated failure, `/models/batch-predict` reported:

```text
success: false
error: SIMULATED_MODEL_SERVING_FAILURE
```

However, immediately afterward:

```text
GET /models
```

returned HTTP 200 and reported:

```text
forecast
production_version: v1
status: ready
```

This indicates that the current `/models` status represents model availability/loading state rather than real-time prediction health.

This is an important incident-drill finding.

### 6.2 No external alert was triggered

The drill detected the incident by executing:

```text
POST /models/batch-predict
```

There was no external alerting mechanism exercised by the drill.

Therefore, the current drill demonstrates API-level detection but does not yet demonstrate automated incident notification.

### 6.3 Containment is currently simulated

The current drill restores the original prediction function after failure injection.

This is safe for a local drill, but it is not yet a real blue-green deployment switch.

The next implementation should replace the temporary restoration with the actual blue-green/rollback mechanism.

---

## 7. Follow-ups

### 7.1 Connect Blue-Green Containment

Replace the temporary restoration:

```python
MULTI_MODEL_MANAGER.predict = original_predict
```

with the actual blue-green deployment switch once the mechanism is connected.

Target flow:

```text
Incident
   |
   v
Detection
   |
   v
Identify active deployment
   |
   v
Switch traffic to known-good deployment
   |
   v
Verify prediction
```

### 7.2 Improve Serving Health Status

Consider tracking recent prediction failures separately from model-loading status.

For example:

```text
Model loaded:        READY
Prediction health:   DEGRADED
Recent failures:     1
```

This would make `/models` more useful during an incident.

### 7.3 Add Automated Alerting

Add monitoring/alerting for repeated model-serving failures so an incident can be detected without requiring a manual prediction request.

### 7.4 Connect Rollback

Once model rollback is available through the serving layer, execute the rollback as part of the drill instead of restoring the Python function directly.

### 7.5 Repeat the Drill After Deployment Changes

Run this drill after changes to:

* Model serving
* Model registry
* Model promotion
* Rollback
* Blue-green deployment
* Monitoring
* Routing
* Incident handling

---

## 8. Current Drill Status

The end-to-end drill currently validates:

```text
Baseline
   ↓
Failure injection
   ↓
API-level detection
   ↓
Service inspection
   ↓
Temporary containment
   ↓
Recovery
   ↓
Verification
```

Current result:

```text
DRILL RESULT: PASSED
```

Known gap:

```text
/models reports the model as ready
even while prediction requests are failing.
```

The next improvement is to replace simulated containment with the actual blue-green/rollback mechanism.
