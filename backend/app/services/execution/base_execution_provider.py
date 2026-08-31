"""
Base Provider Interface for Controlled Decision Execution in Phase 16.
Transport and execution adapter abstractions with ZERO intelligence logic.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.core.status_machine import ExecutionFailureCode


class ExecutionActionPayload(BaseModel):
    recipient: str
    message: str
    channel: Optional[str] = None
    thread_ts: Optional[str] = None
    action_type: str = "INTERVENTION_MESSAGE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionProviderReceipt(BaseModel):
    success: bool
    provider: str
    provider_version: str
    provider_ref: str
    delivery_status: str
    failure_code: Optional[ExecutionFailureCode] = None
    failure_reason: Optional[str] = None
    is_transient_failure: bool = False
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseExecutionProvider(ABC):
    """
    Abstract interface for outbound execution adapters.
    Execution providers are transport adapters only.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def provider_version(self) -> str:
        pass

    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        pass

    @abstractmethod
    async def execute(self, action: ExecutionActionPayload) -> ExecutionProviderReceipt:
        """
        Executes a fully formed, authorized action.
        Must NOT modify the message, recipient, or channel.
        Must NOT store secrets or credentials in the returned receipt.
        """
        pass

    @abstractmethod
    async def get_execution_status(self, provider_ref: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def cancel_execution(self, provider_ref: str) -> bool:
        pass
