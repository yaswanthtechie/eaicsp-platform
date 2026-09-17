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


def test_profile_rejects_non_csv():
    response = client.post(
        "/profile",
        files={
            "file": (
                "test.txt",
                "this is not a csv",
                "text/plain"
            )
        }
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only CSV files are allowed."


def test_profile_rejects_empty_file():
    response = client.post(
        "/profile",
        files={
            "file": (
                "empty.csv",
                "",
                "text/csv"
            )
        }
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded CSV file is empty."


def test_profile_rejects_invalid_csv():
    response = client.post(
        "/profile",
        files={
            "file": (
                "invalid.csv",
                b"\xff\xfe\x00\x01",
                "text/csv"
            )
        }
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid CSV file."


def test_profile_rejects_large_file():
    large_content = b"a" * (10 * 1024 * 1024 + 1)

    response = client.post(
        "/profile",
        files={
            "file": (
                "large.csv",
                large_content,
                "text/csv"
            )
        }
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "File size exceeds the 10 MB limit."


def test_profile_requires_file():
    response = client.post("/profile")

    assert response.status_code == 422


def test_profile_empty_dataset():
    response = client.post(
        "/profile",
        files={
            "file": (
                "empty.csv",
                "sku_id,warehouse_id,quantity_sold,unit_price\n",
                "text/csv"
            )
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "empty_dataset"
    assert data["message"] == "The dataset contains no rows."
    assert data["shape"][0] == 0