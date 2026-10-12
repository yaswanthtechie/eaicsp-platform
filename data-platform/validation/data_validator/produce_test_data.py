import json
from confluent_kafka import Producer


def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")


def main():
    p = Producer({'bootstrap.servers': 'localhost:9092'})

    test_events = [
        # Clean record
        {"transaction_id": 1, "date": "2024-03-10", "sku_id": "SKU-1000", "warehouse_id": "WH-01", "quantity_sold": 5,
         "unit_price": 20.0},
        # Messy record (Invalid SKU format, negative quantity)
        {"transaction_id": 2, "date": "2024-03-11", "sku_id": "BAD-SKU", "warehouse_id": "WH-02", "quantity_sold": -5,
         "unit_price": 10.0},
        # Missing required field (date)
        {"transaction_id": 3, "sku_id": "SKU-1001", "warehouse_id": "WH-01", "quantity_sold": 1, "unit_price": 15.0}
    ]

    for event in test_events:
        p.produce('sales.raw', json.dumps(event).encode('utf-8'), callback=delivery_report)

    p.flush()


if __name__ == "__main__":
    main()