# Incident Drill

## 1. Purpose

This document records an end-to-end incident drill for the unified ML serving layer.

The drill follows `docs/INCIDENT_RUNBOOK.md` through the real FastAPI serving API instead of directly testing an exception-throwing function.

The drill validates:

* Baseline model prediction
* Blue-green deployment configuration
* Failure injection
* Incident detection
* Model/service inspection
* Blue-green failure containment
* Service recovery
* Post-recovery verification

---

## 2. Drill Scenario

A simulated model-serving failure was injected into the forecast prediction path while forecast version `v2` was serving production traffic through the green deployment.

The objective was to verify that the serving layer could:

1. Successfully serve a prediction before the incident.
2. Configure a blue-green deployment with `v1` as blue and `v2` as green.
3. Switch production traffic to `v2`.
4. Detect a prediction failure through the real API.
5. Inspect the model-serving state.
6. Contain the failure by switching traffic back to `v1`.
7. Verify successful predictions after recovery.

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
POST /models/forecast/blue-green
POST /models/forecast/blue-green/switch/green
GET  /models
POST /models/forecast/blue-green/switch/blue
```

The forecast model was used for the prediction request.

The blue-green deployment was configured as:

```text
Blue  = v1
Green = v2
```

Production traffic was first switched to `v2` to reproduce the failure and was then switched back to `v1` for containment and recovery.

---

## 4. Timeline

The following timeline is based on the actual output from the incident drill.

| t (s) | Step                                  | Result | Detail                                                                                                                 |
| ----: | ------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------- |
|  0.04 | Baseline prediction                   | OK     | Forecast `v1` prediction completed successfully.                                                                       |
|  0.05 | Configure blue=`v1`, green=`v2`       | OK     | Blue-green deployment configured with `v1` active and `v2` inactive.                                                   |
|  0.08 | Deploy: switch to green (`v2`)        | OK     | Production traffic switched from `v1` to `v2`.                                                                         |
|  0.09 | Detection via `/models/batch-predict` | OK     | Prediction failed while `v2` was active. The API returned `success: false` with the generic error `prediction failed`. |
|  0.10 | Runbook detection: `GET /models`      | OK     | `/models` reported forecast `v2` as the live version with `status: ready`.                                             |
|  0.11 | Containment: switch blue (`v1`)       | OK     | Traffic was switched back to the known-good blue deployment, `v1`.                                                     |
|  0.12 | Verification prediction               | OK     | Forecast prediction succeeded after traffic was switched back to `v1`.                                                 |

### Actual Drill Result

```text
DRILL RESULT: PASSED
```

### Actual Drill Output

The command produced the following relevant execution sequence:

```text
POST /models/batch-predict -> 200 OK
POST /models/forecast/blue-green -> 200 OK
POST /models/forecast/blue-green/switch/green -> 200 OK
POST /models/batch-predict -> 200 OK
GET /models -> 200 OK
POST /models/forecast/blue-green/switch/blue -> 200 OK
POST /models/batch-predict -> 200 OK
```

The injected failure was logged as:

```text
RuntimeError: SIMULATED_MODEL_SERVING_FAILURE
```

The API response intentionally exposed only:

```text
error: prediction failed
```

The underlying failure details were available in the application logs.

---

## 5. What Worked

* The baseline prediction successfully passed before failure injection.
* The drill used the real `/models/batch-predict` API instead of directly invoking a test stub.
* The blue-green deployment was configured through the real serving API.
* Production traffic was successfully switched from `v1` to `v2`.
* The simulated serving failure propagated through the actual batch prediction path.
* The API correctly returned a failed prediction result.
* The `/models` endpoint remained available during the simulated incident.
* `/models` identified `v2` as the live forecast version while the prediction failure was occurring.
* Containment used the real blue-green switch endpoint.
* Production traffic was successfully switched back from `v2` to the known-good `v1`.
* A post-containment prediction completed successfully.
* The drill verified the complete failure → detection → containment → recovery flow.
* The `finally` block restored the original prediction function even if the drill encountered an unexpected error.

---

## 6. What Didn't Work / Gaps Found

### 6.1 Model health did not reflect the prediction failure

During the simulated failure, `/models/batch-predict` reported:

```text
success: false
error: prediction failed
```

However, immediately afterward:

```text
GET /models
```

returned HTTP 200 and reported the forecast model as:

```text
production_version: v2
status: ready
```

This indicates that the current `/models` status represents model availability/loading state rather than real-time prediction health.

However, the live model version is now visible as `v2`, which helps identify the deployment associated with the failed predictions.

This remains an important incident-drill finding.

### 6.2 No external alert was triggered

The drill detected the incident by executing:

```text
POST /models/batch-predict
```

There was no external alerting mechanism exercised by the drill.

Therefore, the current drill demonstrates API-level detection but does not yet demonstrate automated incident notification.

### 6.3 Containment used the real blue-green switch

Containment is no longer simulated.

The drill used:

```text
POST /models/forecast/blue-green/switch/blue
```

Production traffic was moved back to `v1` while `v2` was still broken.

The subsequent verification prediction succeeded through `v1`.

This demonstrates real blue-green containment through the serving API.

### 6.4 Root-cause details require application logs

The prediction API intentionally returns the generic error:

```text
prediction failed
```

The underlying exception is not exposed through the API response.

This is appropriate for avoiding unnecessary internal error details in client-facing responses, but it means operators must check the application/model-serving logs to determine the actual root cause.

During this drill, the application logs contained:

```text
RuntimeError: SIMULATED_MODEL_SERVING_FAILURE
```

The incident runbook should therefore direct operators to check application/model-serving logs after detecting a prediction failure.

---

## 7. Follow-ups

### 7.1 Connect Blue-Green Containment

**Status: DONE**

The drill now uses the actual blue-green deployment mechanism for containment.

The implemented flow is:

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

The actual containment request was:

```text
POST /models/forecast/blue-green/switch/blue
```

Traffic was successfully moved back to `v1`.

### 7.2 Improve Serving Health Status

**Status: OPEN**

Consider tracking recent prediction failures separately from model-loading status.

For example:

```text
Model loaded:        READY
Prediction health:   DEGRADED
Recent failures:     1
```

This would make `/models` more useful during an incident.

Currently, the endpoint can report:

```text
status: ready
```

even when prediction requests are failing.

### 7.3 Add Automated Alerting

**Status: OPEN**

Add monitoring/alerting for repeated model-serving failures so an incident can be detected without requiring a manual prediction request.

### 7.4 Connect Rollback

**Status: DONE**

The incident drill now demonstrates traffic recovery using the real blue-green deployment mechanism.

The drill switches traffic from the failing `v2` deployment back to the known-good `v1` deployment:

```text
POST /models/forecast/blue-green/switch/blue
```

The subsequent prediction succeeds using `v1`.

### 7.5 Repeat the Drill After Deployment Changes

**Status: ONGOING**

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
Blue-green configuration
   ↓
Traffic switched to v2
   ↓
Failure injection
   ↓
API-level detection
   ↓
Service inspection
   ↓
Blue-green containment
   ↓
Traffic switched back to v1
   ↓
Recovery
   ↓
Verification
```

Current result:

```text
DRILL RESULT: PASSED
```

### Remaining Gaps

```text
1. /models reports the model as ready even while prediction requests
   are failing.

2. No automated external alerting is exercised by the drill.

3. The prediction API returns only "prediction failed"; operators
   must check application/model-serving logs for the underlying
   failure cause.
```

The blue-green containment flow is now demonstrated through the real serving API rather than simulated restoration.
