from app.services import refresh_service


def test_refresh_snapshot_save_load_and_compare(tmp_path, monkeypatch):
    snapshot_file = tmp_path / "snapshot.json"
    log_dir = tmp_path / "logs"

    monkeypatch.setattr(refresh_service, "SNAPSHOT_FILE", snapshot_file)
    monkeypatch.setattr(refresh_service, "LOG_DIR", log_dir)

    assert refresh_service.load_snapshot() == {}

    previous = {"OLD": {"name": "Old Supplier"}}
    current = {
        "NEW": {"name": "New Supplier"},
        "SHARED": {"name": "Shared Supplier"},
    }

    refresh_service.save_snapshot(previous)
    assert refresh_service.load_snapshot() == previous

    changes = refresh_service.refresh_sanctions(current)

    assert changes["added"] == ["NEW", "SHARED"]
    assert changes["removed"] == ["OLD"]
    assert refresh_service.load_snapshot() == current

    log_content = (log_dir / "refresh.log").read_text(encoding="utf-8")
    assert "Refresh comparison completed" in log_content
    assert "Added entities: 2" in log_content
    assert "Removed entities: 1" in log_content


def test_load_snapshot_handles_corrupted_json(tmp_path, monkeypatch):
    snapshot_file = tmp_path / "snapshot.json"
    log_dir = tmp_path / "logs"

    monkeypatch.setattr(refresh_service, "SNAPSHOT_FILE", snapshot_file)
    monkeypatch.setattr(refresh_service, "LOG_DIR", log_dir)

    snapshot_file.write_text("{invalid json", encoding="utf-8")

    assert refresh_service.load_snapshot() == {}
    assert "Snapshot corrupted. Starting fresh." in (log_dir / "refresh.log").read_text(
        encoding="utf-8"
    )


def test_build_snapshot_sorts_sources_and_uses_defaults():
    result = refresh_service.build_snapshot(
        {
            "SUP-1": {
                "name": "Supplier One",
                "sources": ["UN", "OFAC"],
                "confidence": 85,
            },
            "SUP-2": {"name": "Supplier Two"},
        }
    )

    assert result == {
        "SUP-1": {
            "name": "Supplier One",
            "sources": ["OFAC", "UN"],
            "confidence": 85,
        },
        "SUP-2": {
            "name": "Supplier Two",
            "sources": [],
            "confidence": 100,
        },
    }


def test_compare_snapshots_reports_added_and_removed():
    result = refresh_service.compare_snapshots(
        {"OLD": {}, "SHARED": {}},
        {"NEW": {}, "SHARED": {}},
    )

    assert result["added"] == ["NEW"]
    assert result["removed"] == ["OLD"]
    assert "timestamp" in result
