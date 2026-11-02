import pytest

from scripts.a5_e2e_smoke import EventWatcher, SmokeFailure, get_path, render


def test_render_nested_placeholders():
    context = {
        "sku_id": "SKU-000123",
        "warehouse_id": "WH-BLR-01",
        "po_id": "PO-2026-000123",
    }

    value = {
        "path": "/inventory/{{sku_id}}",
        "body": {
            "warehouse": "{{warehouse_id}}",
            "metadata": [
                {"purchase_order": "{{po_id}}"},
                {"sku": "{{sku_id}}"},
            ],
        },
    }

    result = render(value, context)

    assert result["path"] == "/inventory/SKU-000123"
    assert result["body"]["warehouse"] == "WH-BLR-01"
    assert result["body"]["metadata"][0]["purchase_order"] == "PO-2026-000123"
    assert result["body"]["metadata"][1]["sku"] == "SKU-000123"


def test_get_path_supports_list_index():
    data = {
        "payload": {
            "items": [
                {"sku": "SKU-000001"},
                {"sku": "SKU-000123"},
            ]
        }
    }

    assert get_path(data, "payload.items.1.sku") == "SKU-000123"


def test_get_path_raises_key_error_for_missing_key():
    data = {"payload": {"sku": "SKU-000123"}}

    with pytest.raises(KeyError):
        get_path(data, "payload.missing")


def test_event_watcher_wait_for_returns_matching_seen_event():
    watcher = EventWatcher.__new__(EventWatcher)

    expected = {
        "event_type": "inventory.po.approved",
        "payload": {
            "purchase_order_id": "PO-2026-000123",
            "sku_id": "SKU-000123",
        },
    }

    watcher.seen = [
        {"event_type": "unrelated.event", "payload": {}},
        expected,
    ]

    result = watcher.wait_for(
        event_type="inventory.po.approved",
        match={"purchase_order_id": "PO-2026-000123"},
        timeout=1,
    )

    assert result == expected


def test_event_watcher_timeout_message():
    watcher = EventWatcher.__new__(EventWatcher)

    watcher.seen = [
        {
            "event_type": "inventory.updated",
            "payload": {"sku_id": "SKU-000123"},
        }
    ]

    with pytest.raises(SmokeFailure) as exc_info:
        watcher.wait_for(
            event_type="inventory.po.approved",
            match={"purchase_order_id": "PO-2026-000123"},
            timeout=0,
        )

    message = str(exc_info.value)

    assert "Timed out after 0s" in message
    assert "inventory.po.approved" in message
    assert "PO-2026-000123" in message
    assert "inventory.updated" in message