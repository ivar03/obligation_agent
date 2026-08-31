"""
Phase 19 Test Suite: Circuit Breaker & Provider Failure Isolation.
Tests state transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED.
"""

import pytest
import asyncio
from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    ProviderHealth,
    CircuitBreakerOpenError,
    get_circuit_breaker,
)


@pytest.mark.asyncio
async def test_circuit_breaker_normal_closed_operation():
    cb = CircuitBreaker(provider="test_prov_1", failure_threshold=3, reset_timeout=1)
    assert cb.state == CircuitState.CLOSED

    # Successful calls succeed and keep circuit CLOSED
    async with cb.call():
        result = "ok"

    assert result == "ok"
    assert cb.state == CircuitState.CLOSED
    assert cb._failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_trips_to_open():
    cb = CircuitBreaker(provider="test_prov_2", failure_threshold=2, reset_timeout=1)

    # 1st failure
    with pytest.raises(ValueError):
        async with cb.call():
            raise ValueError("Provider down 1")
    assert cb.state == CircuitState.CLOSED
    assert cb._failure_count == 1

    # 2nd failure -> Trips to OPEN
    with pytest.raises(ValueError):
        async with cb.call():
            raise ValueError("Provider down 2")
    assert cb.state == CircuitState.OPEN

    # Immediate next call fails fast without executing body
    with pytest.raises(CircuitBreakerOpenError):
        async with cb.call():
            pytest.fail("Should not execute when circuit is OPEN")


@pytest.mark.asyncio
async def test_circuit_breaker_recovery_to_half_open_and_closed():
    cb = CircuitBreaker(provider="test_prov_3", failure_threshold=1, reset_timeout=0.1)

    # Trip to OPEN
    with pytest.raises(RuntimeError):
        async with cb.call():
            raise RuntimeError("Transient glitch")
    assert cb.state == CircuitState.OPEN

    # Wait for reset timeout
    await asyncio.sleep(0.15)

    # Probe call succeeds -> Recovers to CLOSED
    async with cb.call():
        probe_result = "recovered"

    assert probe_result == "recovered"
    assert cb.state == CircuitState.CLOSED
    assert cb._failure_count == 0
    assert cb.health == ProviderHealth.CONNECTED
