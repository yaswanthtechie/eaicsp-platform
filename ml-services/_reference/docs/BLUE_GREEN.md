# Blue-Green Model Deployment

## 1. Objective

The objective of Blue-Green model deployment is to deploy a new model version without immediately replacing the currently active Production model.

The deployment process maintains two model versions:

* **Blue** - Current Production model version
* **Green** - Candidate model version

The candidate model can be configured and validated before receiving active traffic.

The deployment also integrates with model governance. A candidate version cannot receive Production traffic until the required governance approval is available.

If the candidate version fails after deployment, traffic can be switched back to the previous Production version.

---

## 2. Deployment Model

Blue represents the currently active Production model version.

Example:

```text
Blue = forecast v1
```

Blue continues to serve traffic while the new model version is being prepared and validated.

Green represents the candidate model version.

Example:

```text
Green = forecast v2
```

Green is prepared and validated before becoming the active deployment.

Only one deployment color is active at a time.

---

## 3. Blue-Green Architecture

The deployment maintains two model versions:

```text
                 Model Deployment
                       |
             +---------+---------+
             |                   |
          BLUE                 GREEN
       Production            Candidate
          v1                    v2
             |                   |
             +---------+---------+
                       |
                  Active Traffic
```

Only one deployment color is active at a time.

The inactive deployment remains available so that traffic can be switched back if required.

The deployment state identifies:

* Active color
* Active version
* Inactive color
* Inactive version
* Deployment status
* Switch timestamp

---

## 4. Deployment Workflow

The Blue-Green deployment follows these steps:

1. Blue is serving Production traffic.
2. A new model version is prepared as Green.
3. Green is configured.
4. Green is validated.
5. Governance approval is checked before Production promotion.
6. If governance approval is missing, the switch to Green is blocked.
7. After approval, traffic can be switched from Blue to Green.
8. Green becomes the active deployment.
9. Blue remains available as the previous Production version.
10. If Green fails, traffic can be switched back to Blue.
11. Blue resumes serving traffic.
12. A post-rollback prediction verifies recovery.

---

## 5. Initial State

Initially, the current Production model is assigned to Blue.

```text
Blue    = forecast v1
Green   = empty
Active  = Blue / forecast v1
```

Production traffic is served by forecast `v1`.

---

## 6. Candidate Deployment

When a new model version is available, it is assigned to Green.

```text
Blue    = forecast v1
Green   = forecast v2
Active  = Blue / forecast v1
```

At this point, Green is available but has not replaced the active Production deployment.

The existing Blue version remains available for Production traffic.

The actual demonstration configured:

```text
blue_version  = v1
green_version = v2
active_color  = blue
active_version = v1
status        = ready
```

The configuration request was:

```text
POST /models/forecast/blue-green
```

and returned HTTP `200`.

---

## 7. Green Validation

Before switching traffic to Green, the candidate model should be validated.

Validation includes:

* Model availability
* Model version verification
* Model health check
* Test prediction
* Prediction response validation
* Prediction latency check
* Basic resource verification

Green should only become active after successful validation and governance approval.

The demonstration first verified that Blue was serving successfully:

```text
POST /models/forecast/predict -> 200
```

with:

```text
model_version = v1
```

---

## 8. Governance Before Traffic Switch

Production traffic switching is protected by model governance.

A candidate model version without the required governance approval cannot be promoted to Production.

During the actual demonstration, an attempt was made to switch to Green before approval:

```text
POST /models/forecast/blue-green/switch/green -> 403
```

The service returned:

```text
Production promotion blocked: forecast version v2 does not have governance approval
(status=no governance request).
```

This confirms that an unapproved model cannot receive Production traffic through the Blue-Green switch.

---

## 9. Governance Approval

After the initial switch was correctly blocked, governance approval was provided for the candidate version.

The demonstration recorded:

```text
Governance:
requested by ajith
approved by team-lead
```

After approval, the same Blue-Green switch was allowed.

```text
POST /models/forecast/blue-green/switch/green -> 200
```

This demonstrates the required relationship between:

```text
Candidate Model
      |
      v
Governance Approval
      |
      v
Production Promotion
      |
      v
Blue-Green Traffic Switch
```

---

## 10. Traffic Switch

After successful validation and governance approval, traffic can be switched from Blue to Green.

