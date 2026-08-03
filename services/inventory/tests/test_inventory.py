import threading
import pytest



def create_payload(
    sku="SKU100",
    warehouse="WH001",
    quantity=40
):

    return {
        "sku_id": sku,
        "product_name": "Laptop",
        "warehouse_id": warehouse,
        "quantity_on_hand": quantity,
        "avg_daily_demand": 5,
        "lead_time_days": 4,
        "safety_stock": 10,
    }



# -----------------------------------
# CREATE INVENTORY
# -----------------------------------

def test_create_inventory(client):

    response = client.post(
        "/api/v1/inventory",
        json=create_payload(
            "SKU101"
        )
    )


    assert response.status_code == 201


    data=response.json()


    assert data["sku_id"]=="SKU101"
    assert data["warehouse_id"]=="WH001"
    assert data["reorder_point"]==30





# -----------------------------------
# GET INVENTORY BY WAREHOUSE
# -----------------------------------

def test_get_inventory(client):

    client.post(
        "/api/v1/inventory",
        json=create_payload()
    )


    response=client.get(
        "/api/v1/inventory/SKU100/WH001"
    )


    assert response.status_code==200


    data=response.json()


    assert data["sku_id"]=="SKU100"
    assert data["warehouse_id"]=="WH001"





# -----------------------------------
# REORDER CHECK
# -----------------------------------

def test_reorder_check(client):

    client.post(
        "/api/v1/inventory",
        json=create_payload()
    )


    response=client.get(
        "/api/v1/inventory/SKU100/WH001/reorder-check"
    )


    data=response.json()


    assert data["reorder_point"]==30
    assert data["needs_reorder"] is False





# -----------------------------------
# BELOW REORDER POINT
# -----------------------------------

def test_reorder_required(client):

    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "LOW1",
            quantity=10
        )
    )


    response=client.get(
        "/api/v1/inventory/LOW1/WH001/reorder-check"
    )


    data=response.json()


    assert data["needs_reorder"] is True
    assert data["suggested_order_qty"]==20





# -----------------------------------
# EQUAL REORDER POINT
# -----------------------------------

def test_equal_reorder_point(client):

    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "EQ1",
            quantity=30
        )
    )


    response=client.get(
        "/api/v1/inventory/EQ1/WH001/reorder-check"
    )


    assert response.json()["needs_reorder"] is True





# -----------------------------------
# MULTI WAREHOUSE
# -----------------------------------

def test_same_sku_multiple_warehouses(client):


    first = client.post(
        "/api/v1/inventory",
        json=create_payload(
            "MULTI1",
            "WH001",
            100
        )
    )


    second = client.post(
        "/api/v1/inventory",
        json=create_payload(
            "MULTI1",
            "WH002",
            20
        )
    )


    assert first.status_code==201
    assert second.status_code==201





# -----------------------------------
# REORDER PLAN
# -----------------------------------

def test_reorder_plan(client):

    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "PLAN1",
            "WH001",
            5
        )
    )


    response=client.get(
        "/api/v1/inventory/reorder-plan"
    )


    assert response.status_code==200


    data=response.json()


    assert len(data)>0
    assert "urgency_score" in data[0]





# -----------------------------------
# LOW STOCK
# -----------------------------------

def test_low_stock(client):

    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "LOW2",
            quantity=5
        )
    )


    response=client.get(
        "/api/v1/inventory/low-stock"
    )


    assert response.status_code==200
    assert isinstance(response.json(),list)





# -----------------------------------
# DEMAND SPIKE
# -----------------------------------

def test_simulate(client):

    client.post(
        "/api/v1/inventory",
        json=create_payload()
    )


    response=client.post(
        "/api/v1/inventory/SKU100/WH001/simulate",
        json={
            "demand_spike_percent":50
        }
    )


    assert response.status_code==200


    data=response.json()


    assert "new_reorder_point" in data





# -----------------------------------
# WHAT IF
# -----------------------------------

def test_what_if(client):

    client.post(
        "/api/v1/inventory",
        json=create_payload()
    )


    response=client.post(
        "/api/v1/inventory/what-if",
        json={
            "spike_percent":50
        }
    )


    assert response.status_code==200

    assert "affected_skus" in response.json()





# -----------------------------------
# DELETE
# -----------------------------------

def test_delete_inventory(client):

    client.post(
        "/api/v1/inventory",
        json=create_payload()
    )


    response=client.delete(
        "/api/v1/inventory/SKU100/WH001"
    )


    assert response.status_code==200





# -----------------------------------
# BULK UPDATE ROLLBACK
# -----------------------------------

def test_bulk_update_failure(client):

    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "BULK1",
            "WH001",
            50
        )
    )


    updates=[

        {
            "sku_id":"BULK1",
            "warehouse_id":"WH001",
            "quantity_delta":-10
        },

        {
            "sku_id":"INVALID",
            "warehouse_id":"WH001",
            "quantity_delta":-5
        }

    ]


    response=client.post(
        "/api/v1/inventory/bulk-update",
        json=updates
    )


    assert response.status_code==409



# -----------------------------------
# CONCURRENT DECREMENT
# -----------------------------------

def test_concurrent_decrement(client):


    client.post(
        "/api/v1/inventory",
        json=create_payload(
            "CON1",
            "WH001",
            10
        )
    )



    def decrease():

        response=client.post(
            "/api/v1/inventory/bulk-update",
            json=[
                {
                    "sku_id":"CON1",
                    "warehouse_id":"WH001",
                    "quantity_delta":-1
                }
            ]
        )

        assert response.status_code==200



    threads=[]


    for _ in range(10):

        t=threading.Thread(
            target=decrease
        )

        threads.append(t)
        t.start()



    for t in threads:
        t.join()



    response=client.get(
        "/api/v1/inventory/CON1/WH001"
    )


    assert response.json()["quantity_on_hand"]==0