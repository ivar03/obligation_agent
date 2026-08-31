"""
Phase 19 Production Metrics Collector.

Thread-safe in-process metrics with rolling-window percentile calculation.
All metric labels and values must be credential-free.

Usage:
    from app.core.metrics import metrics
    metrics.increment("api.requests", labels={"route": "/api/obligations"})
    metrics.record_duration("api.latency_ms", 42.3, labels={"route": "/api/obligations"})

Metrics categories:
    api.*          — HTTP request counts, error counts, latency
    ingestion.*    — event processing stats
    intelligence.* — decision plan stats
    execution.*    — execution dispatch stats
    evidence.*     — evidence tracking
    worker.*       — job queue stats
"""

import time
import threading
from collections import defaultdict, deque
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

from app.core.config import settings


@dataclass
class CounterMetric:
    """Simple monotonically increasing counter."""
    name: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    def increment(self, amount: float = 1.0) -> None:
        self.value += amount


@dataclass
class HistogramMetric:
    """Rolling window histogram for percentile calculation."""
    name: str
    window_size: int = 1000
    labels: Dict[str, str] = field(default_factory=dict)
    _samples: deque = field(default_factory=deque)

    def record(self, value: float) -> None:
        self._samples.append(value)
        if len(self._samples) > self.window_size:
            self._samples.popleft()

    def percentile(self, pct: float) -> Optional[float]:
        if not self._samples:
            return None
        sorted_samples = sorted(self._samples)
        idx = int(len(sorted_samples) * pct / 100)
        idx = min(idx, len(sorted_samples) - 1)
        return sorted_samples[idx]

    @property
    def count(self) -> int:
        return len(self._samples)

    @property
    def total(self) -> float:
        return sum(self._samples)

    @property
    def mean(self) -> Optional[float]:
        if not self._samples:
            return None
        return self.total / len(self._samples)

    @property
    def p50(self) -> Optional[float]:
        return self.percentile(50)

    @property
    def p95(self) -> Optional[float]:
        return self.percentile(95)

    @property
    def p99(self) -> Optional[float]:
        return self.percentile(99)


class MetricsCollector:
    """
    Thread-safe singleton metrics collector.
    Counters are cumulative; histograms use a rolling window.
    All data is in-process and ephemeral (resets on restart).
    """

    def __init__(self, window_size: int = 1000):
        self._lock = threading.Lock()
        self._window_size = window_size
        # counters: dict[metric_key] -> float
        self._counters: Dict[str, float] = defaultdict(float)
        # histograms: dict[metric_key] -> deque of floats
        self._histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self._start_time = time.time()

    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def increment(self, name: str, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a named counter."""
        key = self._make_key(name, labels)
        with self._lock:
            self._counters[key] += amount

    def record_duration(self, name: str, duration_ms: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a duration (ms) in a rolling histogram."""
        key = self._make_key(name, labels)
        with self._lock:
            self._histograms[key].append(duration_ms)

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        key = self._make_key(name, labels)
        with self._lock:
            return self._counters.get(key, 0.0)

    def get_histogram_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        key = self._make_key(name, labels)
        with self._lock:
            samples = list(self._histograms.get(key, []))
        if not samples:
            return {"count": 0, "p50": None, "p95": None, "p99": None, "mean": None}
        sorted_s = sorted(samples)
        n = len(sorted_s)
        def pct(p):
            idx = min(int(n * p / 100), n - 1)
            return round(sorted_s[idx], 2)
        return {
            "count": n,
            "mean": round(sum(sorted_s) / n, 2),
            "p50": pct(50),
            "p95": pct(95),
            "p99": pct(99),
        }

    def snapshot(self) -> Dict[str, Any]:
        """Return a full metrics snapshot for the /api/metrics endpoint."""
        with self._lock:
            counters = dict(self._counters)
            histograms = {k: list(v) for k, v in self._histograms.items()}

        def _pcts(samples):
            if not samples:
                return {"count": 0, "p50": None, "p95": None, "p99": None, "mean": None}
            s = sorted(samples)
            n = len(s)
            def pct(p): return round(s[min(int(n * p / 100), n - 1)], 2)
            return {
                "count": n,
                "mean": round(sum(s) / n, 2),
                "p50": pct(50),
                "p95": pct(95),
                "p99": pct(99),
            }

        return {
            "uptime_seconds": round(time.time() - self._start_time, 2),
            "counters": counters,
            "histograms": {k: _pcts(v) for k, v in histograms.items()},
        }

    def reset(self) -> None:
        """Reset all metrics (useful for tests)."""
        with self._lock:
            self._counters.clear()
            self._histograms.clear()
            self._start_time = time.time()


# Global singleton
metrics = MetricsCollector(window_size=settings.METRICS_WINDOW_SIZE)
