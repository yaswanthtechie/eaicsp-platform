# BentoML Serving – Milestone 1

## 1. Objective

The objective of Milestone 1 is to serve the reference Iris model with BentoML and prove that the packaged and containerized service produces the same prediction results as the existing reference service.

The validation covers:

* Request/response contract
* 100-input prediction parity
* Latency measurement
* BentoML build
* Container execution
* Integration testing

---

## 2. Existing Service

The project contains a BentoML `IrisService`.

The Iris prediction API accepts four numeric features:

```json
{
  "request": {
    "features": [5.1, 3.5, 1.4, 0.2]
  }
}
```

The prediction response contains:

```json
{
  "prediction": "setosa",
  "confidence": 1.0,
  "model_version": "local",
  "latency_ms": 14.82,
  "probabilities": {
    "setosa": 1.0,
    "versicolor": 0.0,
    "virginica": 0.0
  }
}
```

The existing `src/service.py` exposes `IrisService.predict()` through BentoML.

---

## 3. Milestone 1 Architecture

```text
                    100 deterministic inputs
                             |
                +------------+------------+
                |                         |
                v                         v
        Reference service          BentoML container
           port 3000                  port 3001
                |                         |
                +------------+------------+
                             |
                             v
                       Output comparison
                             |
                +------------+------------+
                |                         |
                v                         v
            Parity test             Latency test
```

The reference service runs on port `3000`.

The containerized BentoML service runs on port `3001`.

---

## 4. Parity Rules

The same 100 deterministic Iris inputs are sent to both services.

The following prediction outputs must match:

* `prediction`
* `confidence`
* `probabilities`
* probability class names and values

The `latency_ms` field is not compared because latency depends on runtime conditions.

The `model_version` field is also not used as a parity criterion because the container uses the bundled standalone model and may report `local`, while the reference service may use an MLflow model version.

Latency is measured separately.

---

## 5. BentoML Configuration

The BentoML service is defined using:

```text
src.service:IrisService
```

The Bento includes the standalone model artifact:

```text
models/model.pkl
```

The standalone model allows the containerized service to start without depending on a local MLflow model registry inside the container.

The BentoML package version used for validation is:

```text
bentoml==1.4.39
```

---

## 6. Build the Bento

The Bento was built successfully using:

```powershell
bentoml build
```

The successful Bento build generated:

```text
iris_service:zl6ru5v35sv2ofaw
```

The generated Bento can be verified with:

```powershell
bentoml list
```

---

## 7. Run the Reference Service

The reference service runs on port `3000`.

```powershell
bentoml serve src.service:IrisService --host 127.0.0.1 --port 3000
```

The service was verified successfully:

```powershell
Invoke-WebRequest http://127.0.0.1:3000
```

The service returned HTTP `200`.

---

## 8. Run the BentoML Container

The BentoML container was started on port `3001`.

```powershell
docker run --rm -p 3001:3000 iris_service:zl6ru5v35sv2ofaw
```

The container started successfully and BentoML reported:

```text
Service iris_service initialized
Starting production HTTP BentoServer
listening on http://localhost:3000
```

From the host machine, the container was verified using:

```powershell
Invoke-WebRequest http://127.0.0.1:3001
```

The container returned HTTP `200`.

---

## 9. 100-Input Parity Test

The parity test uses the same first 100 deterministic Iris samples for both services.

The automated integration test was executed using:

```powershell
python -m pytest tests\test_bentoml_parity.py -m integration -s -q
```

Result:

```text
============================================================
BentoML 100-Input Parity Test
============================================================
Total inputs       : 100
Prediction matches : 100/100
Prediction parity  : 100.00%
============================================================
.
1 passed, 2 deselected
```

### Parity Result

```text
Total inputs       : 100
Matched            : 100
Mismatched         : 0
Prediction parity  : 100.00%

PARITY: PASS
```

Therefore, all 100 test inputs produced matching prediction results between the reference service and the containerized BentoML service.

---

## 10. Pytest Verification

### Unit tests

The parity test file was executed without selecting only integration tests:

```powershell
python -m pytest tests\test_bentoml_parity.py -q
```

Result:

```text
3 passed, 1 warning in 5.60s
```

This includes:

* deterministic 100-input generation test
* prediction comparison test
* container-backed parity test

### Integration test

The integration test was executed separately:

```powershell
python -m pytest tests\test_bentoml_parity.py -m integration -s -q
```

Result:

```text
1 passed, 2 deselected
```

The integration test therefore successfully validated communication between the reference service and the running BentoML container.

---

## 11. Pytest Marker Warning

The test execution produced:

```text
PytestUnknownMarkWarning:
Unknown pytest.mark.integration
```

The integration test itself passed successfully.

The warning indicates that the custom `integration` marker has not yet been registered in `pytest.ini`.

Recommended configuration:

```ini
[pytest]
markers =
    integration: tests that require running services or containers
```

After adding this configuration, the `PytestUnknownMarkWarning` should no longer appear.

---

## 12. Standalone Parity Validation

A separate parity execution was also performed using the standalone parity script.

Result:

```text
BentoML 100-Input Parity Test
Total inputs       : 100
Prediction matches : 100/100
Prediction parity  : 100.00%
Bento avg latency  : 31.73 ms
Bento min latency  : 18.90 ms
Bento max latency  : 67.38 ms
PARITY RESULT      : PASS
```

These values represent the BentoML-side measurements from that execution.

---

## 13. Latency Comparison

The Milestone 1 requirement includes latency comparison between the reference service and the containerized BentoML service.

The current verified evidence records the BentoML latency values:

| Metric  |         Reference | BentoML Container |
| ------- | ----------------: | ----------------: |
| Average | Pending benchmark |          31.73 ms |
| Median  | Pending benchmark |           Pending |
| P95     | Pending benchmark |           Pending |
| Minimum | Pending benchmark |          18.90 ms |
| Maximum | Pending benchmark |          67.38 ms |

The reference-service latency values and BentoML median/P95 values should be populated from the dedicated benchmark execution rather than estimated.

---

## 14. Model Packaging

The container originally depended on an MLflow registry that was not available inside the newly created container.

To make the Bento independently runnable, the trained Iris model was saved as:

```text
models/model.pkl
```

The model is loaded by the serving layer when the bundled model is available.

This removes the dependency on a pre-existing MLflow registry inside the Bento container.

The generated Bento therefore starts successfully and serves predictions using the packaged model artifact.

---

## 15. Milestone 1 Result

The following Milestone 1 requirements have been verified:

* BentoML service builds successfully.
* BentoML service starts successfully.
* Docker container starts successfully.
* Container responds successfully on port `3001`.
* Reference service responds successfully on port `3000`.
* Both services accept the same 100 deterministic inputs.
* `100/100` predictions match.
* Prediction parity is `100.00%`.
* Unit tests pass.
* Container-backed integration test passes.
* BentoML standalone latency was measured.
* Model artifact is packaged with the Bento.

### Current Status

```text
BentoML Build       : PASS
Container Startup   : PASS
API Availability    : PASS
100-Input Parity    : PASS
Prediction Matches  : 100/100
Parity              : 100.00%
Unit Tests          : PASS
Integration Test    : PASS
Latency Measurement : PARTIAL
```

The remaining Milestone 1 evidence is the complete reference-vs-BentoML latency benchmark containing:

* Average
* Median
* P95
* Minimum
* Maximum

Once those measurements are recorded, Milestone 1 has complete documented evidence.
