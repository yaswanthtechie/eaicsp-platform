Blue-Green Model Deployment

1. Objective

The objective of Blue-Green model deployment is to deploy a new model version without immediately replacing the currently active Production model.

The deployment process maintains two model versions:
- Blue - Current Production model version
- Green - Candidate model version

The candidate model can be validated before receiving active traffic. If the candidate version fails after deployment, traffic can be switched back to the previous Production version.

2. Deployment Model

Blue represents the currently active Production model version.

Example:
Blue = forecast v1

Blue continues to serve traffic while the new model version is being prepared and validated.

Green represents the candidate model version.

Example:
Green = forecast v2

Green is prepared and validated before becoming the active deployment.

3. Blue-Green Architecture

The deployment maintains two model versions:

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

Only one deployment color is active at a time.

The inactive deployment remains available so that traffic can be switched back if required.

4. Deployment Workflow

The Blue-Green deployment follows these steps:

1. Blue is serving Production traffic.
2. A new model version is prepared as Green.
3. Green is validated.
4. If validation succeeds, traffic is switched to Green.
5. Green becomes the active deployment.
6. Blue remains available as the previous Production version.
7. If Green fails, traffic is switched back to Blue.
8. Blue resumes serving traffic.

5. Initial State

Initially, the current Production model is assigned to Blue.

Blue    = forecast v1
Green   = empty
Active  = Blue / forecast v1

The Production traffic is served by forecast v1.

6. Candidate Deployment

When a new model version is available, it is assigned to Green.

Blue    = forecast v1
Green   = forecast v2
Active  = Blue / forecast v1

At this point, Green is available but has not replaced the active Production deployment.

The existing Blue version remains available for Production traffic.

7. Green Validation

Before switching traffic to Green, the candidate model should be validated.

Validation includes:
- Model availability
- Model version verification
- Model health check
- Test prediction
- Prediction response validation
- Prediction latency check
- Basic resource verification

Green should only become active after successful validation.

8. Traffic Switch

After successful validation, traffic can be switched from Blue to Green.

Before the switch:
Blue    = forecast v1
Green   = forecast v2
Active  = Blue / forecast v1

After the switch:
Blue    = forecast v1
Green   = forecast v2
Active  = Green / forecast v2

Green is now serving the active traffic.

Blue remains available as the previous Production version.

9. Active Deployment

After the switch:

Active Color   = Green
Active Version = forecast v2

Predictions routed through the Blue-Green deployment use forecast v2.

The deployment status identifies:
- Active color
- Active version
- Inactive color
- Inactive version
- Deployment status
- Switch time

10. Rollback

If the Green version experiences a failure, traffic can be switched back to Blue.

Example incident:
Active = Green / forecast v2

Green prediction failure

Rollback:
Blue    = forecast v1
Green   = forecast v2
Active  = Blue / forecast v1

Blue resumes serving traffic.

The Green model remains available for investigation.

11. Rollback Procedure

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

12. Deployment States

The Blue-Green deployment can have the following states.

Configured:
Blue and Green model versions have been configured.

Example:
Blue  = v1
Green = v2

Ready:
Both model versions are available and ready for traffic switching.

Switched:
Traffic has been switched from one deployment color to the other.

Example:
Active = Green

13. Deployment Safety

The Blue-Green deployment provides the following safety controls:
- The current Production version is not immediately replaced.
- The candidate model is validated before switching traffic.
- The previous Production version remains available.
- Traffic can be switched back if the candidate fails.
- Model versions are explicitly identified.
- The deployment does not require modification of model artifacts.
- Rollback does not require retraining the previous model.
- The deployment state identifies the currently active color.

14. Validation Checklist

Before switching traffic to Green:

[ ] Blue model is available
[ ] Green model is available
[ ] Green model version is correct
[ ] Green model health check passes
[ ] Green test prediction succeeds
[ ] Green prediction response is valid
[ ] Green latency is acceptable
[ ] Blue remains available for rollback

15. Post-Switch Verification

After switching traffic to Green, verify:

[ ] Active color is Green
[ ] Active version is Green model version
[ ] Prediction succeeds
[ ] Prediction response is valid
[ ] Model health is healthy
[ ] Prediction latency is acceptable
[ ] No unexpected prediction errors occur

Example:
Active Color   : Green
Active Version : forecast v2
Health         : Healthy
Prediction     : Successful

16. Rollback Verification

