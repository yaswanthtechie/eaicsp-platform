import json

from app.services.refresh_service import (
    compare_snapshots,
    refresh_sanctions,
    save_snapshot,
    load_snapshot,
)




def test_compare_snapshots():

    previous = {
        "HAMAS": {},
        "ALPHA": {},
        "OLD_ENTITY": {},
    }

    current = {
        "HAMAS": {},
        "ALPHA": {},
        "NEW_ENTITY": {},
    }

    result = compare_snapshots(
        previous,
        current,
    )

    assert "NEW_ENTITY" in result["added"]

    assert "OLD_ENTITY" in result["removed"]

    assert "HAMAS" not in result["added"]

    assert "ALPHA" not in result["removed"]




def test_compare_empty_snapshot():

    previous = {}

    current = {
        "HAMAS": {},
    }

    result = compare_snapshots(
        previous,
        current,
    )

    assert result["added"] == [
        "HAMAS"
    ]

    assert result["removed"] == []




def test_save_snapshot(
    tmp_path,
    monkeypatch,
):

    from app.services import refresh_service

    test_file = (
        tmp_path /
        "snapshot.json"
    )

    monkeypatch.setattr(
        refresh_service,
        "SNAPSHOT_FILE",
        test_file,
    )

    data = {
        "ENTITY1": {
            "source": "OFAC",
        }
    }

    save_snapshot(data)

    assert test_file.exists()

    with open(
        test_file,
        "r",
        encoding="utf-8",
    ) as file:

        loaded = json.load(file)

    assert loaded == data




def test_load_snapshot_empty(
    tmp_path,
    monkeypatch,
):

    from app.services import refresh_service

    test_file = (
        tmp_path /
        "missing.json"
    )

    monkeypatch.setattr(
        refresh_service,
        "SNAPSHOT_FILE",
        test_file,
    )

    result = load_snapshot()

    assert result == {}



def test_refresh_sanctions(
    tmp_path,
    monkeypatch,
):

    from app.services import refresh_service

    snapshot_file = (
        tmp_path /
        "snapshot.json"
    )

    log_dir = (
        tmp_path /
        "logs"
    )

    monkeypatch.setattr(
        refresh_service,
        "SNAPSHOT_FILE",
        snapshot_file,
    )

    monkeypatch.setattr(
        refresh_service,
        "LOG_DIR",
        log_dir,
    )

 
    first_data = {
        "HAMAS": {},
        "ENTITY_A": {},
    }

    result1 = refresh_sanctions(
        first_data
    )

    assert "HAMAS" in result1["added"]

    assert "ENTITY_A" in result1["added"]


    second_data = {
        "HAMAS": {},
        "ENTITY_B": {},
    }

    result2 = refresh_sanctions(
        second_data
    )

    assert "ENTITY_B" in result2["added"]

    assert "ENTITY_A" in result2["removed"]

    assert snapshot_file.exists()




def test_no_duplicate_changes():

    previous = {
        "HAMAS": {},
    }

    current = {
        "HAMAS": {},
    }

    result = compare_snapshots(
        previous,
        current,
    )

    assert result["added"] == []

    assert result["removed"] == []