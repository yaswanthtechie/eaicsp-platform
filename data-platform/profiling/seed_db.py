import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path

def main():
    # Connect using the internal Docker network URL
    engine = create_engine("postgresql://postgres:password@postgres-profiler:5432/profiling_db")
    data_dir = Path("data")

    for table in ["sales", "products"]:
        csv_path = data_dir / f"{table}_data.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            df.to_sql(table, engine, if_exists="replace", index=False)
            print(f"Successfully loaded '{table}' table with {len(df)} rows.")
        else:
            print(f"WARNING: {csv_path} not found. The DAG will fail on this table.")

if __name__ == "__main__":
    main()