Before the switch:

```text
Blue    = forecast v1
Green   = forecast v2
Active  = Blue / forecast v1
```

After the switch:

```text
Blue    = forecast v1
Green   = forecast v2
Active  = Green / forecast v2
```

The actual demonstration returned:

```json
{
    "model_name": "forecast",
    "blue_version": "v1",
    "green_version": "v2",
    "active_color": "green",
    "active_version": "v2",
    "inactive_color": "blue",
    "inactive_version": "v1",
    "status": "switched"
}
```

The switch request returned HTTP `200`.

---

## 11. Active Deployment

After the switch:

```text
Active Color   = Green
Active Version = forecast v2
```

Predictions routed through the Blue-Green deployment use forecast `v2`.

The actual demonstration verified:

```text
POST /models/forecast/predict -> 200
```

with:

```text
model_version = v2
```

This confirms that Production traffic was successfully moved to the Green deployment.

---

## 12. Rollback

If the Green version experiences a failure, traffic can be switched back to Blue.

Example incident:

```text
Active = Green / forecast v2

Green prediction failure

        |
        v

Rollback

        |
        v

Active = Blue / forecast v1
```

Blue resumes serving traffic.

The Green model remains available for investigation.

The actual demonstration successfully performed this rollback:

```text
POST /models/forecast/blue-green/switch/blue -> 200
```

The resulting deployment state was:

```text
Blue          = forecast v1
Green         = forecast v2
Active Color  = blue
Active Version = v1
Status        = switched
```

---

## 13. Rollback Procedure

If Green fails:

1. Identify the failure.
2. Confirm that Green is the active deployment.
3. Identify Blue as the known-good version.
4. Switch traffic back to Blue.
5. Verify Blue model health.
6. Send a test prediction.
7. Confirm successful prediction.
8. Verify prediction latency.
9. Monitor subsequent requests.
10. Investigate the failed Green version.

The actual demonstration verified the rollback by sending a prediction after switching back to Blue.

The final prediction returned:

```text
model_version = v1
prediction = successful
```

---

## 14. Deployment States

The Blue-Green deployment can have the following states.

### Configured

Blue and Green model versions have been configured.

Example:

```text
Blue  = v1
Green = v2
```

### Ready

Both model versions are available and ready for traffic switching.

Example:

```text
Active Color   = blue
Active Version = v1
Status         = ready
```

### Switched

Traffic has been switched from one deployment color to the other.

Example:

```text
Active Color   = green
Active Version = v2
Status         = switched
```

---

## 15. Deployment Safety

The Blue-Green deployment provides the following safety controls:

* The current Production version is not immediately replaced.
* The candidate model can be validated before switching traffic.
* Governance approval is required before Production promotion.
* An unapproved candidate switch is rejected with HTTP `403`.
* The previous Production version remains available.
* Traffic can be switched back if the candidate fails.
* Model versions are explicitly identified.
* The deployment does not require modification of model artifacts.
* Rollback does not require retraining the previous model.
* The deployment state identifies the currently active color.
* The active model version can be verified through prediction responses.

---

## 16. Validation Checklist

Before switching traffic to Green:

* [ ] Blue model is available
* [ ] Green model is available
* [ ] Green model version is correct
* [ ] Green model health check passes
* [ ] Green test prediction succeeds
* [ ] Green prediction response is valid
* [ ] Green latency is acceptable
* [ ] Blue remains available for rollback
* [ ] Governance approval for Green is available

The actual demonstration verified the governance gate by attempting the switch before approval and receiving HTTP `403`.

---

## 17. Post-Switch Verification

After switching traffic to Green, verify:

* [ ] Active color is Green
* [ ] Active version is Green model version
* [ ] Prediction succeeds
* [ ] Prediction response is valid
* [ ] Model health is healthy
* [ ] Prediction latency is acceptable
* [ ] No unexpected prediction errors occur

Actual demonstration:

```text
Active Color   : Green
Active Version : forecast v2
Prediction     : Successful
```

The prediction response confirmed:

```text
model_version = v2
```

---

## 18. Rollback Verification

After switching back to Blue, verify:

* [ ] Active color is Blue
* [ ] Active version is Blue model version
* [ ] Prediction succeeds
* [ ] Prediction response is valid
* [ ] Model health is healthy
* [ ] Prediction latency is acceptable

