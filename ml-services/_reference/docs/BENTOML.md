BentoML Serving -- Milestone 1

1. Objective

The objective of Milestone 1 is to serve the reference Iris model with
BentoML and prove that the packaged and containerized service produces
the same prediction results as the existing reference service.

The validation covers:

Request/response contract

100-input prediction parity

Latency measurement

BentoML build

Container execution

Integration testing

2. Existing Service

The project contains a BentoML IrisService.

The Iris prediction API accepts four numeric features:

{
  "request": {
    "features": [5.1, 3.5, 1.4, 0.2]
  }
}

The prediction response contains:

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

The existing src/service.py exposes IrisService.predict() through
BentoML.

3. Milestone 1 Architecture

                    100 deterministic inputs

                             |
                +------------+------------+
                |                         |
                v                         v
        Reference service          BentoML container
           port 3000                   port 3001
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

The reference service runs on port 3000.

The containerized BentoML service runs on port 3001.

4. Parity Rules

The same 100 deterministic Iris inputs are sent to both services.

The following prediction outputs must match:

prediction

confidence

probabilities

probability class names and values

The latency_ms field is not compared because latency depends on
runtime conditions.

The model_version field is also not used as a parity criterion because
the container uses the bundled standalone model and may report local,
while the reference service may use an MLflow model version.

Latency is measured separately.

5. BentoML Configuration

The BentoML service is defined using:

src.service:IrisService

The Bento includes the standalone model artifact:

models/model.pkl

The standalone model allows the containerized service to start without
depending on a local MLflow model registry inside the container.

The BentoML package version used for validation is:

bentoml==1.4.39

6. Build the Bento

The Bento was built successfully using:

bentoml build

The successful Bento build generated:

iris_service:zl6ru5v35sv2ofaw

The generated Bento can be verified with:

bentoml list

The Docker image used for the final container validation was:

iris-ml-service:round12-13

7. Run the Reference Service

The reference service runs on port 3000.

bentoml serve src.service:IrisService --host 127.0.0.1 --port 3000

The service was verified successfully:

Invoke-WebRequest http://127.0.0.1:3000

The service returned HTTP 200.

8. Run the BentoML Container

The BentoML container was started on port 3001.

docker run --rm -p 3001:3000 iris-ml-service:round12-13

The container started successfully and BentoML reported:

Service iris_service initialized

Starting production HTTP BentoServer

listening on http://localhost:3000

From the host machine, the container was verified using:

Invoke-WebRequest http://127.0.0.1:3001

The container returned HTTP 200.

The Docker image explicitly enables bundled-model mode:

BENTO_BUNDLED_MODEL=true

and loads the packaged:

/app/models/model.pkl

This keeps the container independent of an MLflow @production alias
while leaving normal MLflow governance and promotion behavior unchanged.

9. 100-Input Parity Test

The parity test uses 100 deterministic Iris samples for both services.

The automated integration test was executed using:

python -m pytest tests\test_bentoml_parity.py -m integration -s -q

Result:

============================================================
BentoML 100-Input Parity Test
============================================================

Total inputs       : 100

Prediction matches : 100/100

Prediction parity  : 100.00%
============================================================

1 passed, 2 deselected

Parity Result

Total inputs       : 100
Matched            : 100
Mismatched         : 0
Prediction parity  : 100.00%

PARITY: PASS

Therefore, all 100 test inputs produced matching prediction results
between the reference service and the containerized BentoML service.

10. Pytest Verification

Unit tests

The parity test file was executed without selecting only integration
tests:

python -m pytest tests\test_bentoml_parity.py -q

The current test file includes:

deterministic 100-input generation test

prediction comparison test

container-backed parity test

parity-input class coverage test

latency summary test

The integration test is deselected by default through pytest.ini.

Integration test

The integration test was executed separately:

python -m pytest tests\test_bentoml_parity.py -m integration -s -q

Result:

1 passed, 2 deselected

The integration test successfully validated communication between the
reference service and the running BentoML container.

11. Pytest Marker Configuration

The custom integration marker is registered in pytest.ini:

[pytest]
markers =
    integration: tests that require running services or containers
addopts = -m "not integration"

Therefore, integration tests are excluded from the normal test suite and
can be explicitly selected when both services are running.

12. Standalone Parity Validation

A separate parity execution was also performed using the standalone
parity script.

The deterministic input set contains 100 Iris samples and covers all
three Iris classes.

The final benchmark also confirmed:

Parity: 100/100

The standalone parity script measures client-side round-trip latency for
the BentoML service. The dedicated benchmark in Section 13 provides the
final reference-vs-BentoML comparison.

13. Latency Comparison

The dedicated benchmark was executed with both services running:

python -m scripts.bentoml_benchmark

The benchmark used the same deterministic 100 inputs for the reference
and BentoML services.

Benchmark Result

Parity: 100/100
| Server | mean | p50 | p95 | min | max |
|---|---:|---:|---:|---:|---:|
| reference | 27.07 | 24.76 | 41.42 | 14.94 | 95.01 |
| bentoml | 27.38 | 24.78 | 45.58 | 16.42 | 82.43 |

Latency Table

Metric           Reference   BentoML Container

Average           27.07 ms            27.38 ms
Median (P50)      24.76 ms            24.78 ms
P95               41.42 ms            45.58 ms
Minimum           14.94 ms            16.42 ms
Maximum           95.01 ms            82.43 ms

Benchmark Result

Total inputs       : 100
Prediction matches : 100/100
Prediction parity  : 100.00%

Reference mean     : 27.07 ms
BentoML mean       : 27.38 ms

Reference P50      : 24.76 ms
BentoML P50        : 24.78 ms

Reference P95      : 41.42 ms
BentoML P95        : 45.58 ms

Reference min      : 14.94 ms
BentoML min        : 16.42 ms

Reference max      : 95.01 ms
BentoML max        : 82.43 ms

The benchmark uses client-side round-trip latency measurements for 100
requests.

14. Model Packaging

The container originally depended on an MLflow registry that was not
available inside the newly created container.

To make the Bento independently runnable, the trained Iris model was
saved as:

models/model.pkl

The serving layer loads this standalone model when
BENTO_BUNDLED_MODEL=true.

This removes the dependency on a pre-existing MLflow registry inside the
Bento container.

The generated container therefore starts successfully and serves
predictions using the packaged model artifact.

MLflow governance is not bypassed by this behavior. Normal local/MLflow
serving continues to use the @production alias, while the packaged
Bento uses the explicitly bundled model.

15. Milestone 1 Result

The following Milestone 1 requirements have been verified:

BentoML service builds successfully.

BentoML service starts successfully.

Docker container starts successfully.

Container responds successfully on port 3001.

Reference service responds successfully on port 3000.

Both services accept the same 100 deterministic inputs.

100/100 predictions match.

Prediction parity is 100.00%.

Unit tests pass.

Container-backed integration test passes.

Reference and BentoML latency were measured using the dedicated
benchmark.

Model artifact is packaged with the container.

Final Status

BentoML Build       : PASS
Container Startup   : PASS
API Availability    : PASS
100-Input Parity    : PASS
Prediction Matches  : 100/100
Parity              : 100.00%
Unit Tests          : PASS
Integration Test    : PASS
Latency Measurement : PASS