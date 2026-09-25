# Model Governance

## Objective

Production promotion requires explicit governance approval.

## Workflow

Candidate Model
    ↓
Evaluation
    ↓
Approval Request
    ↓
Pending
    ↓
Approval Decision
    ├── Rejected → Promotion blocked
    └── Approved → Promotion allowed
                       ↓
                   Production

## Approval States

- pending
- approved
- rejected

## Governance Evidence

An unapproved model promotion must fail with a governance error.

After approval, the same model version can be promoted successfully.

## Example

Model: forecast
Version: v2

Status before approval:

PROMOTION BLOCKED

Status after approval:

PROMOTION ALLOWED