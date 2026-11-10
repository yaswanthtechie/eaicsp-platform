import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(322)

OUT = Path(__file__).parent / "samples" / "client_format"
OUT.mkdir(parents=True, exist_ok=True)

def write(name, rows):
    path = OUT / f"{name}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{name}.csv: {len(rows)} rows")

products = [
    {"product_code": f"PRD-{10482+i}", "product_name": f"Product {i+1}",
     "category": ["Electronics", "Grocery", "Household", "Apparel", "Hardware"][i%5],
     "unit_of_measure": "PCS", "unit_price": round(random.uniform(50, 5000), 2),
     "is_active": "true"} for i in range(50)
]

warehouses = [
    {"warehouse_code": code, "warehouse_name": f"{city} Distribution Centre",
     "city": city, "state": state, "pincode": pin, "warehouse_type": "Regional"}
    for code, city, state, pin in [
        ("HYD-01","Hyderabad","Telangana","500001"),
        ("BLR-01","Bengaluru","Karnataka","560001"),
        ("MUM-01","Mumbai","Maharashtra","400001"),
        ("DEL-01","New Delhi","Delhi","110001"),
        ("CHE-01","Chennai","Tamil Nadu","600001")
    ]
]

suppliers = [
    {"supplier_code": f"SUP-{2231+i}", "supplier_name": f"Supplier {i+1}",
     "city": ["Hyderabad","Mumbai","Pune","Bengaluru","Chennai"][i%5],
     "state": ["Telangana","Maharashtra","Maharashtra","Karnataka","Tamil Nadu"][i%5],
     "contact_email": f"supplier{i+1}@example.test",
     "phone": f"9{random.randint(100000000,999999999)}",
     "is_active": "true"} for i in range(20)
]

carriers = [
    {"carrier_code":"CAR-01","carrier_name":"Express Logistics","carrier_type":"Express","base_late_rate":0.08,"is_active":"true"},
    {"carrier_code":"CAR-02","carrier_name":"National Freight","carrier_type":"Road","base_late_rate":0.22,"is_active":"true"},
    {"carrier_code":"CAR-03","carrier_name":"Regional Transport","carrier_type":"Road","base_late_rate":0.35,"is_active":"true"},
    {"carrier_code":"CAR-04","carrier_name":"Air Cargo","carrier_type":"Air","base_late_rate":0.04,"is_active":"true"}
]

write("product_master", products + [
    {**products[0], "product_name": ""},
    {**products[1], "unit_price": -10}
])
write("warehouse_master", warehouses + [
    {**warehouses[0], "pincode": ""},
    {**warehouses[1], "warehouse_code": ""}
])
write("supplier_master", suppliers + [
    {**suppliers[0], "supplier_name": ""},
    {**suppliers[1], "contact_email": "bad-email"}
])
write("carriers", carriers + [
    {**carriers[0], "carrier_name": ""},
    {**carriers[1], "base_late_rate": 1.5}
])

start_sales = date(2025, 5, 10)
end_date = date(2026, 11, 9)
sales = []
day = start_sales
order = 10000

while day <= end_date:
    for _ in range(5):
        p = random.choice(products)
        wh = random.choice(warehouses)
        qty = random.randint(1, 30)
        price = float(p["unit_price"])
        order += 1
        sales.append({
            "sale_date":day.isoformat(),
            "product_code":p["product_code"],
            "warehouse_code":wh["warehouse_code"],
            "quantity_sold":qty,
            "unit_price":price,
            "sales_amount":round(qty*price,2),
            "order_number":f"ORD-{order}"
        })
    day += timedelta(days=1)

sales.extend([
    {**sales[0], "product_code": ""},
    {**sales[1], "sale_date": "BAD-DATE"},
    {**sales[2], "product_code": "PRD-99999"},
    {**sales[3], "quantity_sold": -10}
])
write("sales_history", sales)

snapshots = []
for p in products:
    for wh in warehouses:
        snapshots.append({
            "snapshot_date":"2026-11-09",
            "product_code":p["product_code"],
            "warehouse_code":wh["warehouse_code"],
            "quantity_on_hand":random.randint(0,1000),
            "quantity_reserved":random.randint(0,100),
            "reorder_level":random.randint(20,100)
        })
snapshots.extend([
    {**snapshots[0], "product_code":""},
    {**snapshots[1], "quantity_on_hand":-5}
])
write("inventory_snapshot", snapshots)

lead_times = []
for s in suppliers:
    for p in random.sample(products, 5):
        minimum = random.randint(2,7)
        maximum = minimum + random.randint(5,15)
        lead_times.append({
            "supplier_code":s["supplier_code"],
            "product_code":p["product_code"],
            "average_lead_time_days":(minimum+maximum)//2,
            "minimum_lead_time_days":minimum,
            "maximum_lead_time_days":maximum,
            "effective_date":"2026-01-01"
        })
lead_times.extend([
    {**lead_times[0], "supplier_code":""},
    {**lead_times[1], "product_code":"PRD-99999"}
])
write("supplier_lead_times", lead_times)

