# Event Contracts & Schemas

This directory acts as the single source of truth for our Kafka event schemas. As per the integration blueprint, we follow a strict **contract-first** approach. Every event must have a JSON Schema and a worked example documented here before any consumer builds against it.

Consumers should leverage these schemas to build strict payload validations at their boundaries. Any incoming event failing this schema validation should be routed to a dead-letter queue (DLQ) rather than halting the partition or polluting local stores.

## Naming Rules
Event types and their corresponding files must follow the `<domain>.<entity>.<action>` format.
* **Domain:** The owning service (e.g., `inventory`, `supplierportal`, `compliance`).
* **Entity:** The core business object (e.g., `po`, `shipment`, `supplier`).
* **Action:** Past-tense verb of what occurred (e.g., `approved`, `status_changed`).

*Example:* `inventory.po.approved`

## Versioning Rules
1. **Major Versions Only in Filenames:** Schemas are versioned with a `vX` suffix in the filename (e.g., `envelope.v1.json`). 
2. **Backwards Compatibility:** Adding optional fields to the `payload` is a non-breaking change and does not require a new version. Removing fields, changing data types, or adding required fields is a breaking change and requires publishing a `v2` schema alongside `v1`.
3. Consumers must parse the `event_version` field in the envelope to apply the correct validation profile.

## How to Add an Event
1. Copy `_template.v1.json` and rename it to your event name (e.g., `logistics.route.optimized.v1.json`).
2. Define your specific properties within the `payload` block. Use strict formatting where applicable (e.g., regex patterns for canonical IDs).
3. Create a valid mock payload in the `examples/` subfolder.
4. Open a PR and ensure your unit tests validate the example payload against your new schema.