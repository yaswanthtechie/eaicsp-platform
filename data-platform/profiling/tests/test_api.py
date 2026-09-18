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

VALID_CSV = "sku_id,warehouse_id,quantity_sold,unit_price\nSKU001,WH1,10,100\nSKU002,WH2,20,200\n"


def test_profile_accepts_csv_with_charset_parameter():
    response = client.post(
        "/profile",
        files={"file": ("data.csv", VALID_CSV, "text/csv; charset=utf-8")}
    )

    assert response.status_code == 200


def test_profile_accepts_windows_excel_content_type():
    # Windows browsers send this for .csv files when Excel is installed
    response = client.post(
        "/profile",
        files={"file": ("data.csv", VALID_CSV, "application/vnd.ms-excel")}
    )

    assert response.status_code == 200


def test_profile_rejects_csv_content_type_with_wrong_extension():
    response = client.post(
        "/profile",
        files={"file": ("data.exe", VALID_CSV, "text/csv")}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only CSV files are allowed."


def test_profile_rejects_rows_with_more_fields_than_header():
    response = client.post(
        "/profile",
        files={"file": ("ragged.csv", "a,b\n1,2,3,4\n5\n", "text/csv")}
    )

    assert response.status_code == 400
    assert "more fields than the header" in response.json()["detail"]


def test_profile_with_missing_values_returns_valid_json():
    # NaN in the report used to crash JSON encoding with a 500
    csv_content = "a,b\n1,\n,2\n3,4\n"

    response = client.post(
        "/profile",
        files={"file": ("nulls.csv", csv_content, "text/csv")}
    )

    assert response.status_code == 200