After switching back to Blue, verify:

[ ] Active color is Blue
[ ] Active version is Blue model version
[ ] Prediction succeeds
[ ] Prediction response is valid
[ ] Model health is healthy
[ ] Prediction latency is acceptable

Example:
Active Color   : Blue
Active Version : forecast v1
Health         : Healthy
Prediction     : Successful

17. Demonstration Procedure

The Blue-Green deployment should be demonstrated using the following workflow.

Step 1 - Configure deployment
Blue  = forecast v1
Green = forecast v2
Expected:
Active = Blue / forecast v1

Step 2 - Validate Green
Verify that forecast v2 is available and can successfully execute a test prediction.

Step 3 - Switch to Green
Active = Green / forecast v2

Step 4 - Verify Green
Run a prediction and verify:
Deployment Color = Green
Model Version    = v2
Prediction       = Successful

Step 5 - Rollback to Blue
Active = Blue / forecast v1

Step 6 - Verify Blue
Run another prediction and verify:
Deployment Color = Blue
Model Version    = v1
Prediction       = Successful

18. Example Deployment Timeline

Initial
Blue  = forecast v1
Green = empty
Active = Blue

Candidate prepared
Blue  = forecast v1
Green = forecast v2
Active = Blue

Green validated
Blue  = forecast v1
Green = forecast v2
Active = Blue
Green = VALIDATED

Traffic switched
Blue  = forecast v1
Green = forecast v2
Active = Green

Rollback
Blue  = forecast v1
Green = forecast v2
Active = Blue

19. Failure Scenario

Example:

Production:
Blue  = forecast v1
Green = forecast v2
Active = Green

If forecast v2 starts returning prediction errors:

Green / v2
    |
    | Prediction failure
    v
Rollback
    |
    v
Blue / v1

After rollback:
Blue  = forecast v1
Green = forecast v2
Active = Blue

The service can continue using the known-good model while the Green version is investigated.

20. Implementation Components

The Blue-Green deployment implementation consists of:

src/blue_green.py

This module manages:
- Blue model version
- Green model version
- Active deployment color
- Deployment status
- Traffic switching
- Rollback
- Blue-Green predictions

The implementation uses the existing ModelManager to access registered model versions.

21. Blue-Green Manager Operations

The Blue-Green manager provides the following operations.

Configure:
configure(model_name, blue_version, green_version)

Status:
status(model_name)

Predict:
predict(model_name, payload)

Switch to Green:
switch_to_green(model_name)

Switch to Blue:
switch_to_blue(model_name)

Switching to Blue provides the rollback mechanism.

22. Example Status

A Blue-Green deployment status can contain:

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

This makes it possible to identify which deployment is currently active.

23. Testing

The Blue-Green implementation should be tested for:
- Blue-Green configuration
- Initial Blue activation
- Green activation
- Green prediction
- Rollback to Blue
- Invalid deployment color
- Same Blue and Green version rejection
- Missing model version
- Deployment status

Run:
python -m pytest -q tests/test_blue_green.py

Expected result:
7 passed

The exact test count may change if additional Blue-Green tests are added.

24. Evidence

The following evidence should be retained:
1. Blue-Green configuration result
2. Initial Blue status
3. Green validation result
4. Switch from Blue to Green
5. Prediction using Green
6. Switch from Green back to Blue
7. Prediction using Blue
8. Blue-Green test results

Evidence flow:
Configure -> Validate Green -> Switch to Green -> Test Prediction -> Rollback -> Test Prediction

25. Completion Criteria

The Blue-Green deployment requirement is considered complete when:
- Blue and Green model versions can be configured.
- The candidate Green version can be validated.
- Blue remains active while Green is being validated.
- Traffic can be switched from Blue to Green.
- Green becomes the active deployment.
- Predictions can be executed using the active Green version.
- Traffic can be switched back from Green to Blue.
- Blue successfully resumes serving predictions.
- Deployment status identifies the active color and version.
- Blue-Green tests pass.
- The complete deployment and rollback flow is demonstrated.

26. Summary

The Blue-Green deployment approach provides a controlled way to introduce a new model version.

The deployment flow is:

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
       | Validate
       v
  Switch Traffic
       |
       v
   GREEN / v2
       |
       | Failure
       v
    Rollback
       |
       v
    BLUE / v1

This allows a candidate model version to be validated before becoming active and provides a direct rollback path to the previous Production version.