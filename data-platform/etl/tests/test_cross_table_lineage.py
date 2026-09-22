
from types import SimpleNamespace

from etl.src.lineage import trace_row_lineage


class Result:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def mappings(self):
        return self

    def first(self):
        return self._row

    def all(self):
        return self._rows


class Connection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        sql = str(query)
        if "FROM shipments_fact" in sql:
            return Result(row={
                "id": 30, "shipment_date": "2024-01-01",
                "sku_id": "S1", "warehouse_id": "W1",
                "run_id": 300, "source_batch": "ship.csv",
            })
        if "FROM inventory_snapshot" in sql:
            return Result(rows=[{
                "id": 20, "snapshot_date": "2024-01-01",
                "sku_id": "S1", "warehouse_id": "W1",
                "run_id": 200, "source_batch": "inv.csv",
            }])
        if "FROM sales_fact" in sql:
            return Result(rows=[{
                "id": 10, "date": "2024-01-01",
                "sku_id": "S1", "warehouse_id": "W1",
                "run_id": 100, "source_batch": "sales.csv",
            }])
        raise AssertionError(sql)


class Engine:
    def connect(self):
        return Connection()


def test_lineage_walks_shipments_to_inventory_to_sales():
    sales = SimpleNamespace(
        name="sales", table="sales_fact", date_column="date",
        depends_on=None,
    )
    inventory = SimpleNamespace(
        name="inventory", table="inventory_snapshot",
        date_column="snapshot_date", depends_on="sales",
    )
    shipments = SimpleNamespace(
        name="shipments", table="shipments_fact",
        date_column="shipment_date", depends_on="inventory",
    )

    config = SimpleNamespace(
        sources=[sales, inventory, shipments],
        get_source=lambda name: {"sales": sales, "inventory": inventory, "shipments": shipments}[name],
    )

    lineage = trace_row_lineage(30, "shipments_fact", config=config, engine=Engine())
    assert [item["table"] for item in lineage] == [
        "shipments_fact", "inventory_snapshot", "sales_fact"
    ]
    assert [item["run_id"] for item in lineage] == [300, 200, 100]
