"""Master data schemas for products and warehouses (R15 / #353 / #354)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProductResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "sku_id": "SKU-000001",
                "name": "Product 1",
                "category": "Electronics",
                "unit_of_measure": "PCS",
            }
        },
    )

    sku_id: str = Field(description="Canonical SKU identifier", examples=["SKU-000001"])
    name: str = Field(description="Product name", examples=["Product 1"])
    category: str = Field(description="Product category", examples=["Electronics"])
    unit_of_measure: Optional[str] = Field(
        default=None, description="Unit of measure", examples=["PCS"]
    )


class ProductListResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "sku_id": "SKU-000001",
                        "name": "Product 1",
                        "category": "Electronics",
                        "unit_of_measure": "PCS",
                    }
                ],
                "total": 1,
            }
        },
    )

    items: list[ProductResponse]
    total: int = Field(ge=0, description="Total matching records before pagination")


class WarehouseResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "warehouse_id": "WH-BLR-01",
                "name": "Bangalore Warehouse",
                "city": "Bangalore",
                "state": "Karnataka",
                "country": "India",
            }
        },
    )

    warehouse_id: str = Field(
        description="Canonical warehouse identifier", examples=["WH-BLR-01"]
    )
    name: str = Field(description="Warehouse name", examples=["Bangalore Warehouse"])
    city: str = Field(description="City", examples=["Bangalore"])
    state: str = Field(description="State", examples=["Karnataka"])
    country: str = Field(description="Country", examples=["India"])


class WarehouseListResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "warehouse_id": "WH-BLR-01",
                        "name": "Bangalore Warehouse",
                        "city": "Bangalore",
                        "state": "Karnataka",
                        "country": "India",
                    }
                ],
                "total": 1,
            }
        },
    )

    items: list[WarehouseResponse]
    total: int = Field(ge=0, description="Total matching records before pagination")
