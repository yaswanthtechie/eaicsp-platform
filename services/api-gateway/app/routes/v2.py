"""
API Version 2 router demonstrating a future breaking API contract
without disrupting v1 clients.
"""

from fastapi import APIRouter

router = APIRouter(
    prefix="/api/v2",
    tags=["v2"],
)


@router.get(
    "/status",
    summary="API v2 Gateway Status",
)
async def get_v2_status():
    """
    Return API v2 version and status metadata.
    """
    return {
        "status": "active",
        "version": "v2.0.0-stub",
    }


@router.get(
    "/inventory/items",
    summary="API v2 Inventory Items (Stub)",
)
async def get_v2_inventory_items():
    """
    Demonstration stub showing a breaking API schema change in v2.
    Returns a versioned envelope containing version, data, and meta fields.
    """
    return {
        "version": "v2",
        "data": [
            {
                "id": "inv_001",
                "name": "Item A",
                "quantity": 100,
                "status": "in_stock",
            },
            {
                "id": "inv_002",
                "name": "Item B",
                "quantity": 50,
                "status": "low_stock",
            },
        ],
        "meta": {
            "total": 2,
            "page": 1,
            "page_size": 10,
            "breaking_change": True,
        },
    }
