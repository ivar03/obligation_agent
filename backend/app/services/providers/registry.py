from typing import Dict, List, Any, Optional
from app.core.logging import logger
from app.services.providers.base_provider import BaseProvider
from app.services.providers.mock_provider import MockProvider
from app.services.providers.slack_provider import SlackProvider
from app.services.providers.gmail_provider import GmailProvider
from app.services.providers.google_calendar_provider import GoogleCalendarProvider


class ProviderRegistry:
    """
    Central registry for event provider adapters.
    Maintains registered providers and enables plug-and-play provider resolution.
    """

    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {}
        # Automatically register built-in providers
        self.register(MockProvider())
        self.register(SlackProvider())
        self.register(GmailProvider())
        self.register(GoogleCalendarProvider())

    def register(self, provider: BaseProvider) -> None:
        """Registers a provider adapter."""
        name = provider.provider_name.lower()
        self._providers[name] = provider
        logger.info(f"Provider registered: '{name}' (v{provider.provider_version})")

    def get(self, provider_name: str) -> BaseProvider:
        """
        Retrieves a provider adapter by name.
        Raises ValueError if the provider is not registered.
        """
        name = provider_name.lower()
        if name not in self._providers:
            available = ", ".join(self._providers.keys())
            raise ValueError(f"Unknown provider '{provider_name}'. Available providers: [{available}]")
        return self._providers[name]

    def has_provider(self, provider_name: str) -> bool:
        """Checks if a provider is registered."""
        return provider_name.lower() in self._providers

    def list_providers(self) -> List[Dict[str, Any]]:
        """Lists all registered providers and their metadata."""
        return [
            {
                "name": p.provider_name,
                "version": p.provider_version,
                "capabilities": p.capabilities,
                "is_connected": p.validate_connection(),
            }
            for p in self._providers.values()
        ]


# Singleton instance
provider_registry = ProviderRegistry()