incidents = []
for i in range(40):
    s = random.choice(suppliers)
    incidents.append({
        "incident_id":f"INC-{i+1:06d}",
        "supplier_code":s["supplier_code"],
        "incident_date":(date(2026,1,1)+timedelta(days=i*7)).isoformat(),
        "incident_type":random.choice(["Quality","Delay","Compliance","Packaging"]),
        "severity":random.choice(["low","medium","high"]),
        "description":f"Synthetic incident {i+1}",
        "resolved":str(i%3 != 0).lower()
    })
incidents.extend([
    {**incidents[0], "supplier_code":""},
    {**incidents[1], "incident_date":"BAD-DATE"}
])
write("supplier_incidents", incidents)

po_history = []
shipments = []
start = date(2025,11,10)

for i in range(365):
    p = random.choice(products)
    wh = random.choice(warehouses)
    s = random.choice(suppliers)
    carrier = random.choice(carriers)
    order_date = start + timedelta(days=i)
    planned = order_date + timedelta(days=random.randint(5,15))

    po_number = f"PO-{55120+i}"
    qty = random.randint(10,500)

    po_history.append({
        "po_number":po_number,
        "supplier_code":s["supplier_code"],
        "product_code":p["product_code"],
        "warehouse_code":wh["warehouse_code"],
        "order_date":order_date.isoformat(),
        "planned_delivery_date":planned.isoformat(),
        "quantity_ordered":qty,
        "unit_cost":round(float(p["unit_price"])*0.8,2),
        "po_status":"Delivered"
    })

    route_factor = 1.4 if wh["city"] in ["Delhi","Chennai"] and carrier["carrier_type"]=="Road" else 1.0
    late_probability = min(float(carrier["base_late_rate"])*route_factor, 0.8)
    is_late = random.random() < late_probability
    actual = planned + timedelta(days=random.randint(1,8) if is_late else random.randint(-2,0))

    shipments.append({
        "shipment_id":f"SH-{778120+i}",
        "po_number":po_number,
        "supplier_code":s["supplier_code"],
        "product_code":p["product_code"],
        "warehouse_code":wh["warehouse_code"],
        "carrier_code":carrier["carrier_code"],
        "dispatch_date":order_date.isoformat(),
        "planned_delivery_date":planned.isoformat(),
        "actual_delivery_date":actual.isoformat(),
        "shipment_status":"Delayed" if is_late else "Delivered",
        "quantity_shipped":qty
    })

po_history.extend([
    {**po_history[0], "supplier_code":""},
    {**po_history[1], "planned_delivery_date":"BAD-DATE"},
    {**po_history[2], "quantity_ordered":-5}
])
shipments.extend([
    {**shipments[0], "product_code":"PRD-99999"},
    {**shipments[1], "actual_delivery_date":"BAD-DATE"},
    {**shipments[2], "quantity_shipped":-5}
])
write("purchase_order_history", po_history)
write("shipment_history", shipments)

# Document intentionally invalid test rows.
readme = """# Synthetic Client Format Samples

All files in this directory are synthetic. No real client records are included.

## Files
- product_master.csv: 50 products plus 2 invalid rows.
- warehouse_master.csv: 5 Indian warehouses.
- supplier_master.csv: 20 suppliers.
- carriers.csv: 4 carriers with different late rates.
- sales_history.csv: 18 months of daily sales, 5 records per day, plus 4 invalid rows.
- inventory_snapshot.csv: 250 product/warehouse combinations plus 2 invalid rows.
- supplier_lead_times.csv: 100 supplier/product combinations plus 2 invalid rows.
- supplier_incidents.csv: 40 incidents plus 2 invalid rows.
- shipment_history.csv: 365 shipments plus 3 invalid rows.
- purchase_order_history.csv: 365 purchase orders plus 3 invalid rows.

## Deliberately invalid rows
- sales_history: missing product_code; invalid sale_date; unknown product_code PRD-99999; negative quantity_sold.
- inventory_snapshot: missing product_code; negative quantity_on_hand.
- supplier_lead_times: missing supplier_code; unknown product_code PRD-99999.
- supplier_incidents: missing supplier_code; invalid incident_date.
- shipment_history: unknown product_code PRD-99999; invalid actual_delivery_date; negative quantity_shipped.
- purchase_order_history: missing supplier_code; invalid planned_delivery_date; negative quantity_ordered.

## Other master files
product_master, warehouse_master, supplier_master and carriers contain valid synthetic records only.

## Identifier rules
Client codes are used throughout. Canonical platform IDs such as SKU-000123 and WH-BLR-01 are not included in these files. Mapping happens during ingestion.

## Shipment lateness
Carrier late rates differ. Route factors also influence the probability of delay. All dates and records are synthetic.

## Schema qualification
spec.yaml contains inferred fields where the original client column document was unavailable. Confirm those fields before production ingestion.
"""
(OUT / "README.md").write_text(readme, encoding="utf-8")

print("\nSynthetic client files generated successfully.")
