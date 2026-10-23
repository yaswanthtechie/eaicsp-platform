# ETA Shipment Predicted Contract

## 1. Event

**Event name:** `eta.shipment.predicted`

## 2. Purpose

Published by the ETA service when an ETA prediction is generated for a shipment.

## 3. Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `shipment_id` | string | Yes | Unique identifier of the shipment |
| `po_number` | string | Yes | Purchase order number associated with the shipment |
| `eta_days` | number | Yes | Predicted delivery time in days |
| `confidence_low` | number | Yes | Lower bound of the ETA prediction interval, in days |
| `confidence_high` | number | Yes | Upper bound of the ETA prediction interval, in days |
| `model_version` | string | Yes | Version of the ETA model that generated the prediction |
| `predicted_at` | string | Yes | UTC timestamp when the prediction was generated, in ISO-8601 format |

## 4. Example

    {
      "shipment_id": "SHIP-12345",
      "po_number": "PO-98765",
      "eta_days": 5.2,
      "confidence_low": 4.1,
      "confidence_high": 7.3,
      "model_version": "eta-model-v1",
      "predicted_at": "2026-10-23T10:30:00Z"
    }

## 5. Validation Rules

- `shipment_id` must be present and non-empty.
- `po_number` must be present and non-empty.
- `eta_days` must be numeric and non-negative.
- `confidence_low` must be numeric and non-negative.
- `confidence_high` must be numeric and non-negative.
- `confidence_low` must be less than or equal to `confidence_high`.
- `model_version` must be present and non-empty.
- `predicted_at` must be a valid ISO-8601 UTC timestamp.