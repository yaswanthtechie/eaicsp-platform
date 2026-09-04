import subprocess
import time
import os
import sys

services = [
    ("logistics", "services/logistics", "uvicorn app.main:app --port 8002"),
    ("compliance", "services/compliance", "uvicorn app.main:app --port 8003"),
    ("supplier-portal", "services/supplier-portal", "uvicorn app.main:app --port 8004"),
    ("platform", "services/platform", "uvicorn app.main:app --port 8005"),
]

processes = []

for name, path, cmd in services:
    print(f"Starting {name} in {path}...")
    cwd = os.path.join(os.getcwd(), path.replace('/', '\\'))
    p = subprocess.Popen(
        cmd,
        cwd=cwd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    processes.append((name, p))

time.sleep(5)

for name, p in processes:
    if p.poll() is not None:
        print(f"[{name}] FAILED to start. Exit code: {p.poll()}")
        out, err = p.communicate()
        print(f"STDOUT:\n{out}")
        print(f"STDERR:\n{err}")
    else:
        print(f"[{name}] is RUNNING.")
        # Do not kill it, leave it running
