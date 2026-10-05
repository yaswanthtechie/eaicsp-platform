#!/usr/bin/env python3
"""
Benchmark script for measuring inventory read latency with and without Redis caching.

Usage:
    python scripts/benchmark_cache_latency.py [--iterations N] [--redis-url URL]

Measures:
    - Uncached database read latency (direct PostgreSQL / SQLite query)
    - Cached Redis read latency (serialized hot-read hit)
    - Speedup factor and percentile latency distributions
"""

import argparse
import sys
import time
from datetime import UTC, datetime

# Ensure inventory service root is on sys.path
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.database import Base, SessionLocal, engine
from app.models.inventory import Inventory
from app.services.cache_service import (
    cache,
    get_cached_inventory,
    invalidate_inventory_cache,
    set_cached_inventory,
)


def seed_benchmark_item(db, sku_id: str = "SKU-BENCHMARK", warehouse_id: str = "WH-BENCHMARK"):
    """Ensure benchmark test inventory item exists."""
    item = (
        db.query(Inventory)
        .filter(Inventory.sku_id == sku_id, Inventory.warehouse_id == warehouse_id)
        .first()
    )
    if not item:
        item = Inventory(
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            product_name="Benchmark High Performance SKU",
            category="Electronics",
            quantity_on_hand=500,
            lead_time_days=3,
            safety_stock=20,
            version=1,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
    return item


def run_benchmark(iterations: int = 100):
    print("=" * 70)
    print("EAICSP Platform — Inventory Service: Redis Cache Benchmark")
    print("=" * 70)
    print(f"Iterations:        {iterations}")
    print(f"Database URL:      {settings.DATABASE_URL}")
    print(f"Redis URL:         {settings.REDIS_URL}")
    print(f"Mock Mode:         {cache.mock_mode}")
    print("-" * 70)

    db = SessionLocal()
    sku_id = "SKU-BENCH-001"
    warehouse_id = "WH-BENCH-001"

    try:
        item = seed_benchmark_item(db, sku_id=sku_id, warehouse_id=warehouse_id)
        payload = {
            "sku_id": item.sku_id,
            "warehouse_id": item.warehouse_id,
            "product_name": item.product_name,
            "category": item.category,
            "quantity_on_hand": item.quantity_on_hand,
            "lead_time_days": item.lead_time_days,
            "safety_stock": item.safety_stock,
            "version": item.version,
        }

        # Warm up
        db.query(Inventory).filter(
            Inventory.sku_id == sku_id,
            Inventory.warehouse_id == warehouse_id,
        ).first()

        # -------------------------------------------------------------
        # 1. Uncached Database Reads
        # -------------------------------------------------------------
        print("\n[1/2] Benchmarking Uncached Database Reads...")
        uncached_durations = []
        for _ in range(iterations):
            invalidate_inventory_cache(sku_id, warehouse_id)
            t0 = time.perf_counter()
            result = (
                db.query(Inventory)
                .filter(Inventory.sku_id == sku_id, Inventory.warehouse_id == warehouse_id)
                .first()
            )
            t1 = time.perf_counter()
            assert result is not None
            uncached_durations.append((t1 - t0) * 1000)

        # -------------------------------------------------------------
        # 2. Cached Reads (Redis Cache Hits)
        # -------------------------------------------------------------
        print("[2/2] Benchmarking Cached Reads (Redis Cache Hits)...")
        set_cached_inventory(sku_id, warehouse_id, payload)
        cached_durations = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            cached_val = get_cached_inventory(sku_id, warehouse_id)
            t1 = time.perf_counter()
            assert cached_val is not None
            cached_durations.append((t1 - t0) * 1000)

        # -------------------------------------------------------------
        # Statistics & Report
        # -------------------------------------------------------------
        avg_uncached = sum(uncached_durations) / len(uncached_durations)
        min_uncached = min(uncached_durations)
        max_uncached = max(uncached_durations)

        avg_cached = sum(cached_durations) / len(cached_durations)
        min_cached = min(cached_durations)
        max_cached = max(cached_durations)

        speedup = avg_uncached / max(avg_cached, 0.0001)

        print("\n" + "=" * 70)
        print("BENCHMARK RESULTS SUMMARY")
        print("=" * 70)
        print(f"Metric                 Uncached (DB)        Cached (Redis)       Delta / Speedup")
        print(f"---------------------  -------------------  -------------------  ---------------")
        print(f"Average Latency:       {avg_uncached:8.2f} ms         {avg_cached:8.2f} ms         {speedup:6.1f}x faster")
        print(f"Min Latency:           {min_uncached:8.2f} ms         {min_cached:8.2f} ms")
        print(f"Max Latency:           {max_uncached:8.2f} ms         {max_cached:8.2f} ms")
        print("=" * 70)
        print(f"Conclusion: Redis caching provides approximately a {speedup:.1f}x latency speedup.")
        print("=" * 70 + "\n")

    finally:
        invalidate_inventory_cache(sku_id, warehouse_id)
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark Redis cache latency")
    parser.add_argument("--iterations", type=int, default=100, help="Number of benchmark iterations")
    args = parser.parse_args()

    run_benchmark(iterations=args.iterations)
