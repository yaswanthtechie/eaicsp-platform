# R9 M5 — Disaster Recovery Drill

## Objective

Recover the ETL pipeline after a simulated mid-run failure using only:

1. the PostgreSQL backup;
2. `etl_run_log` and `etl_run_batches`;
3. the original recorded source batch files;
4. the existing deterministic replay mechanism.

No rows are manually reconstructed.

## Drill procedure

1. Select the latest successful run (or pass `--run-id`).
2. Run:

```bash
python scripts/disaster_recovery_drill.py --backup docs/dr_drill_backup.dump
```

3. Restore the dump into a clean PostgreSQL instance using the normal
   PostgreSQL restore procedure.
4. Run the drill again with `--replay` against the restored instance:

```bash
python scripts/disaster_recovery_drill.py --backup docs/dr_drill_backup.dump --run-id <RUN_ID> --replay
```

5. Verify the replay result and the normal reconciliation records.

The source-file manifest is read from `etl_run_batches`, so the recovery
does not depend on remembering which files were processed manually.

## Failure simulation

For the exercise, stop/kill the ETL process after extraction or loading has
started. The failed run remains represented by the run log and its recorded
batch manifest. The backup + replay procedure above reconstructs the run from
those durable artifacts.

## Evidence to retain

- backup file checksum;
- run ID;
- list of recorded batch files;
- replay result;
- reconciliation result;
- timestamp and operator.

The drill is intentionally non-destructive: the script creates the backup and
checks the recovery manifest. Restoration should be performed against a clean
database/environment rather than overwriting a live production database.
