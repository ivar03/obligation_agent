import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.obligation import Intervention


class BaseInterventionExecutor(ABC):
    """
    Abstract interface for intervention execution adapters (Mock, Slack, Email, Webhook).
    """

    @abstractmethod
    async def execute(
        self, session: AsyncSession, intervention: Intervention
    ) -> Dict[str, Any]:
        pass


class DevMockInterventionExecutor(BaseInterventionExecutor):
    """
    Default simulation executor for local and demo operation.
    Accurately records mock execution timestamps and references without claiming false external delivery.
    """

    async def execute(
        self, session: AsyncSession, intervention: Intervention
    ) -> Dict[str, Any]:
        ref_id = f"SIM-DEMO-{uuid.uuid4().hex[:8].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"MockExecutor: Simulating intervention [{intervention.id}] to [{intervention.target_owner}] (Ref: {ref_id})."
        )

        return {
            "mode": "MOCK_DEMO",
            "execution_reference": ref_id,
            "simulated_at": now_iso,
            "recipient": intervention.target_owner,
            "message_snippet": (intervention.approved_message or intervention.message_draft)[:100],
            "status": "MOCK_EXECUTED",
            "note": "Intervention executed in simulation mode. No external messages were transmitted.",
        }
