"""
Phase 19 Test Suite: Real-Time Metrics & Latency Percentiles.
Tests rolling window histograms, counters, percentiles (p50/p95/p99), and snapshot exports.
"""

import pytest
from app.core.metrics import MetricsCollector


def test_metrics_collector_counters():
    collector = MetricsCollector(window_size=100)
    collector.increment("api.requests", 1.0, labels={"route": "/api/obligations"})
    collector.increment("api.requests", 2.0, labels={"route": "/api/obligations"})
    collector.increment("api.requests", 1.0, labels={"route": "/api/health"})

    val = collector.get_counter("api.requests", labels={"route": "/api/obligations"})
    assert val == 3.0

    val_health = collector.get_counter("api.requests", labels={"route": "/api/health"})
    assert val_health == 1.0


def test_metrics_collector_histogram_percentiles():
    collector = MetricsCollector(window_size=1000)

    # Insert 100 data points: 1.0 to 100.0 ms
    for i in range(1, 101):
        collector.record_duration("api.latency_ms", float(i), labels={"route": "/api/test"})

    stats = collector.get_histogram_stats("api.latency_ms", labels={"route": "/api/test"})
    assert stats["count"] == 100
    assert stats["mean"] == 50.5
    assert stats["p50"] == 50.0 or stats["p50"] == 51.0
    assert stats["p95"] == 95.0 or stats["p95"] == 96.0
    assert stats["p99"] == 99.0 or stats["p99"] == 100.0


def test_metrics_snapshot():
    collector = MetricsCollector(window_size=50)
    collector.increment("events.ingested", 5)
    collector.record_duration("events.latency", 25.0)

    snap = collector.snapshot()
    assert "uptime_seconds" in snap
    assert "counters" in snap
    assert "histograms" in snap
    assert snap["counters"].get("events.ingested") == 5
