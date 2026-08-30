from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid

from app.schemas.obligation import ExternalEvent
from app.services.providers.base_provider import BaseProvider


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MockProvider(BaseProvider):
    """
    Deterministic Mock Provider for development, continuous simulation, and automated testing.
    Provides deterministic canonical scenarios without external credentials.
    """

    SCENARIO_COMPLETION = "SCENARIO_A_COMPLETION"
    SCENARIO_PROGRESS = "SCENARIO_B_PROGRESS"
    SCENARIO_BLOCKER = "SCENARIO_C_BLOCKER"
    SCENARIO_REQUEST = "SCENARIO_D_REQUEST"
    SCENARIO_CHATTER = "SCENARIO_E_CHATTER"

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def provider_version(self) -> str:
        return "1.0.0"

    @property
    def capabilities(self) -> List[str]:
        return ["events", "attachments", "simulation", "deterministic_scenarios"]

    def normalize_event(self, raw_payload: Dict[str, Any]) -> ExternalEvent:
        """
        Normalizes a mock payload or canonical scenario into a standard ExternalEvent.
        """
        scenario = raw_payload.get("scenario")
        if scenario:
            return self.generate_canonical_event(
                scenario=scenario,
                custom_sender=raw_payload.get("sender"),
                custom_recipients=raw_payload.get("recipients"),
                custom_content=raw_payload.get("content"),
                custom_metadata=raw_payload.get("metadata"),
                source_ref=raw_payload.get("source_ref"),
            )

        # Standard dictionary normalization
        content = raw_payload.get("content") or raw_payload.get("text") or raw_payload.get("message") or ""
        sender = raw_payload.get("sender") or raw_payload.get("from") or raw_payload.get("author")
        recipients = raw_payload.get("recipients") or raw_payload.get("to") or []
        if isinstance(recipients, str):
            recipients = [recipients]

        source_ref = raw_payload.get("source_ref") or raw_payload.get("id") or raw_payload.get("message_id")
        source_type = raw_payload.get("source_type") or "message"
        metadata = raw_payload.get("metadata") or {}
        if "attachments" in raw_payload:
            metadata["attachments"] = raw_payload["attachments"]

        raw_ts = raw_payload.get("timestamp") or raw_payload.get("occurred_at")
        if isinstance(raw_ts, str):
            try:
                ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            except ValueError:
                ts = utc_now()
        elif isinstance(raw_ts, datetime):
            ts = raw_ts
        else:
            ts = utc_now()

        return ExternalEvent(
            source_type=source_type,
            source_ref=str(source_ref) if source_ref else f"mock_{uuid.uuid4().hex[:12]}",
            sender=sender,
            recipients=recipients,
            timestamp=ts,
            content=content,
            metadata=metadata,
        )

    def generate_canonical_event(
        self,
        scenario: str,
        custom_sender: Optional[str] = None,
        custom_recipients: Optional[List[str]] = None,
        custom_content: Optional[str] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
        source_ref: Optional[str] = None,
    ) -> ExternalEvent:
        """
        Generates deterministic test scenarios for benchmark verification.
        """
        sender = custom_sender or "Rahul"
        recipients = custom_recipients or ["Ravi"]
        ts = utc_now()
        ref = source_ref or f"mock_scenario_{scenario.lower()}_{uuid.uuid4().hex[:8]}"
        meta = custom_metadata.copy() if custom_metadata else {}

        if scenario.upper() in ["SCENARIO_A", "COMPLETION", self.SCENARIO_COMPLETION]:
            content = custom_content or "Sent the database benchmark numbers."
            meta.setdefault("attachments", [{"name": "benchmark_results.csv", "size": 8192}])
            return ExternalEvent(
                source_type="slack",
                source_ref=ref,
                sender=sender,
                recipients=recipients,
                timestamp=ts,
                content=content,
                metadata=meta,
            )

        elif scenario.upper() in ["SCENARIO_B", "PROGRESS", self.SCENARIO_PROGRESS]:
            content = custom_content or "Working on the benchmark numbers. Will send them shortly."
            return ExternalEvent(
                source_type="slack",
                source_ref=ref,
                sender=sender,
                recipients=recipients,
                timestamp=ts,
                content=content,
                metadata=meta,
            )

        elif scenario.upper() in ["SCENARIO_C", "BLOCKER", self.SCENARIO_BLOCKER]:
            content = custom_content or "I couldn't send the benchmark numbers because the database export failed."
            return ExternalEvent(
                source_type="slack",
                source_ref=ref,
                sender=sender,
                recipients=recipients,
                timestamp=ts,
                content=content,
                metadata=meta,
            )

        elif scenario.upper() in ["SCENARIO_D", "REQUEST", self.SCENARIO_REQUEST]:
            content = custom_content or "Can you confirm whether the benchmark numbers are still needed?"
            return ExternalEvent(
                source_type="slack",
                source_ref=ref,
                sender=sender,
                recipients=recipients,
                timestamp=ts,
                content=content,
                metadata=meta,
            )

        elif scenario.upper() in ["SCENARIO_E", "CHATTER", "IRRELEVANT", self.SCENARIO_CHATTER]:
            content = custom_content or "Hey team, hope everyone is having a great morning!"
            return ExternalEvent(
                source_type="slack",
                source_ref=ref,
                sender=sender,
                recipients=recipients,
                timestamp=ts,
                content=content,
                metadata=meta,
            )

        # Fallback to general event
        return ExternalEvent(
            source_type="message",
            source_ref=ref,
            sender=sender,
            recipients=recipients,
            timestamp=ts,
            content=custom_content or f"Mock event for scenario {scenario}",
            metadata=meta,
        )
