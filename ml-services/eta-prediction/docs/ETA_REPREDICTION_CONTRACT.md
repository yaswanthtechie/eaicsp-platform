# ETA Re-Prediction Contract

## 1. Purpose

This document defines the contract for a future Logistics-to-ETA integration when a shipment status changes.

The purpose is to define how Logistics will provide shipment context and a status-change event to the ETA service so that an updated ETA can eventually be requested in a consistent and production-ready way.

## 2. Scope

### In Scope

- Define the request contract for a shipment status-change event.
- Define the response contract for an ETA prediction.
- Define required validation rules.
- Define event identity and idempotency expectations.
- Define error semantics.
- Define observability requirements.
- Define integration decisions that must be agreed with Logistics before implementation.

## 3. Existing ETA Prediction Contract

The existing ETA prediction interface accepts the following request:

    {
      "origin": "sao paulo",
      "destination": "rio de janeiro",
      "carrier": "carrier-x",
      "weight_kg": 2.5
    }

The existing prediction response is:

    {
      "eta_days": 5.2,
      "confidence_low": 4.1,
      "confidence_high": 7.3
    }

The future Logistics integration should preserve these prediction fields so that the existing ETA prediction semantics remain consistent.

## 4. Proposed Status-Change Re-Prediction Request

When a meaningful shipment status transition occurs, Logistics will eventually provide a request containing the shipment identity, status-change event, and shipment information required by the ETA service.

### Request

    {
      "shipment_id": "SHIP-12345",
      "event_id": "EVENT-98765",
      "status": "<canonical_shipment_status>",
      "status_changed_at": "2026-10-07T09:30:00Z",
      "origin": "sao paulo",
      "destination": "rio de janeiro",
      "carrier": "carrier-x",
      "weight_kg": 2.5
    }

### Required Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `shipment_id` | string | Yes | Unique identifier of the shipment. |
| `event_id` | string | Yes | Unique identifier of the status-change event. Used for event tracking and idempotency. |
| `status` | string | Yes | Canonical shipment status supplied by Logistics. The exact status enumeration must be agreed with Logistics. |
| `status_changed_at` | string | Yes | Timestamp at which the shipment status changed. ISO-8601 UTC format is proposed. |
| `origin` | string | Yes | Shipment origin city. |
| `destination` | string | Yes | Shipment destination city. |
| `carrier` | string | Yes | Carrier associated with the shipment. |
| `weight_kg` | number | Yes | Shipment weight in kilograms. Must be finite and non-negative. |

## 5. Proposed Response

The ETA service will return the shipment identifier together with the ETA prediction.

    {
      "shipment_id": "SHIP-12345",
      "eta_days": 5.2,
      "confidence_low": 4.1,
      "confidence_high": 7.3
    }

### Response Fields

| Field | Type | Description |
|---|---|---|
| `shipment_id` | string | Shipment identifier supplied in the request. |
| `eta_days` | number | ETA prediction in days. |
| `confidence_low` | number | Lower bound of the prediction interval in days. |
| `confidence_high` | number | Upper bound of the prediction interval in days. |

The response must satisfy:

    confidence_low <= confidence_high

The point prediction is not required to fall inside the prediction interval because the existing ETA implementation uses an independently calibrated empirical prediction interval.

## 6. Status-Change Trigger

The future integration is intended to be triggered by a **meaningful shipment status transition** detected by Logistics.

The exact canonical status values and the list of statuses that trigger ETA re-prediction must be agreed with the Logistics service before implementation.

The ETA service must not independently invent or assume Logistics status values.

### Expected Flow

    Shipment status changes
            |
            v
    Logistics detects the status transition
            |
            v
    Logistics creates the status-change event
            |
            v
    Logistics sends the ETA re-prediction request
            |
            v
    ETA service validates the request
            |
            v
    ETA service generates the ETA prediction
            |
            v
    ETA service returns the prediction
            |
            v
    Logistics consumes the updated ETA

## 7. Validation Requirements

The future integration must validate the request before prediction.

### Shipment Identity

- `shipment_id` must be present.
- `shipment_id` must not be empty.
- `event_id` must be present.
- `event_id` must not be empty.

### Status

