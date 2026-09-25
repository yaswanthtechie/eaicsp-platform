# Model Serving Incident Response Runbook

## Purpose

This runbook defines the response procedure for failures in the unified ML serving layer.

It covers detection, containment, diagnosis, recovery, verification, closure, and incident drills.

The objective is to restore model-serving functionality safely while minimizing production impact.

---

## 1. Incident Symptoms

A model-serving incident may include:

* Prediction requests returning errors
* Increased prediction latency
* Unhealthy model status
* Model loading failures
* Unexpected model version being served
* Increased failed requests
* CPU or memory exhaustion
* Production prediction failures

---

## 2. Detection

When an issue is reported, first check model health:

```text
GET /models
```

Review:

* Model name
* Current production version
* Model health/readiness
* Loading status
* Reported errors

Check application and serving logs for:

* HTTP 4xx/5xx errors
* Model loading exceptions
* Prediction exceptions
* Timeout errors
* Increased failure rate
* First failure time

Check resource usage:

```text
resource_metrics
```

Review CPU, memory, latency, and resource-related failures.

Record:

* Incident start time
* Affected model
* Current version
* Error message
* Error rate
* First failure time
* Resource metrics

---

## 3. Containment

The first priority is to prevent further production impact.

Identify the failing model and version using:

```text
GET /models
```

Check logs for the exact error and failure rate.

### Blue-Green Deployment

If Blue-Green deployment exists, switch to the known-good Blue version:

```text
POST /models/<model>/blue-green/switch/blue
```

Verify that production traffic is using the known-good version.

### Registry Rollback

If Blue-Green is unavailable, roll back the registry alias:

```python
rollback_model("<model>")
```

The rollback must restore the previously known-good production version.

Record:

```text
Incident detected:
Containment started:
Containment completed:
Affected model:
Failed version:
Restored version:
```

---

## 4. Diagnosis

After containment, identify the root cause.

Check whether a new version was recently promoted.

Review:

* Governance records
* Approval records
* MLflow model versions
* MLflow aliases
* Promotion history
* Deployment history

Determine whether the failure is:

### Model Loading Failure

Examples:

* Missing/corrupted artifact
* Dependency mismatch
* Model initialization failure
* Incorrect model path
* Registry loading failure

### Bad Input

Examples:

* Missing fields
* Incorrect data types
* Invalid feature values
* Schema validation failure
* Unexpected input format

### Resource Exhaustion

Check:

```text
resource_metrics
```

Look for high CPU/memory usage, resource spikes, latency, and timeouts.

Record the exact:

* Error
* Model name
* Model version
* Request type
* First failure time
* Failure frequency
* Relevant log entry
* Resource metrics

---

## 5. Recovery

Choose either rollback or fix-forward.

### Stay Rolled Back

Remain on the known-good version when the new version is faulty, the root cause is unresolved, or no safe replacement exists.

### Fix Forward

Follow the normal lifecycle:

```text
Create/Fix Model
      ↓
Train/Retrain
      ↓
Evaluate Candidate
      ↓
Governance Approval
      ↓
Register Model
      ↓
Promote Approved Version
      ↓
Verify Production
```

Never promote a hotfix directly to Production without governance approval.

---

## 6. Verification

After rollback or recovery:

```text
GET /models
```

Verify:

* Model is healthy
* Expected version is active
* Model is ready
* No loading errors exist

Send a known-good prediction payload and verify:

* Request succeeds
* Valid prediction is returned
* Expected model version is serving
* No unexpected errors occur

Monitor logs and metrics.

The error rate must return to baseline and remain stable for at least:

```text
15 minutes
```

Verification criteria:

```text
GET /models → Healthy
Known-good payload → Successful
Production version → Expected
Error rate → Baseline
Monitoring → 15 minutes minimum
```

---

## 7. Closure

After successful verification, create an incident note containing:

* Incident date/time
* Detection time
* Affected model/version
* First failure time
* Error rate/message
* Root cause
* Containment action
* Rollback/recovery action
* Recovery time
* Verification results
* What worked
* What did not work
* Follow-up actions

Maintain the timeline:

```text
Detection
   ↓
Failure Identified
   ↓
Containment
   ↓
Root Cause Identified
   ↓
Recovery
   ↓
Verification
   ↓
15-Minute Monitoring
   ↓
Closure
```

---

## 8. Incident Drill

Detailed drill instructions are maintained in:

```text
INCIDENT_DRILL.md
```

The drill must follow Sections 2 through 6:

```text
Detection
   ↓
Containment
   ↓
Diagnosis
   ↓
Recovery
   ↓
Verification
```

Record:

```text
Detection time:
Containment time:
Diagnosis time:
Recovery time:
Verification time:
Total drill duration:
```

Drill evidence must include the affected model, simulated failure, error, containment action, recovery action, model health, successful prediction, error-rate verification, and timings.

---

## 9. Quick Response Checklist

```text
[ ] Check GET /models
[ ] Identify failing model/version
[ ] Check logs and error rate
[ ] Record first failure time
[ ] Check resource_metrics
[ ] Check governance and MLflow records
[ ] Determine failure type
[ ] Switch Blue-Green to Blue if available
[ ] Otherwise rollback registry alias
[ ] Record containment time
[ ] Decide rollback or fix-forward
[ ] Obtain governance approval
[ ] Promote approved version if required
[ ] Check GET /models
[ ] Send known-good payload
[ ] Verify expected version
[ ] Monitor for 15 minutes
[ ] Record incident timeline
[ ] Document root cause
[ ] Record follow-up actions
[ ] Close incident
```

---

## 10. Safety Rules

1. Contain production impact first.
2. Identify the exact model and version.
3. Preserve the original error details.
4. Use a known-good version for rollback when required.
5. Never promote an unapproved hotfix.
6. Follow model governance for production promotion.
7. Verify health after rollback or promotion.
8. Use a known-good payload for verification.
9. Monitor for at least 15 minutes after recovery.
10. Record the complete incident timeline.
11. Document follow-up actions.
12. Do not close the incident until recovery is verified.
