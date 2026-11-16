import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(322)

OUT = Path(__file__).parent / "samples" / "client_format"
OUT.mkdir(parents=True, exist_ok=True)
TODAY = date(2026, 11, 10)

def write(name, rows):
    path = OUT / f"{name}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{name}.csv: {len(rows)} rows")

products = [
    {"product_code": f"PRD-{10482+i}", "product_name": f"Product {i+1}",
     "category": ["Electronics", "Grocery", "Household", "Apparel", "Hardware"][i%5],
     "unit_of_measure": "PCS", "unit_price": round(random.uniform(50,5000),2),
     "is_active": "true"} for i in range(50)
]

warehouses = [
    {"warehouse_code": code, "warehouse_name": f"{city} Distribution Centre",
     "city": city, "state": state, "country": "India",
     "pincode": pin, "warehouse_type": "Regional"}
    for code,city,state,pin in [
        ("HYD-01","Hyderabad","Telangana","500001"),
        ("BLR-01","Bengaluru","Karnataka","560001"),
        ("MUM-01","Mumbai","Maharashtra","400001"),
        ("DEL-01","New Delhi","Delhi","110001"),
        ("CHE-01","Chennai","Tamil Nadu","600001")
    ]
]

suppliers = [
    {"supplier_code":f"SUP-{2231+i}", "supplier_name":f"Supplier {i+1}",
     "city":["Hyderabad","Mumbai","Pune","Bengaluru","Chennai"][i%5],
     "state":["Telangana","Maharashtra","Maharashtra","Karnataka","Tamil Nadu"][i%5],
     "contact_email":f"supplier{i+1}@example.test",
     "phone":f"90000{i+1:05d}",
     "is_active":"true"} for i in range(20)
]

carriers = [
    {"carrier_code":"CAR-01","carrier_name":"Express Logistics","carrier_type":"Express","base_late_rate":0.04,"is_active":"true"},
    {"carrier_code":"CAR-02","carrier_name":"National Freight","carrier_type":"Road","base_late_rate":0.21,"is_active":"true"},
    {"carrier_code":"CAR-03","carrier_name":"Regional Transport","carrier_type":"Road","base_late_rate":0.47,"is_active":"true"},
    {"carrier_code":"CAR-04","carrier_name":"Air Cargo","carrier_type":"Air","base_late_rate":0.04,"is_active":"true"}
]

write("product_master", products + [
    {**products[0], "product_code":"PRD-99901", "product_name":""},
    {**products[1], "product_code":"PRD-99902", "unit_price":-10}
])
write("warehouse_master", warehouses + [
    {**warehouses[0], "warehouse_code":"BAD-901", "pincode":""},
    {**warehouses[1], "warehouse_code":"BAD-902", "country":""}
])
write("supplier_master", suppliers + [
    {**suppliers[0], "supplier_code":"SUP-9991", "supplier_name":""},
    {**suppliers[1], "supplier_code":"SUP-9992", "contact_email":"bad-email"}
])
write("carriers", carriers + [
    {**carriers[0], "carrier_code":"CAR-98", "carrier_name":""},
    {**carriers[1], "carrier_code":"CAR-99", "base_late_rate":1.5}
])

# Complete daily series: 10 products x 5 warehouses x 549 days.
sales = []
start_sales = date(2025,5,10)
for day_index in range(549):
    day = start_sales + timedelta(days=day_index)
    for p in products[:10]:
        for wh in warehouses:
            weekly_factor = 1.25 if day.weekday() in (4,5) else 0.85
            qty = 0 if random.random() < 0.08 else max(1, round(random.randint(3,20)*weekly_factor))
            price = float(p["unit_price"])
            sales.append({
                "sale_date":day.isoformat(),
                "product_code":p["product_code"],
                "warehouse_code":wh["warehouse_code"],
                "quantity_sold":qty,
                "unit_price":price,
                "sales_amount":round(qty*price,2),
                "order_number":f"ORD-{day_index:04d}-{p['product_code']}-{wh['warehouse_code']}"
            })

