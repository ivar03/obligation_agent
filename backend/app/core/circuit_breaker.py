"""
Phase 19 Circuit Breaker & Provider Failure Isolation.

Prevents provider outages from bringing down the core Obligation Agent.
Each provider gets its own CircuitBreaker instance. When a provider exceeds
the failure threshold, the circuit OPENS, and subsequent calls immediately
raise CircuitOpenError without touching the provider.

States:
    CLOSED      — Normal operation, requests pass through
    OPEN        — Provider failures exceeded threshold; requests fail fast
    HALF_OPEN   — Testing if provider has recovered; one probe request allowed

Provider Health States:
    CONNECTED, DEGRADED, RATE_LIMITED, AUTH_FAILED, UNAVAILABLE, DISCONNECTED

Usage:
    from app.core.circuit_breaker import get_circuit_breaker

    cb = get_circuit_breaker("slack")
    async with cb.call():
        await slack_client.post_message(...)
"""

import time
import asyncio
from enum import Enum
from typing import Dict, Optional, AsyncGenerator
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("obligation_agent.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"       # Normal — pass through
    OPEN = "OPEN"           # Failing — fail fast
    HALF_OPEN = "HALF_OPEN" # Testing recovery


class ProviderHealth(str, Enum):
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    AUTH_FAILED = "AUTH_FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    DISCONNECTED = "DISCONNECTED"


class CircuitBreakerOpenError(Exception):
    """Raised when a circuit is OPEN and a call is attempted."""
    pass


class CircuitBreaker:
    """
    Per-provider circuit breaker.

    Thread-safe; uses asyncio.Lock for HALF_OPEN probe serialisation.
    """

    def __init__(
        self,
        provider: str,
        failure_threshold: int = None,
        reset_timeout: int = None,
    ):
        self.provider = provider
        self.failure_threshold = failure_threshold or settings.CB_FAILURE_THRESHOLD
        self.reset_timeout = reset_timeout or settings.CB_RECOVERY_TIMEOUT

        self.state = CircuitState.CLOSED
        self.health = ProviderHealth.CONNECTED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def call(self) -> AsyncGenerator[None, None]:
        """
        Context manager wrapping a provider call.
        Raises CircuitBreakerOpenError if the circuit is OPEN.
        Records success/failure and transitions state accordingly.

        Example:
            async with circuit.call():
                result = await provider.do_thing()
        """
        await self._check_state()
        try:
            yield
            self._on_success()
        except CircuitBreakerOpenError:
            raise
        except Exception as exc:
            self._on_failure(exc)
            raise

    def get_status(self) -> dict:
        return {
            "provider": self.provider,
            "state": self.state,
            "health": self.health,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_at": self._last_failure_time,
        }

    def reset(self) -> None:
        """Manually reset the circuit (for admin / test use)."""
        self.state = CircuitState.CLOSED
        self.health = ProviderHealth.CONNECTED
        self._failure_count = 0
        self._last_failure_time = None
        logger.info(f"Circuit breaker for '{self.provider}' manually reset.")

    # ------------------------------------------------------------------
    # Internal state transitions
    # ------------------------------------------------------------------

    async def _check_state(self) -> None:
        if self.state == CircuitState.CLOSED:
            return

        if self.state == CircuitState.OPEN:
            elapsed = time.monotonic() - (self._last_failure_time or 0)
            if elapsed >= self.reset_timeout:
                # Transition to HALF_OPEN to probe
                async with self._half_open_lock:
                    if self.state == CircuitState.OPEN:
                        self.state = CircuitState.HALF_OPEN
                        self.health = ProviderHealth.DEGRADED
                        logger.info(f"Circuit '{self.provider}' entering HALF_OPEN for probe.")
                return  # Allow this one probe through

            logger.warning(
                f"Circuit '{self.provider}' is OPEN. "
                f"Retry after {self.reset_timeout - elapsed:.0f}s."
            )
            raise CircuitBreakerOpenError(
                f"Provider '{self.provider}' circuit is OPEN. "
                f"Retry after {int(self.reset_timeout - elapsed) + 1}s."
            )

        # HALF_OPEN: allow the probe through

    def _on_success(self) -> None:
        if self.state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            logger.info(f"Circuit '{self.provider}' recovered → CLOSED.")
        self.state = CircuitState.CLOSED
        self.health = ProviderHealth.CONNECTED
        self._failure_count = 0
        self._last_failure_time = None

    def _on_failure(self, exc: Exception) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        self.health = self._classify_error(exc)

        if self._failure_count >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.error(
                f"Circuit '{self.provider}' OPENED after {self._failure_count} failures. "
                f"Will retry in {self.reset_timeout}s.",
                extra={"provider": self.provider, "error": str(exc)},
            )
        else:
            logger.warning(
                f"Circuit '{self.provider}' failure {self._failure_count}/{self.failure_threshold}: {exc}",
                extra={"provider": self.provider},
            )

    @staticmethod
    def _classify_error(exc: Exception) -> ProviderHealth:
        msg = str(exc).lower()
        if "auth" in msg or "unauthorized" in msg or "403" in msg or "401" in msg:
            return ProviderHealth.AUTH_FAILED
        if "rate" in msg or "429" in msg or "too many" in msg:
            return ProviderHealth.RATE_LIMITED
        if "timeout" in msg or "timed out" in msg:
            return ProviderHealth.DEGRADED
        return ProviderHealth.UNAVAILABLE


# ---------------------------------------------------------------------------
# Registry: one instance per provider
# ---------------------------------------------------------------------------

_registry: Dict[str, CircuitBreaker] = {}
_registry_lock = asyncio.Lock()


def get_circuit_breaker(provider: str) -> CircuitBreaker:
    """Return (or create) the CircuitBreaker for a given provider name."""
    if provider not in _registry:
        _registry[provider] = CircuitBreaker(provider=provider)
    return _registry[provider]


def get_all_circuit_statuses() -> dict:
    """Return health status for all registered providers (for /metrics)."""
    return {name: cb.get_status() for name, cb in _registry.items()}
