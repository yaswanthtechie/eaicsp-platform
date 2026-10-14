"""Count rows stored in InfluxDB. Usage: python -m src.check_influx"""

import os

from influxdb_client import InfluxDBClient

org = os.environ.get("INFLUXDB_ORG", "eaicsp")
bucket = os.environ.get("INFLUXDB_BUCKET", "iot_sensors")

client = InfluxDBClient(
    url=os.environ.get("INFLUXDB_URL", "http://localhost:8086"),
    token=os.environ["INFLUXDB_TOKEN"],
    org=org,
)

flux = f'''
from(bucket: "{bucket}")
  |> range(start: 2026-01-01T00:00:00Z, stop: 2027-01-01T00:00:00Z)
  |> filter(fn: (r) => r._measurement == "warehouse_sensor" and r._field == "is_flagged")
  |> group(columns: ["sensor_id"])
  |> count()
'''

total = 0

for table in client.query_api().query(flux):
    for record in table.records:
        print(record.values.get("sensor_id"), record.get_value())
        total += record.get_value()

print("total rows:", total)
client.close()