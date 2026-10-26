#!/usr/bin/env python3
"""
Generate clean, 100% consistent canonical seed data into data-platform/out/
without requiring external dependencies like pandas/numpy.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OUT_DIR = REPO_ROOT / "data-platform" / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)

random.seed(42)

# 1. Warehouses (6 canonical warehouses)
WAREHOUSES = [
    ("WH-BLR-01", "Bengaluru DC", "Bengaluru", "Karnataka", 12.9716, 77.5946, 120000, 1.25),
    ("WH-BOM-01", "Mumbai DC", "Bhiwandi", "Maharashtra", 19.3002, 73.0581, 130000, 1.20),
    ("WH-CCU-01", "Kolkata DC", "Kolkata", "West Bengal", 22.5726, 88.3639, 80000, 0.80),
    ("WH-DEL-01", "Delhi NCR DC", "Gurugram", "Haryana", 28.4595, 77.0266, 140000, 1.30),
    ("WH-HYD-01", "Hyderabad DC", "Hyderabad", "Telangana", 17.3850, 78.4867, 100000, 1.00),
    ("WH-MAA-01", "Chennai DC", "Chennai", "Tamil Nadu", 13.0827, 80.2707, 90000, 0.85),
]

with open(OUT_DIR / "warehouses.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["warehouse_id", "name", "city", "state", "lat", "lng", "capacity_units", "demand_weight"])
    writer.writerows(WAREHOUSES)

# 2. Suppliers (60 canonical suppliers including 3 sanctioned ones)
SANCTIONED = {
    7: ("ALPHA SANCTIONS CORP", "Russia", "OFAC-SDN"),
    23: ("TEST EU ENTITY 01", "Iran", "EU-CONSOLIDATED"),
    45: ("TEST UN ENTITY 01", "Belarus", "UN-SC"),
}

SUPPLIER_CITIES = [
    ("Bengaluru", "Karnataka", 12.9716, 77.5946),
    ("Hyderabad", "Telangana", 17.3850, 78.4867),
    ("Chennai", "Tamil Nadu", 13.0827, 80.2707),
    ("Mumbai", "Maharashtra", 19.0760, 72.8777),
    ("Pune", "Maharashtra", 18.5204, 73.8567),
    ("New Delhi", "Delhi", 28.6139, 77.2090),
    ("Kolkata", "West Bengal", 22.5726, 88.3639),
    ("Ahmedabad", "Gujarat", 23.0225, 72.5714),
    ("Jaipur", "Rajasthan", 26.9124, 75.7873),
    ("Lucknow", "Uttar Pradesh", 26.8467, 80.9462),
]

SUPPLIER_NAMES = [
    "Apex", "Bluepeak", "Cedar", "Evergreen", "Falcon", "Granite", "Ironwood",
    "Juniper", "Keystone", "Lotus", "Meridian", "Nimbus", "Orion", "Pioneer",
    "Quartz", "Redwood", "Summit", "Tidal", "Unity", "Vertex", "Willow", "Zenith"
]
SUPPLIER_TYPES = ["Supplies", "Traders", "Industries", "Enterprises", "Manufacturing"]
SUPPLIER_SUFFIX = ["Pvt Ltd", "Ltd", "LLP", "Co", "Inc"]

suppliers_data = []
supplier_ids = []
for n in range(1, 61):
    sid = f"SUP-{n:05d}"
    supplier_ids.append(sid)
    city_info = SUPPLIER_CITIES[n % len(SUPPLIER_CITIES)]
    city, state, lat, lng = city_info
    
    if n in SANCTIONED:
        name, country, s_list = SANCTIONED[n]
        flagged = True
    else:
        name = f"{random.choice(SUPPLIER_NAMES)} {random.choice(SUPPLIER_TYPES)} {random.choice(SUPPLIER_SUFFIX)}"
        country = "India" if n % 5 != 0 else random.choice(["China", "Vietnam", "Taiwan", "Germany"])
        s_list = ""
        flagged = False
        
    lead_time = random.randint(5, 30)
    pay_terms = random.choice([15, 30, 45, 60])
    rel_score = round(random.uniform(0.75, 0.99), 2)
    
    suppliers_data.append([
        sid, name, country, city, state, lat, lng,
        flagged, s_list, lead_time, pay_terms, rel_score
    ])

with open(OUT_DIR / "suppliers.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "supplier_id", "name", "country", "city", "state", "lat", "lng",
        "sanctions_flag", "sanctions_list", "lead_time_days", "payment_terms_days", "reliability_score"
    ])
    writer.writerows(suppliers_data)

# 3. SKUs (50 canonical SKUs)
CATEGORIES = {
    "Stationery": (["Gel Pen", "Marker Set", "A4 Notebook", "Stapler", "Sticky Notes"], ["Pack of 5", "Pack of 10", "Pack of 25"], (40.0, 400.0)),
    "Cleaning": (["Floor Cleaner", "Hand Wash", "Disinfectant Spray", "Glass Cleaner", "Dish Liquid"], ["500 ml", "1 L", "5 L"], (80.0, 800.0)),
    "Packaging": (["Packing Tape", "Bubble Wrap", "Stretch Film", "Corrugated Box"], ["Roll of 50 m", "Pack of 100"], (120.0, 1500.0)),
    "Electronics Accessories": (["USB-C Cable", "Power Adapter", "HDMI Cable", "Wireless Mouse"], ["1 pc", "Pack of 2"], (250.0, 3000.0)),
    "Office Furniture": (["Desk Organizer", "Monitor Riser", "Footrest", "Task Chair"], ["1 pc", "Set of 2"], (700.0, 8000.0)),
}

BRANDS = ["Northwind", "Kestrel", "Lumina", "Brightline", "Ardent", "Solis"]
ABC_CLASSES = ["A"] * 10 + ["B"] * 15 + ["C"] * 25

skus_data = []
sku_ids = []
sku_price_map = {}

cat_keys = list(CATEGORIES.keys())
for n in range(1, 51):
    sku_id = f"SKU-{n:06d}"
    sku_ids.append(sku_id)
    cat = cat_keys[(n - 1) % len(cat_keys)]
    items, packs, (min_p, max_p) = CATEGORIES[cat]
    
    brand = BRANDS[n % len(BRANDS)]
    item = items[n % len(items)]
    pack = packs[n % len(packs)]
    name = f"{brand} {item} - {pack}"
    
    price = round(random.uniform(min_p, max_p), 2)
    cost = round(price * random.uniform(0.55, 0.75), 2)
    abc = ABC_CLASSES[n - 1]
    sup = supplier_ids[n % len(supplier_ids)]
    
    sku_price_map[sku_id] = price
    skus_data.append([sku_id, name, cat, pack, price, cost, abc, sup])

with open(OUT_DIR / "skus.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["sku_id", "name", "category", "pack_size", "unit_price", "unit_cost", "abc_class", "supplier_id"])
    writer.writerows(skus_data)

# 4. Sales Daily (past 30 days for each SKU x Warehouse)
END_DATE = date(2026, 10, 14)
sales_data = []

wh_ids = [w[0] for w in WAREHOUSES]

for day_offset in range(30, 0, -1):
    current_date = (END_DATE - timedelta(days=day_offset)).isoformat()
    for sku_id in sku_ids:
        price = sku_price_map[sku_id]
        for wh_id in wh_ids:
            # Poisson-like demand
            qty_sold = random.choices([0, 1, 2, 3, 5, 8, 12], weights=[20, 25, 20, 15, 10, 7, 3])[0]
            sales_data.append([current_date, sku_id, wh_id, qty_sold, price])

with open(OUT_DIR / "sales_daily.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["date", "sku_id", "warehouse_id", "quantity_sold", "unit_price"])
    writer.writerows(sales_data)

# 5. Current Stock (Snapshot on 2026-10-14 for all SKUs x Warehouses)
current_stock_data = []
SNAPSHOT_DATE = "2026-10-14"

for sku_id in sku_ids:
    for wh_id in wh_ids:
        # Stock between 50 and 300 units
        qty = random.randint(50, 250)
        current_stock_data.append([SNAPSHOT_DATE, sku_id, wh_id, qty])

with open(OUT_DIR / "current_stock.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["snapshot_date", "sku_id", "warehouse_id", "quantity_on_hand"])
    writer.writerows(current_stock_data)

print(f"Canonical seed generated successfully into {OUT_DIR}:")
print(f" - {len(WAREHOUSES)} warehouses")
print(f" - {len(suppliers_data)} suppliers")
print(f" - {len(skus_data)} SKUs")
print(f" - {len(sales_data)} sales history rows")
print(f" - {len(current_stock_data)} current stock rows")

