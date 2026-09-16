from fastapi.testclient import TestClient

from src.api import app


client = TestClient(app)


def test_profile_upload():
    csv_content = """sku_id,warehouse_id,quantity_sold,unit_price
SKU001,WH1,10,100
SKU002,WH1,20,200
SKU003,WH2,30,150
SKU004,WH2,40,120
"""

    response = client.post(
        "/profile",
        files={
            "file": (
                "test.csv",
                csv_content,
                "text/csv"
            )
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert "shape" in data
    assert "columns" in data
    assert "column_summary" in data
    assert "quality_scorecard" in data
    assert "insights" in data