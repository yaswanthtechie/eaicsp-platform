# Profiling Library - Handover

**Folder:** `data-platform/profiling/`
**Previous owner:** Sandeep (until 08/10/2026)
**Current owner:** Tharun (from 08/10/2026)
**Last updated:** 14/10/2026

> How to use this template: replace every `<...>` and every `TODO` with what you actually found. Write facts you checked yourself. If you're not sure, say so in "Things I don't understand yet". "Mostly works" is not useful; "works on Postgres, fails on empty tables" is.

---

## 1. What this library does

<3 lines, in plain words. Example: "Profiles datasets (null rates, distinct counts, min/max, quantiles, drift) from files or directly inside Postgres (SQL pushdown). Runs on a schedule through an Airflow DAG and stores every run in an audit archive.">

---

## 2. How to run it

### Local Python (unit tests)
```powershell
cd data-platform/profiling
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest -m "not integration" -q
```
Result on 14/102026: `<179 passed, 0 failed, 3 skipped>`

### Database (Docker)
```powershell
docker compose -f docker-compose.dev.yml up -d
```
- Container name: `profiling-postgres-local`
- Database: `profiling_db`, schema `public`

### Load test data
```powershell
python benchmark_pushdown.py
```
Creates: `<list the tables, e.g. benchmark_1m_sales, products, test_sales_parity>`

### Airflow DAG (local test)
```powershell
docker exec -it airflow-tester python dags/profiling_dag.py
```
Result on 14/10/2026: `both tasks succeeded`

---

## 3. Connection details (read this before debugging)

| Where the code runs | Database address |
|---|---|
| My laptop (seed script, local tests) | `localhost:5433` |
| Inside Docker (the Airflow DAG) | `postgres-profiler:5432` |

- Port **5433** on the laptop, because 5432 is already in use by <what, e.g. a Postgres installed on Windows>.
- The DAG first looks for the Airflow connection `postgres_profiler_db`. If it doesn't exist, it uses the `PROFILING_DB_URL` environment variable, or the local default.
- Credentials come from `.env` (see `.env.example`). Nothing is hardcoded for real environments.

---

## 4. Module by module

| Module / file           | What it does                                    | Status                      | Tested?                        |
|-------------------------|-------------------------------------------------|-----------------------------|--------------------------------|
| `src/postgres_profiler.py` | SQL pushdown profiling inside Postgres          | works                       | yes                            |
| `src/audit_archive.py`  | Stores every profiling run                      | works                       | yes                            |
| `dags/profiling_dag.py` | Scheduled profiling in Airflow                  | Works (verified 13/10/2026) | Run manually with `dag.test()` |
| `cross_check_evidently.py`   | Cross-check the drift detection against Evidentl | works                       | yes                            |

---

## 5. Sandeep's Round 12-13 work: status

| Milestone | Status                             | Notes |
|---|------------------------------------|---|
| 1. SQL pushdown profiling (same results as pandas, with timings) | done (fixed by Tharun, 12/10/2026) |Benchmark summary written to reports/pushdown_benchmark_results.csv |
| 2. Scheduled profiling as an Airflow DAG | Done (fixed by Tharun, 13/10/2026) | See section 7 |
| 3. Evidently comparison (agreements and disagreements explained) | Done (fixed by Tharun, 13/10/2026) | reports/evidently_drift_report.html |

Open PR from Sandeep: `<PR number, or "none">` → `<finished and merged / closed, remaining items listed below>`

---

## 6. Known issues and gotchas

- **Airflow uses SQLAlchemy 1.4, not 2.0.** Code that runs inside Airflow must work with 1.4. Example: use `from sqlalchemy.engine import Engine`, not `from sqlalchemy import Engine`. Don't upgrade SQLAlchemy inside the Airflow container.
- **Never log a database URL directly.** Airflow's log formatter prints the password. Log `url.render_as_string(hide_password=True)` instead.
- **The DAG only profiles tables that exist.** A missing table fails immediately with a clear message listing the available tables (no retry).
- **PowerShell quoting:** `python -c "..."` one-liners break easily inside `docker exec`. Use `psql` or a small script file instead.
- **`\dt *.*` in psql shows system tables first.** Use `\dt public.*` to see our tables.


---

## 7. What I fixed

| Date | Problem | Fix |
|---|---|---|
| 13/10 | DAG failed: `cannot import name 'Engine' from 'sqlalchemy'` | Import changed for SQLAlchemy 1.4 compatibility |
| 13/10 | DAG failed: `NoSuchTableError: sales` | No `sales` table exists; DAG now profiles `benchmark_1m_sales` and `products` |
| 13/10 | Missing tables caused slow retries and unclear errors | Added a table check that fails clearly, without retrying |
| 13/10 | Database password could appear in logs | URL is masked before logging |


---

## 8. Things I don't understand yet
- Docker/Windows File System Conflicts: Exactly how Linux-created symlinks inside Docker (like Airflow's logs/scheduler/latest) interact with the Windows host file system, which recently caused pytest to crash with [WinError 1920] during test collection.

- Airflow Local Metadata: Why running a seemingly standalone local script via dag.test() strictly requires a fully initialized SQLite metadata database (airflow db migrate) to track task_instance records.

- Evidently's Statistical Underpinnings: The deep mathematical differences between Evidently's default drift tests (like Wasserstein distance) and our custom heuristic thresholds, specifically regarding how Evidently evaluates variance shifts without mean shifts.

- The Dependency Matrix: The exact long-term compatibility path for our stack, given that Pandas 3.0 requires Python 3.11+, but Airflow 2.7.3 restricts SQLAlchemy to <2.0, making Conda environment resolution fragile.

---

## 9. What's left / next steps

- [ ] Round 14: expose quality scores on Prometheus `/metrics`, same naming style as the validation library