- `status` must be present.
- `status` must use the canonical status vocabulary agreed with Logistics.
- Unsupported status values must be rejected.

### Timestamp

- `status_changed_at` must be present.
- The timestamp must use the agreed ISO-8601 UTC representation.
- Invalid timestamps must be rejected.

### Location

- `origin` must be a non-empty city name.
- `destination` must be a non-empty city name.
- Cities must be resolvable using the ETA service's supported geographic data.

### Shipment Weight

- `weight_kg` must be numeric.
- `weight_kg` must be finite.
- `weight_kg` must be greater than or equal to zero.

## 8. Idempotency

Status-change events must be processed idempotently.

`event_id` is the preferred unique identifier for a status-change event.

If the same event is delivered more than once, the integration should not create conflicting duplicate ETA updates.

The final idempotency mechanism and storage responsibility must be agreed between Logistics and ETA before implementation.

## 9. Error Semantics

The future integration should distinguish between different failure categories.

### Validation Error

The request does not satisfy the contract.

Examples:

- Missing required field.
- Invalid weight.
- Invalid timestamp.
- Unsupported status.
- Empty city name.

### Unknown Location

The supplied origin or destination cannot be resolved by the ETA service.

### Model or Calibration Unavailable

The ETA prediction cannot be produced because the required model or prediction-interval calibration is unavailable.

### Internal Error

An unexpected failure occurs while processing the request.

The eventual transport/API implementation should map these semantic error categories to the agreed HTTP or service-level error representation.

Milestone 1 defines the semantics only; it does not implement API error handling.

## 10. Versioning

The contract should be versioned before cross-service implementation.

A version identifier such as `v1` should be agreed as part of the Logistics integration.

Breaking changes to the request or response contract must result in a new contract version rather than silently changing the existing contract.

The exact transport-level versioning mechanism is to be agreed with the integration owners.

## 11. Observability Requirements

The eventual production integration should make each ETA re-prediction traceable.

At minimum, the following information should be available in structured logs or equivalent observability systems:

- `shipment_id`
- `event_id`
- shipment status
- status-change timestamp
- contract version
- model version
- prediction
- confidence interval
- processing latency
- success/failure outcome
- error category when processing fails

Sensitive shipment information must follow the platform's existing logging and data-handling policies.

## 12. Current Implementation Boundary

This document defines a **future integration contract**.

The current ETA prediction implementation should not be represented as already supporting real-time status-change re-prediction.

In particular:

- The Logistics integration is not currently wired.
- No new API endpoint is introduced by this milestone.
- The existing prediction function remains unchanged.
- The existing ETA model is not modified by this milestone.
- Shipment status is not claimed to be a current model feature.
- The contract defines how status information can be supplied in a future integration.
- The way shipment status will affect the actual ETA prediction must be explicitly designed and implemented before the integration is enabled.

This distinction is important to prevent the documentation from claiming functionality that has not yet been implemented.

## 13. Integration Decisions Required Before Implementation

The following items require agreement with Logistics before this contract is wired:

1. Canonical shipment status enumeration.
2. Which status transitions trigger ETA re-prediction.
3. Transport mechanism between Logistics and ETA.
4. API/service endpoint naming.
5. Authentication and authorization mechanism.
6. Contract versioning mechanism.
7. Idempotency storage and ownership.
8. Timeout and retry policy.
9. Error response format.
10. Whether the future ETA model should predict total delivery time or remaining delivery time after a status transition.

The final item is particularly important because the current ETA prediction contract represents an ETA prediction in days, while a status-aware production implementation must explicitly define how elapsed shipment time and the current shipment state affect the predicted remaining time.

## 14. Example End-to-End Contract

### Logistics → ETA

    {
      "shipment_id": "SHIP-12345",
      "event_id": "EVENT-98765",
      "status": "<canonical_shipment_status>",
      "status_changed_at": "2026-10-07T09:30:00Z",
      "origin": "sao paulo",
      "destination": "rio de janeiro",
      "carrier": "carrier-x",
      "weight_kg": 2.5
    }

### ETA → Logistics

    {
      "shipment_id": "SHIP-12345",
      "eta_days": 5.2,
      "confidence_low": 4.1,
      "confidence_high": 7.3
    }

