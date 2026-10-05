"""
Runner script for Round 10 Locust Load Test Sweep.
Executes Locust across user concurrencies [5, 10, 20, 50, 100],
gathers real metrics from the generated CSVs, identifies break point and bottleneck,
and prints a formatted summary.
"""

import csv
import subprocess
import sys
import time
from pathlib import Path

CONCURRENCIES = [5, 10, 20, 50, 100]
RUN_TIME = "20s"
HOST = "http://127.0.0.1:8000"
GATEWAY_DIR = Path(__file__).resolve().parent

results = []

for u in CONCURRENCIES:
    print(f"\n=======================================================")
    print(f"Running Locust sweep for {u} concurrent users ({RUN_TIME})...")
    print(f"=======================================================")
    spawn_rate = max(2, u // 5)
    csv_prefix = f"load_tests/round10_results_u{u}"
    cmd = [
        sys.executable,
        "-m", "locust",
        "-f", "load_tests/round10_locustfile.py",
        "--headless",
        "--users", str(u),
        "--spawn-rate", str(spawn_rate),
        "--run-time", RUN_TIME,
        "--host", HOST,
        "--csv", csv_prefix,
    ]
    p = subprocess.run(cmd, cwd=str(GATEWAY_DIR), capture_output=True, text=True)
    if p.returncode != 0:
        print(f"Locust run for {u} users failed:\n{p.stderr}")

    stats_file = GATEWAY_DIR / f"{csv_prefix}_stats.csv"
    if stats_file.exists():
        with open(stats_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Type") is None or row.get("Name") == "Aggregated":
                    reqs = int(row.get("Request Count", 0))
                    fails = int(row.get("Failure Count", 0))
                    err_rate = (fails / reqs * 100.0) if reqs else 0.0
                    results.append({
                        "concurrency": u,
                        "reqs": reqs,
                        "fails": fails,
                        "error_rate": err_rate,
                        "rps": float(row.get("Requests/s", 0.0)),
                        "p50": float(row.get("50%", 0.0)),
                        "p95": float(row.get("95%", 0.0)),
                        "p99": float(row.get("99%", 0.0)),
                        "avg": float(row.get("Average Response Time", 0.0)),
                    })
    time.sleep(1)

print("\n" + "="*80)
print("ROUND 10 LOCUST LOAD TEST SWEEP SUMMARY (DOWNSTREAM ACTIVE)")
print("="*80)
print(f"{'Users':<8}{'Requests':<10}{'Failures':<10}{'Error %':<10}{'RPS':<10}{'p50 (ms)':<12}{'p95 (ms)':<12}{'p99 (ms)':<12}")
print("-" * 80)
for r in results:
    print(f"{r['concurrency']:<8}{r['reqs']:<10}{r['fails']:<10}{r['error_rate']:<10.2f}{r['rps']:<10.1f}{r['p50']:<12.1f}{r['p95']:<12.1f}{r['p99']:<12.1f}")
print("="*80)
