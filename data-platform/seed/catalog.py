"""Reference data: warehouses, suppliers, SKUs.

All randomness comes from the Generator passed in, so output depends only on
the seed. Warehouses are a fixed list (no randomness) and sorted by ID.
"""

import numpy as np
import pandas as pd

from . import ids

N_SKUS = 500
N_SUPPLIERS = 60

# (city_code, name, city, state, lat, lng, capacity_units, demand_weight)
_WAREHOUSES = [
    ("BLR", "Bengaluru DC", "Bengaluru", "Karnataka", 12.9716, 77.5946, 120_000, 1.25),
    ("BOM", "Mumbai DC", "Bhiwandi", "Maharashtra", 19.3002, 73.0581, 130_000, 1.20),
    ("CCU", "Kolkata DC", "Kolkata", "West Bengal", 22.5726, 88.3639, 80_000, 0.80),
    ("DEL", "Delhi NCR DC", "Gurugram", "Haryana", 28.4595, 77.0266, 140_000, 1.30),
    ("HYD", "Hyderabad DC", "Hyderabad", "Telangana", 17.3850, 78.4867, 100_000, 1.00),
    ("MAA", "Chennai DC", "Chennai", "Tamil Nadu", 13.0827, 80.2707, 90_000, 0.85),
]


# Real Indian city coordinates (latitude, longitude), WGS84 decimal degrees.
# Supplier cities are assigned by the seeded RNG, across 14 distinct cities.
_SUPPLIER_CITIES = [
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
    ("Kochi", "Kerala", 9.9312, 76.2673),
    ("Indore", "Madhya Pradesh", 22.7196, 75.8577),
    ("Bhubaneswar", "Odisha", 20.2961, 85.8245),
    ("Guwahati", "Assam", 26.1445, 91.7362),
]

# Fixed on purpose: downstream compliance tests can hard-code these three IDs.
SANCTIONED = {
    ids.supplier_id(7): ("ALPHA SANCTIONS CORP", "Russia", "OFAC-SDN"),
    ids.supplier_id(23): ("TEST EU ENTITY 01", "Iran", "EU-CONSOLIDATED"),
    ids.supplier_id(45): ("TEST UN ENTITY 01", "Belarus", "UN-SC"),
}

_NAME_A = ["Apex", "Bluepeak", "Cedar", "Driftwood", "Evergreen", "Falcon", "Granite", "Harbor",
           "Ironwood", "Juniper", "Keystone", "Lotus", "Meridian", "Nimbus", "Orion", "Pioneer",
           "Quartz", "Redwood", "Summit", "Tidal", "Unity", "Vertex", "Willow", "Zenith"]
_NAME_B = ["Supplies", "Traders", "Industries", "Distribution", "Wholesale", "Sourcing",
           "Manufacturing", "Logistics", "Enterprises", "Exports"]
_NAME_C = ["Pvt Ltd", "Ltd", "LLP", "Co", "GmbH", "Inc"]
_COUNTRIES = ["India"] * 6 + ["China", "Vietnam", "Taiwan", "UAE", "Germany", "Malaysia", "Thailand"]

_BRANDS = ["Northwind", "Kestrel", "Lumina", "Brightline", "Ardent", "Solis"]

# category -> (items, pack sizes, (min_price, max_price)). Pack sizes are
# category-specific so we never get "Marker Set 500 ml".
_CATEGORIES = {
    "Stationery": (
        ["Gel Pen", "Marker Set", "A4 Notebook", "Stapler", "Sticky Notes", "File Folder"],
        ["Pack of 5", "Pack of 10", "Pack of 25"], (40, 600)),
    "Cleaning": (
        ["Floor Cleaner", "Hand Wash", "Disinfectant Spray", "Glass Cleaner", "Dish Liquid", "Sanitizer"],
        ["500 ml", "1 L", "5 L"], (80, 1100)),
    "Packaging": (
        ["Packing Tape", "Bubble Wrap", "Stretch Film", "Corrugated Box", "Mailer Bag", "Label Roll"],
        ["Roll of 50 m", "Pack of 100", "Carton of 250"], (120, 2200)),
    "Electronics Accessories": (
        ["USB-C Cable", "Power Adapter", "HDMI Cable", "Wireless Mouse", "Keyboard", "Laptop Stand"],
        ["1 pc", "Pack of 2", "Pack of 5"], (250, 6500)),
    "Safety": (
        ["Safety Gloves", "Face Mask", "Safety Goggles", "Hard Hat", "Ear Plugs", "Hi-Vis Vest"],
        ["Pair", "Pack of 10", "Box of 50"], (60, 1800)),
    "Office Furniture": (
        ["Desk Organizer", "Monitor Riser", "Footrest", "Filing Cabinet", "Whiteboard", "Task Chair"],
        ["1 pc", "Set of 2", "Set of 4"], (700, 14000)),
}