sales.extend([
    {**sales[0], "order_number":"ORD-99901", "product_code":""},
    {**sales[1], "order_number":"ORD-99902", "sale_date":"BAD-DATE"},
    {**sales[2], "order_number":"ORD-99903", "product_code":"PRD-99999"},
    {**sales[3], "order_number":"ORD-99904", "quantity_sold":-10}
])
write("sales_history", sales)

inventory = []
for p in products:
    for wh in warehouses:
        inventory.append({
            "snapshot_date":"2026-11-09",
            "product_code":p["product_code"],
            "warehouse_code":wh["warehouse_code"],
            "quantity_on_hand":random.randint(0,1000),
            "quantity_reserved":random.randint(0,100),
            "reorder_point":random.randint(20,100),
            "safety_stock":random.randint(10,50) if random.random() > .2 else ""
        })
inventory.extend([
    {**inventory[0], "product_code":"PRD-99903"},
    {"snapshot_date":"2026-11-08", **inventory[1], "quantity_on_hand":-5}
])
write("inventory_snapshot", inventory)

lead_times = []
for supplier in suppliers:
    for product in random.sample(products,5):
        low = random.randint(2,7)
        high = low + random.randint(5,15)
        lead_times.append({
            "supplier_code":supplier["supplier_code"],
            "product_code":product["product_code"],
            "average_lead_time_days":(low+high)//2,
            "minimum_lead_time_days":low,
            "maximum_lead_time_days":high,
            "effective_date":"2026-01-01"
        })
lead_times.extend([
    {**lead_times[0], "supplier_code":"SUP-9993"},
    {**lead_times[1], "product_code":"PRD-99999"}
])
write("supplier_lead_times", lead_times)

incidents = []
for i in range(40):
    supplier = random.choice(suppliers)
    incidents.append({
        "incident_id":f"INC-{i+1:06d}",
        "supplier_code":supplier["supplier_code"],
        "incident_date":(date(2026,1,1)+timedelta(days=i*7)).isoformat(),
        "incident_type":random.choice(["Quality","Delay","Compliance","Packaging"]),
        "severity":random.choice(["low","medium","high"]),
        "description":f"Synthetic incident {i+1}",
        "resolved":str(i%3 != 0).lower()
    })
incidents.extend([
    {**incidents[0], "incident_id":"INC-999901", "supplier_code":"SUP-9994"},
    {**incidents[1], "incident_id":"INC-999902", "incident_date":"BAD-DATE"}
])
write("supplier_incidents", incidents)

po_history = []
shipments = []
po_start = date(2025,11,10)
shipment_number = 778120

for i in range(365):
    product = random.choice(products)
    warehouse = random.choice(warehouses)
    supplier = random.choice(suppliers)
    carrier = random.choice(carriers)
    order_date = po_start + timedelta(days=i)
    expected = order_date + timedelta(days=random.randint(5,15))
    po_number = f"PO-{55120+i}"
    qty = random.randint(10,500)

    # 338 received, 12 open (in transit) and 15 cancelled.
    status = "Received" if i < 338 else ("Open" if i < 350 else "Cancelled")

    # Decide lateness first, then derive the delivery date from it.
    route_factor = 1.4 if warehouse["city"] in ("New Delhi","Chennai") and carrier["carrier_type"] == "Road" else 1.0
    late_probability = min(carrier["base_late_rate"]*route_factor,.8)
    is_late = random.random() < late_probability
    delay_days = random.randint(1,8) if is_late else random.randint(-2,0)
    received = expected + timedelta(days=delay_days) if status == "Received" else None

    po_history.append({
        "po_number":po_number,
        "supplier_code":supplier["supplier_code"],
        "product_code":product["product_code"],
        "warehouse_code":warehouse["warehouse_code"],
        "order_date":order_date.isoformat(),
        "expected_date":expected.isoformat(),
        "received_date":received.isoformat() if received else "",
        "quantity_ordered":qty,
        "unit_cost":round(float(product["unit_price"])*.8,2),
        "po_status":status
    })

    if status == "Cancelled":
        continue


    # The final 12 non-cancelled records remain in transit.
    in_transit = i >= 338
    actual = None if in_transit else received
    shipment_status = "In Transit" if in_transit else ("Delayed" if is_late else "Delivered")

    shipment_number += 1
    shipments.append({
        "shipment_id":f"SH-{shipment_number}",
        "po_number":po_number,
        "origin_city":supplier["city"],
        "destination_warehouse_code":warehouse["warehouse_code"],
        "carrier_name":carrier["carrier_name"],
        "dispatch_date":order_date.isoformat(),
        "planned_delivery_date":expected.isoformat(),
        "actual_delivery_date":actual.isoformat() if actual else "",
        "weight_kg":round(random.uniform(2,800),2) if i%30 else "",
        "volume_m3":round(random.uniform(.01,8),3) if i%30 else "",
        "supplier_code":supplier["supplier_code"],
        "product_code":product["product_code"],
        "shipment_status":shipment_status,
        "quantity_shipped":qty
    })

