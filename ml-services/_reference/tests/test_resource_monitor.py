from src.resource_monitor import ResourceMonitor


def test_cpu_percent_is_measured():
    monitor = ResourceMonitor()

    started_at, cpu_started_at = monitor.start()

    sum(i * i for i in range(3_000_000))

    metrics = monitor.measure_batch(
        1,
        1,
        1,
        started_at,
        cpu_started_at,
    )

    assert metrics.cpu_percent > 0