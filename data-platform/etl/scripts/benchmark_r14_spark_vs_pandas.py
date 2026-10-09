"""R14 honest Pandas-vs-Spark benchmark (transform only, same CSV, same rules).

Each engine runs in its OWN process; peak memory = max summed RSS of that process
and its children (includes the Spark JVM). Needs psutil for memory.
    python scripts/benchmark_r14_spark_vs_pandas.py data/backfill/sales_history.csv
Writes docs/r14_benchmark.json. Postgres write time is NOT included (see README).
"""
import argparse, json, os, subprocess, sys, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
KEY = ["date", "sku_id", "warehouse_id"]


def pandas_path(path):
    import pandas as pd
    df = pd.read_csv(path, dtype=str)
    df = df.drop_duplicates()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["quantity_sold"] = pd.to_numeric(df["quantity_sold"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df = df.dropna()                       # same reject policy as the Spark path
    df = df.drop_duplicates(subset=KEY, keep="last")
    return int(len(df)), int(df["quantity_sold"].sum()), float(df["unit_price"].sum())


def spark_path(path):
    from pyspark.sql import SparkSession, functions as F
    from pyspark.sql.types import StructType, StructField, StringType
    from spark.sales_backfill import COLUMNS, _prepare, dedupe_by_key
    spark = SparkSession.builder.master("local[*]").appName("r14-benchmark").getOrCreate()
    try:
        schema = StructType([StructField(c, StringType(), True) for c in COLUMNS])
        df = spark.read.option("header", True).schema(schema).csv(path)
        df = dedupe_by_key(_prepare(df))
        a = df.agg(F.count("*").alias("n"), F.sum("quantity_sold").alias("q"),
                   F.sum("unit_price").alias("p")).collect()[0]
        return int(a["n"]), int(a["q"]), float(a["p"])
    finally:
        spark.stop()


def child(engine, path):
    import psutil
    peak = [0]; stop = threading.Event()

    def sample():
        me = psutil.Process()
        while not stop.is_set():
            try:
                peak[0] = max(peak[0], me.memory_info().rss
                              + sum(c.memory_info().rss for c in me.children(recursive=True)))
            except psutil.Error:
                pass
            time.sleep(0.1)
    t = threading.Thread(target=sample, daemon=True); t.start()
    t0 = time.perf_counter()
    rows, qty, price = (pandas_path if engine == "pandas" else spark_path)(path)
    sec = time.perf_counter() - t0
    stop.set(); t.join()
    print("RESULT " + json.dumps({"engine": engine, "rows": rows, "qty": qty,
                                  "price": round(price, 2), "seconds": round(sec, 2),
                                  "peak_rss_mb": round(peak[0] / 1e6)}))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input"); p.add_argument("--engine", choices=["pandas", "spark"])
    a = p.parse_args()
    if a.engine:
        return child(a.engine, a.input)
    res = {}
    for eng in ("pandas", "spark"):
        out = subprocess.run([sys.executable, __file__, a.input, "--engine", eng],
                             capture_output=True, text=True)
        line = [l for l in out.stdout.splitlines() if l.startswith("RESULT ")]
        if not line:
            raise SystemExit(f"{eng} failed:\n{out.stderr[-2000:]}")
        res[eng] = json.loads(line[0][7:]); print(res[eng])
    pr, sr = res["pandas"], res["spark"]
    parity = (pr["rows"], pr["qty"]) == (sr["rows"], sr["qty"]) and abs(pr["price"] - sr["price"]) <= 0.01
    print("PARITY:", "PASS" if parity else "FAIL")
    os.makedirs("docs", exist_ok=True)
    json.dump({**res, "parity": parity, "input_bytes": os.path.getsize(a.input)},
              open("docs/r14_benchmark.json", "w"), indent=2)
    if not parity:
        raise SystemExit("PARITY FAILURE")


if __name__ == "__main__":
    main()