po_history.extend([
    {**po_history[0], "po_number":"PO-99901", "supplier_code":""},
    {**po_history[1], "po_number":"PO-99902", "expected_date":"BAD-DATE"},
    {**po_history[2], "po_number":"PO-99903", "quantity_ordered":-5}
])
shipments.extend([
    {**shipments[0], "shipment_id":"SH-999901", "product_code":"PRD-99999"},
    {**shipments[1], "shipment_id":"SH-999902", "actual_delivery_date":"BAD-DATE"},
    {**shipments[2], "shipment_id":"SH-999903", "quantity_shipped":-5}
])
write("purchase_order_history", po_history)
write("shipment_history", shipments)

readme = """# Synthetic Client Format Samples

All records are synthetic. No real client data is included.

## Files and rows
- product_master.csv: 50 products plus 2 invalid rows.
- warehouse_master.csv: 5 Indian warehouses plus 2 invalid rows.
- supplier_master.csv: 20 suppliers plus 2 invalid rows.
- carriers.csv: 4 carriers with different late rates plus 2 invalid rows.
- sales_history.csv: 10 products x 5 warehouses x 549 daily dates, plus 4 invalid rows.
- inventory_snapshot.csv: 250 product/warehouse combinations plus 2 invalid rows.
- supplier_lead_times.csv: 100 supplier/product combinations plus 2 invalid rows.
- supplier_incidents.csv: 40 incidents plus 2 invalid rows.
- purchase_order_history.csv: 365 purchase orders plus 3 invalid rows.
- shipment_history.csv: 350 shipments plus 3 invalid rows.

## Invalid rows
- product_master: missing product_name; negative unit_price.
- warehouse_master: missing pincode; missing country.
- supplier_master: missing supplier_name; malformed contact_email.
- carriers: missing carrier_name; base_late_rate above 1.
- sales_history: missing product_code; invalid sale_date; unknown product_code PRD-99999; negative quantity_sold.
- inventory_snapshot: unknown product_code PRD-99903; negative quantity_on_hand.
- supplier_lead_times: unknown supplier_code SUP-9993; unknown product_code PRD-99999.
- supplier_incidents: unknown supplier_code SUP-9994; invalid incident_date.
- purchase_order_history: missing supplier_code; invalid expected_date; negative quantity_ordered.
- shipment_history: unknown product_code PRD-99999; invalid actual_delivery_date; negative quantity_shipped.

## Identifiers
Client identifiers are retained in source files. Canonical platform IDs are assigned during ingestion using spec.yaml mappings.

## Shipment lateness
Carrier-specific late rates are used. Road routes to New Delhi and Chennai have an additional route factor. Twelve shipments remain In Transit with blank actual_delivery_date.

## Schema qualification
Fields marked inferred in spec.yaml must be confirmed against the original client document before production ingestion.
"""
(OUT / "README.md").write_text(readme, encoding="utf-8")
print("Synthetic client files generated successfully.")
