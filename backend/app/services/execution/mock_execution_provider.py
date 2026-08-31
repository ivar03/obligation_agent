"""
Mock Execution Provider for Controlled Execution in Phase 16.
Deterministic development and live simulation provider with zero external credentials required.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
from app.core.logging import logger
from app.core.status_machine import ExecutionFailureCode
from app.services.execution.base_execution_provider import (
    BaseExecutionProvider,
    ExecutionActionPayload,
    ExecutionProviderReceipt,
)


class MockExecutionProvider(BaseExecutionProvider):
    """
    Deterministic mock provider for controlled decision execution.
    Supports behavior toggles via payload metadata (mock_behavior: 'SUCCESS', 'DELIVERY_FAILURE', 'TEMPORARY_FAILURE', 'DUPLICATE').
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def provider_version(self) -> str:
        return "1.0.0"

    @property
    def capabilities(self) -> List[str]:
        return ["messages", "simulation", "instant_delivery", "idempotent_mock"]

    def validate_connection(self) -> bool:
        return True

    async def execute(self, action: ExecutionActionPayload) -> ExecutionProviderReceipt:
        ref_id = f"SIM-EXEC-{uuid.uuid4().hex[:8].upper()}"
        behavior_val = action.metadata.get("mock_behavior") if action.metadata else None
        behavior = (behavior_val or "SUCCESS").upper()

        logger.info(
            f"MockExecutionProvider: Executing action for recipient [{action.recipient}] (Behavior: {behavior}, Ref: {ref_id})"
        )

        if behavior == "DELIVERY_FAILURE":
            return ExecutionProviderReceipt(
                success=False,
                provider=self.provider_name,
                provider_version=self.provider_version,
                provider_ref=ref_id,
                delivery_status="PERMANENT_FAILURE",
                failure_code=ExecutionFailureCode.INVALID_RECIPIENT,
                failure_reason=f"Mock recipient [{action.recipient}] is unknown or invalid in simulated directory.",
                is_transient_failure=False,
                raw_metadata={
                    "execution_mode": "MOCK_DEMO",
                    "recipient": action.recipient,
                    "channel": action.channel or "sim-general",
                    "simulated_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        elif behavior == "TEMPORARY_FAILURE":
            return ExecutionProviderReceipt(
                success=False,
                provider=self.provider_name,
                provider_version=self.provider_version,
                provider_ref=ref_id,
                delivery_status="TRANSIENT_FAILURE",
                failure_code=ExecutionFailureCode.RATE_LIMITED,
                failure_reason="Simulated provider rate limit encountered. Retry scheduled.",
                is_transient_failure=True,
                raw_metadata={
                    "execution_mode": "MOCK_DEMO",
                    "recipient": action.recipient,
                    "simulated_at": datetime.now(timezone.utc).isoformat(),
                    "retry_after_seconds": 15,
                },
            )

        # Default: SUCCESS
        return ExecutionProviderReceipt(
            success=True,
            provider=self.provider_name,
            provider_version=self.provider_version,
            provider_ref=ref_id,
            delivery_status="DELIVERED",
            failure_code=None,
            failure_reason=None,
            is_transient_failure=False,
            raw_metadata={
                "execution_mode": "MOCK_DEMO",
                "recipient": action.recipient,
                "channel": action.channel or "sim-channel",
                "message_length": len(action.message),
                "simulated_at": datetime.now(timezone.utc).isoformat(),
                "note": "Controlled execution simulated successfully with zero external credentials.",
            },
        )

    async def get_execution_status(self, provider_ref: str) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "provider_ref": provider_ref,
            "status": "DELIVERED",
            "execution_mode": "MOCK_DEMO",
        }

    async def cancel_execution(self, provider_ref: str) -> bool:
        logger.info(f"MockExecutionProvider: Cancelled execution reference [{provider_ref}].")
        return True
