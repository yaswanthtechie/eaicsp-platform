"""Canonical ID formats (integration blueprint, section 2).

    SKU-000123   zero-padded to 6 digits
    WH-BLR-01    WH-<3-letter city code>-<2-digit site number>
    SUP-00045    zero-padded to 5 digits

Everything that mints or validates an ID in the seed goes through this module,
so the format lives in exactly one place.
"""

import re

SKU_RE = re.compile(r"^SKU-\d{6}$")
WH_RE = re.compile(r"^WH-[A-Z]{3}-\d{2}$")
SUP_RE = re.compile(r"^SUP-\d{5}$")


def sku_id(n: int) -> str:
    return f"SKU-{n:06d}"


def supplier_id(n: int) -> str:
    return f"SUP-{n:05d}"


def warehouse_id(city_code: str, site: int = 1) -> str:
    return f"WH-{city_code}-{site:02d}"
