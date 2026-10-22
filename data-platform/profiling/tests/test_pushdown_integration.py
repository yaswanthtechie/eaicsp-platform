import pytest
import pandas as pd
from sqlalchemy import create_engine
from src.db_config import get_db_url
from src.postgres_profiler import PostgresPushdownProfiler
from src.profile import profile
from src.parity import compare_reports



@pytest.mark.integration
def test_postgres_pushdown_vs_pandas_parity():
    engine = create_engine(get_db_url())   # fails loudly if PROFILING_DB_URL is missing

    # 1. Populate test data in PostgreSQL
    df_sample = pd.DataFrame({
        "sku_id": [f"SKU{i:03d}" for i in range(1, 101)],
        "quantity_sold": [float(i) for i in range(1, 101)],
        "unit_price": [10.5 * i for i in range(1, 101)],
    })
    df_sample.loc[0:4, "quantity_sold"] = None  # 5 nulls
    df_sample.loc[98, "quantity_sold"] = 99999.0  # Outlier

    table_name = "test_sales_parity"
    with engine.begin() as connection:
        df_sample.to_sql(
            table_name,
            connection,
            if_exists="replace",
            index=False,
        )

    # 2. Run Pushdown Profiler
    pushdown = PostgresPushdownProfiler(engine)
    report_sql = pushdown.profile_table(table_name)

    # 3. Run In-Memory Pandas Profiler
    report_pandas = profile(df_sample)

    # 4. Verify Parity
    assert compare_reports(report_pandas, report_sql) == []