Actual demonstration:

```text
Active Color   : Blue
Active Version : forecast v1
Prediction     : Successful
```

The final prediction response confirmed:

```text
model_version = v1
```

---

## 19. Demonstration Procedure

The Blue-Green deployment was demonstrated using the following workflow.

### Step 1 - Configure deployment

```text
Blue  = forecast v1
Green = forecast v2
```

Expected:

```text
Active = Blue / forecast v1
```

Actual result:

```text
POST /models/forecast/blue-green -> 200
Status = ready
Active = Blue / forecast v1
```

### Step 2 - Verify Blue prediction

```text
POST /models/forecast/predict -> 200
```

Result:

```text
model_version = v1
Prediction = Successful
```

### Step 3 - Attempt switch without governance approval

```text
POST /models/forecast/blue-green/switch/green -> 403
```

Result:

```text
Production promotion blocked
```

This confirms the governance gate.

### Step 4 - Approve Green

Governance approval was recorded for forecast `v2`.

```text
Requested by = ajith
Approved by  = team-lead
```

### Step 5 - Switch to Green

```text
POST /models/forecast/blue-green/switch/green -> 200
```

Result:

```text
Active = Green / forecast v2
```

### Step 6 - Verify Green

```text
POST /models/forecast/predict -> 200
```

Result:

```text
model_version = v2
Prediction = Successful
```

### Step 7 - Rollback to Blue

```text
POST /models/forecast/blue-green/switch/blue -> 200
```

Result:

```text
Active = Blue / forecast v1
```

### Step 8 - Verify Blue

```text
POST /models/forecast/predict -> 200
```

Result:

```text
model_version = v1
Prediction = Successful
```

---

## 20. Demonstration Timeline

The actual demonstration followed this sequence:

```text
Initial
Blue  = forecast v1
Green = forecast v2
Active = Blue

        |
        v

Blue prediction
v1 -> Successful

        |
        v

Attempt Green switch
No governance approval
        |
        v
HTTP 403
Promotion blocked

        |
        v

Governance approval
requested by ajith
approved by team-lead

        |
        v

Switch Traffic
        |
        v

Active = Green / forecast v2

        |
        v

Green prediction
v2 -> Successful

        |
        v

Rollback
        |
        v

Active = Blue / forecast v1

        |
        v

Blue prediction
v1 -> Successful
```

---

## 21. Failure Scenario

Example:

```text
Production:
Blue  = forecast v1
Green = forecast v2
Active = Green
```

If forecast `v2` starts returning prediction errors:

```text
Green / v2
    |
    | Prediction failure
    v
Identify active deployment
    |
    v
Switch traffic to Blue
    |
    v
Blue / v1
```

After rollback:

```text
Blue  = forecast v1
Green = forecast v2
Active = Blue
```

The service can continue using the known-good model while the Green version is investigated.

The incident drill separately demonstrates this failure and containment path using the real Blue-Green switch endpoint.

---

## 22. Implementation Components

The Blue-Green deployment implementation consists of:

```text
src/blue_green.py
```

This module manages:

* Blue model version
* Green model version
* Active deployment color
* Deployment status
* Traffic switching
* Rollback
* Blue-Green predictions

The implementation uses the existing `ModelManager` to access registered model versions.

The serving layer exposes the Blue-Green functionality through the model API.

---

## 23. Blue-Green API Operations

The Blue-Green serving API provides the following operations.

### Configure

```text
POST /models/{model_name}/blue-green
```

Example:

```text
POST /models/forecast/blue-green
```

### Switch to Green

```text
POST /models/{model_name}/blue-green/switch/green
```

### Switch to Blue

```text
POST /models/{model_name}/blue-green/switch/blue
```

The Blue switch provides the rollback mechanism.

### Prediction

```text
POST /models/{model_name}/predict
```

### Model Status

```text
GET /models
```

These endpoints were exercised during the actual Blue-Green demonstration and incident drill.

---

## 24. Example Status

A Blue-Green deployment status can contain:

```json
{
    "model_name": "forecast",
    "blue_version": "v1",
    "green_version": "v2",
    "active_color": "green",
    "active_version": "v2",
    "inactive_color": "blue",
    "inactive_version": "v1",
    "status": "switched"
}
```

This makes it possible to identify which deployment is currently active.