_ABC_SHARES = (("A", 50), ("B", 100), ("C", 350))  # sums to N_SKUS


def warehouses() -> pd.DataFrame:
    rows = [
        {"warehouse_id": ids.warehouse_id(code, 1), "name": name, "city": city, "state": state,
         "lat": lat, "lng": lng, "capacity_units": cap, "demand_weight": w}
        for code, name, city, state, lat, lng, cap, w in _WAREHOUSES
    ]
    return pd.DataFrame(rows).sort_values("warehouse_id").reset_index(drop=True)


def suppliers(rng: np.random.Generator) -> pd.DataFrame:
    n_clean = N_SUPPLIERS - len(SANCTIONED)
    combos = [(a, b, c) for a in _NAME_A for b in _NAME_B for c in _NAME_C]
    picks = rng.choice(len(combos), size=n_clean, replace=False)
    clean_names = iter(" ".join(combos[i]) for i in picks)
    clean_countries = iter(rng.choice(_COUNTRIES, size=n_clean))

    # Locations are assigned with the same seeded generator as the rest of the supplier
    # attributes; every run with the same seed gets identical city/state/coordinates.
    city_indexes = np.tile(
        np.arange(len(_SUPPLIER_CITIES)),
        int(np.ceil(N_SUPPLIERS / len(_SUPPLIER_CITIES))),
    )[:N_SUPPLIERS]
    rng.shuffle(city_indexes)  # every configured city is represented; ordering is still seeded
    rows = []
    for n in range(1, N_SUPPLIERS + 1):
        sid = ids.supplier_id(n)
        city, state, lat, lng = _SUPPLIER_CITIES[int(city_indexes[n - 1])]
        if sid in SANCTIONED:
            name, country, lst = SANCTIONED[sid]
            flagged = True
        else:
            name, country, lst, flagged = next(clean_names), str(next(clean_countries)), "", False
        rows.append({"supplier_id": sid, "name": name, "country": country,
                     "city": city, "state": state, "lat": lat, "lng": lng,
                     "sanctions_flag": flagged, "sanctions_list": lst})
    df = pd.DataFrame(rows)
    df["lead_time_days"] = rng.integers(3, 46, size=len(df)).astype("int32")
    df["payment_terms_days"] = rng.choice([15, 30, 45, 60], size=len(df)).astype("int32")
    df["reliability_score"] = np.round(rng.uniform(0.70, 0.99, size=len(df)), 2)
    return df


def skus(rng: np.random.Generator, supplier_ids: list[str]) -> pd.DataFrame:
    cats = list(_CATEGORIES)
    per_cat = [N_SKUS // len(cats) + (1 if i < N_SKUS % len(cats) else 0) for i in range(len(cats))]

    rows = []
    for cat, count in zip(cats, per_cat):
        items, packs, (lo, hi) = _CATEGORIES[cat]
        combos = [(b, i, p) for b in _BRANDS for i in items for p in packs]
        for k in rng.choice(len(combos), size=count, replace=False):
            brand, item, pack = combos[k]
            price = float(np.round(np.exp(rng.uniform(np.log(lo), np.log(hi))), 0))
            rows.append({
                "name": f"{brand} {item} - {pack}", "category": cat, "pack_size": pack,
                "unit_price": price,
                "unit_cost": float(np.round(price * rng.uniform(0.55, 0.80), 2)),
            })

    # Shuffle so category isn't correlated with SKU number, then number them.
    order = rng.permutation(len(rows))
    df = pd.DataFrame([rows[i] for i in order])
    df.insert(0, "sku_id", [ids.sku_id(n) for n in range(1, len(df) + 1)])

    abc = np.array([c for c, k in _ABC_SHARES for _ in range(k)])
    df["abc_class"] = rng.permutation(abc)
    df["supplier_id"] = rng.choice(supplier_ids, size=len(df))
    return df
