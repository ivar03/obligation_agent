from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from app.schemas.obligation import ExternalEvent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BaseProvider(ABC):
    """
    Abstract Provider Adapter Interface.
    Normalizes provider-specific payloads (Slack, Gmail, Webhook, Mock, etc.)
    into standard ExternalEvent instances.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Canonical name of the provider (e.g., 'mock', 'slack', 'gmail')."""
        pass

    @property
    @abstractmethod
    def provider_version(self) -> str:
        """Provider adapter version string."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """List of capabilities supported by this provider (e.g., ['events', 'attachments', 'simulation'])."""
        pass

    @abstractmethod
    def normalize_event(self, raw_payload: Dict[str, Any]) -> ExternalEvent:
        """
        Transforms provider-specific payload into a normalized ExternalEvent.
        """
        pass

    def validate_connection(self) -> bool:
        """Validates connection to the external provider. Defaults to True."""
        return True

    def validate_payload(self, raw_payload: Dict[str, Any]) -> bool:
        """Validates that raw payload contains required structure for this provider."""
        return bool(raw_payload)