---

## 25. Governance Behavior

Blue-Green Production promotion is integrated with model governance.

### Without approval

Attempting to promote an unapproved candidate:

```text
POST /models/forecast/blue-green/switch/green
```

returns:

```text
HTTP 403 Forbidden
```

with the reason:

```text
Production promotion blocked:
forecast version v2 does not have governance approval
```

### With approval

After the candidate receives governance approval:

```text
POST /models/forecast/blue-green/switch/green
```

returns:

```text
HTTP 200 OK
```

and Green becomes active.

This ensures that Blue-Green deployment does not bypass the model governance process.

---

## 26. Testing

The Blue-Green implementation should be tested for:

* Blue-Green configuration
* Initial Blue activation
* Green activation
* Governance-blocked Green activation
* Approved Green activation
* Green prediction
* Rollback to Blue
* Blue prediction after rollback
* Invalid deployment color
* Same Blue and Green version rejection
* Missing model version
* Deployment status

Run:

```powershell
python -m pytest -q tests/test_blue_green.py
```

Expected result:

```text
All Blue-Green tests pass.
```

The exact test count may change if additional Blue-Green tests are added.

---

## 27. Evidence

The following evidence was produced by the actual Blue-Green demonstration:

### 1. Blue-Green configuration

```text
POST /models/forecast/blue-green -> 200
```

```text
Blue  = v1
Green = v2
Active = Blue / v1
Status = ready
```

### 2. Initial Blue prediction

```text
POST /models/forecast/predict -> 200
model_version = v1
```

### 3. Governance protection

```text
POST /models/forecast/blue-green/switch/green -> 403
```

The switch was blocked because `v2` did not have governance approval.

### 4. Governance approval

```text
Requested by = ajith
Approved by  = team-lead
```

### 5. Switch from Blue to Green

```text
POST /models/forecast/blue-green/switch/green -> 200
```

```text
Active = Green / v2
```

### 6. Prediction using Green

```text
POST /models/forecast/predict -> 200
model_version = v2
```

### 7. Switch from Green back to Blue

```text
POST /models/forecast/blue-green/switch/blue -> 200
```

```text
Active = Blue / v1
```

### 8. Prediction using Blue

```text
POST /models/forecast/predict -> 200
model_version = v1
```

Evidence flow:

```text
Configure
    ->
Validate Blue
    ->
Governance Check
    ->
Block Unapproved Switch
    ->
Approve Candidate
    ->
Switch to Green
    ->
Test Green
    ->
Rollback to Blue
    ->
Test Blue
```

---

## 28. Completion Criteria

The Blue-Green deployment requirement is considered complete when:

* [x] Blue and Green model versions can be configured.
* [x] The candidate Green version can be validated.
* [x] Blue remains active while Green is being validated.
* [x] An unapproved Green promotion is blocked.
* [x] An approved Green version can be promoted.
* [x] Traffic can be switched from Blue to Green.
* [x] Green becomes the active deployment.
* [x] Predictions can be executed using the active Green version.
* [x] Traffic can be switched back from Green to Blue.
* [x] Blue successfully resumes serving predictions.
* [x] Deployment status identifies the active color and version.
* [x] The complete deployment and rollback flow has been demonstrated.

---

## 29. Summary

The Blue-Green deployment approach provides a controlled way to introduce a new model version while retaining the previous Production version for rollback.

The demonstrated deployment flow is:

```text
Current Production
       |
       v
     BLUE
      v1
       |
       | Candidate
       v
    GREEN
      v2
       |
       | Governance Check
       |
       +------ No approval ------> BLOCKED / 403
       |
       | Approved
       v
  Switch Traffic
       |
       v
   GREEN / v2
       |
       | Prediction
       v
    SUCCESS
       |
       | Failure / Rollback
       v
    BLUE / v1
       |
       v
    SUCCESS
```

The actual demonstration confirms:

```text
Unapproved Green switch -> 403 Forbidden
Approved Green switch   -> 200 OK
Green prediction        -> Successful
Rollback to Blue        -> 200 OK
Blue prediction         -> Successful
```

This demonstrates that the Blue-Green deployment provides:

* Controlled candidate promotion
* Governance protection
* Explicit active-version tracking
* Production traffic switching
* Safe rollback
* Post-rollback prediction verification
