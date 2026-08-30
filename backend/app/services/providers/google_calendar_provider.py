import json
import re
import uuid
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from app.core.config import settings
from app.core.logging import logger
from app.schemas.obligation import ExternalEvent
from app.services.providers.base_provider import BaseProvider


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_calendar_identity(raw_identity: Any) -> str:
    """
    Normalizes a calendar user/organizer/attendee object or string into a display name.
    e.g., {'email': 'rahul@acme.com', 'displayName': 'Rahul Sharma'} -> 'Rahul Sharma'
          {'email': 'ravi@acme.com'} -> 'ravi@acme.com'
          'Rahul <rahul@acme.com>' -> 'Rahul'
          'Rahul' -> 'Rahul'
    """
    if not raw_identity:
        return "Unknown"
    
    if isinstance(raw_identity, dict):
        return raw_identity.get("displayName") or raw_identity.get("name") or raw_identity.get("email") or "Unknown"

    raw = str(raw_identity).strip()
    match = re.match(r'^"?([^"<]+)"?\s*<([^>]+)>$', raw)
    if match:
        name = match.group(1).strip()
        email = match.group(2).strip()
        return name if name else email

    angle_match = re.match(r'^<([^>]+)>$', raw)
    if angle_match:
        return angle_match.group(1).strip()

    return raw


class GoogleCalendarProvider(BaseProvider):
    """
    Real Provider Adapter for Google Calendar.
    Normalizes calendar events, meetings, attendee responses, reschedules, cancellations,
    and Google push notifications into provider-agnostic ExternalEvent instances.
    Contains ZERO obligation-specific intelligence.
    """

    SCENARIO_MEETING = "SCENARIO_A_MEETING"
    SCENARIO_RESCHEDULED = "SCENARIO_B_RESCHEDULED"
    SCENARIO_CANCELLED = "SCENARIO_C_CANCELLED"
    SCENARIO_ATTENDEE_ACCEPTED = "SCENARIO_D_ATTENDEE_ACCEPTED"
    SCENARIO_MEETING_COMPLETED = "SCENARIO_E_MEETING_COMPLETED"
    SCENARIO_UNRELATED = "SCENARIO_F_UNRELATED"

    @property
    def provider_name(self) -> str:
        return "google_calendar"

    @property
    def provider_version(self) -> str:
        return "1.0.0"

    @property
    def capabilities(self) -> List[str]:
        return [
            "events",
            "calendar",
            "meetings",
            "attendees",
            "oauth",
            "calendar_ingestion",
        ]

    def validate_connection(self) -> bool:
        """
        Validates Google Calendar connection configuration.
        """
        if settings.GOOGLE_CALENDAR_ENABLED and (
            settings.GOOGLE_CALENDAR_CLIENT_ID or settings.GOOGLE_CALENDAR_WEBHOOK_SECRET
        ):
            return True
        return False

    def validate_payload(self, raw_payload: Dict[str, Any]) -> bool:
        """
        Validates that raw payload has valid structure for a calendar event or notification.
        """
        if not isinstance(raw_payload, dict) or not raw_payload:
            return False

        if "scenario" in raw_payload:
            return True

        cal_keys = [
            "summary",
            "title",
            "event",
            "items",
            "calendar_id",
            "calendarId",
            "attendees",
            "organizer",
            "start",
            "end",
            "start_time",
            "end_time",
            "resourceId",
            "channelId",
        ]
        if any(k in raw_payload for k in cal_keys):
            return True

        return False

    def normalize_event(self, raw_payload: Dict[str, Any]) -> ExternalEvent:
        """
        Transforms Google Calendar payloads into a normalized ExternalEvent.
        """
        if not self.validate_payload(raw_payload):
            raise ValueError("Malformed Google Calendar payload: invalid structure or empty dictionary.")

        # 1. Handle Canonical Test Scenarios
        scenario = raw_payload.get("scenario")
        if scenario:
            return self.generate_canonical_event(
                scenario=scenario,
                custom_summary=raw_payload.get("summary") or raw_payload.get("title"),
                custom_organizer=raw_payload.get("organizer"),
                custom_attendees=raw_payload.get("attendees"),
                custom_start=raw_payload.get("start_time") or raw_payload.get("start"),
                custom_end=raw_payload.get("end_time") or raw_payload.get("end"),
                custom_status=raw_payload.get("status") or raw_payload.get("meeting_status"),
                source_ref=raw_payload.get("source_ref"),
                custom_metadata=raw_payload.get("metadata"),
            )

        working = raw_payload.get("event") if isinstance(raw_payload.get("event"), dict) else raw_payload

        # 2. Extract Event Core Attributes
        summary = working.get("summary") or working.get("title") or "Untitled Calendar Event"
        description = working.get("description") or ""
        calendar_id = working.get("calendar_id") or working.get("calendarId") or "primary"
        event_id = working.get("id") or working.get("event_id") or working.get("eventId") or f"evt_{uuid.uuid4().hex[:12]}"
        event_status = (working.get("status") or working.get("meeting_status") or "confirmed").lower()
        sequence = working.get("sequence", 0)

        # 3. Extract Organizer (Sender) & Attendees (Recipients)
        raw_organizer = working.get("organizer") or working.get("creator") or "Ravi <ravi@acme.com>"
        organizer_name = parse_calendar_identity(raw_organizer)

        raw_attendees = working.get("attendees") or []
        attendees_list: List[str] = []
        attendee_responses: Dict[str, str] = {}

        if isinstance(raw_attendees, list):
            for att in raw_attendees:
                att_name = parse_calendar_identity(att)
                if att_name and att_name != "Unknown":
                    attendees_list.append(att_name)
                if isinstance(att, dict) and "responseStatus" in att:
                    attendee_responses[att_name] = att["responseStatus"]
        elif isinstance(raw_attendees, str):
            attendees_list = [parse_calendar_identity(a) for a in raw_attendees.split(",") if a.strip()]

        if not attendees_list and organizer_name:
            attendees_list = [organizer_name]

        # 4. Extract Start & End Times
        start_obj = working.get("start") or {}
        end_obj = working.get("end") or {}

        start_time_raw = start_obj.get("dateTime") or start_obj.get("date") or working.get("start_time")
        end_time_raw = end_obj.get("dateTime") or end_obj.get("date") or working.get("end_time")
        tz = start_obj.get("timeZone") or working.get("timezone") or "UTC"
        location = working.get("location") or ""
        meeting_url = working.get("hangoutLink") or working.get("meeting_url") or working.get("htmlLink")

        start_dt = self._parse_datetime(start_time_raw)
        end_dt = self._parse_datetime(end_time_raw)

        # 5. Determine Temporal Signal & Semantic Meeting Status
        # Status options: scheduled, rescheduled, cancelled, completed, attendee_response
        meeting_status_type = "MEETING_SCHEDULED"
        if event_status == "cancelled" or working.get("cancelled"):
            meeting_status_type = "MEETING_CANCELLED"
        elif working.get("completed") or (end_dt and end_dt < utc_now()):
            meeting_status_type = "MEETING_COMPLETED"
        elif working.get("attendee_response"):
            meeting_status_type = "ATTENDEE_RESPONSE"
        elif working.get("rescheduled") or working.get("previous_start_time"):
            meeting_status_type = "MEETING_RESCHEDULED"
        elif sequence > 0:
            meeting_status_type = "MEETING_RESCHEDULED"

        # 6. Build Rich Descriptive Content
        content_lines = [
            f"Calendar Meeting: {summary}",
            f"Status: {meeting_status_type} ({event_status})",
            f"Organizer: {organizer_name}",
            f"Attendees: {', '.join(attendees_list) if attendees_list else 'None specified'}",
        ]
        if start_dt:
            content_lines.append(f"Start Time: {start_dt.isoformat()} ({tz})")
        if end_dt:
            content_lines.append(f"End Time: {end_dt.isoformat()}")
        if location:
            content_lines.append(f"Location: {location}")
        if description:
            content_lines.append(f"Description: {description}")

        content = "\n".join(content_lines)

        # 7. Deterministic Source Reference
        # Format: google_calendar:<calendar_id>:<event_id>:<sequence_or_status>
        if working.get("source_ref"):
            source_ref = str(working.get("source_ref"))
        else:
            clean_event_id = str(event_id).strip("<> ")
            source_ref = f"google_calendar:{calendar_id}:{clean_event_id}:{sequence}"

        # 8. Build Safe Metadata Dictionary (zero secret exposure)
        event_meta: Dict[str, Any] = {
            "source_provider": "google_calendar",
            "calendar_id": calendar_id,
            "event_id": str(event_id),
            "summary": summary,
            "meeting_status": meeting_status_type,
            "raw_status": event_status,
            "sequence": sequence,
            "timezone": tz,
            "organizer": organizer_name,
            "attendees": attendees_list,
            "attendee_responses": attendee_responses,
        }
        if start_dt:
            event_meta["start_time"] = start_dt.isoformat()
        if end_dt:
            event_meta["end_time"] = end_dt.isoformat()
        if location:
            event_meta["location"] = location
        if meeting_url:
            event_meta["meeting_url"] = meeting_url
        if working.get("recurrence"):
            event_meta["recurrence"] = working.get("recurrence")
        if working.get("previous_start_time"):
            event_meta["previous_start_time"] = working.get("previous_start_time")

        custom_meta = working.get("metadata")
        if isinstance(custom_meta, dict):
            for k, v in custom_meta.items():
                if k not in ["token", "secret", "access_token", "refresh_token", "client_secret", "authorization"]:
                    event_meta[k] = v

        event_ts = self._parse_datetime(working.get("updated") or working.get("created")) or utc_now()

        return ExternalEvent(
            source_type="google_calendar",
            source_ref=source_ref,
            sender=organizer_name,
            recipients=attendees_list,
            timestamp=event_ts,
            content=content,
            metadata=event_meta,
        )

    def _parse_datetime(self, val: Any) -> Optional[datetime]:
        if not val:
            return None
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        if isinstance(val, (int, float)):
            try:
                return datetime.fromtimestamp(val, tz=timezone.utc)
            except Exception:
                return None
        if isinstance(val, str):
            try:
                # Support ISO string
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    def generate_canonical_event(
        self,
        scenario: str,
        custom_summary: Optional[str] = None,
        custom_organizer: Optional[str] = None,
        custom_attendees: Optional[List[str]] = None,
        custom_start: Optional[Any] = None,
        custom_end: Optional[Any] = None,
        custom_status: Optional[str] = None,
        source_ref: Optional[str] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> ExternalEvent:
        """
        Generates deterministic test scenarios for Google Calendar temporal intelligence.
        """
        organizer = custom_organizer or "Ravi <ravi@acme.com>"
        attendees = custom_attendees or ["Rahul <rahul@acme.com>", "Ravi <ravi@acme.com>"]
        now = utc_now()
        scenario_key = scenario.upper()
        meta = custom_metadata.copy() if custom_metadata else {}

        if scenario_key in ["SCENARIO_A_MEETING", "SCENARIO_A", "MEETING_SCHEDULED"]:
            summary = custom_summary or "Project Review"
            start = custom_start or (now + timedelta(days=1, hours=4)).isoformat()
            end = custom_end or (now + timedelta(days=1, hours=5)).isoformat()
            ref = source_ref or "google_calendar:primary:evt_review_101:0"
            return self.normalize_event({
                "id": "evt_review_101",
                "summary": summary,
                "description": "Quarterly project review covering database benchmark numbers and performance milestones.",
                "organizer": organizer,
                "attendees": attendees,
                "start": {"dateTime": start},
                "end": {"dateTime": end},
                "status": "confirmed",
                "sequence": 0,
                "source_ref": ref,
                "metadata": meta,
            })

        elif scenario_key in ["SCENARIO_B_RESCHEDULED", "SCENARIO_B", "MEETING_RESCHEDULED"]:
            summary = custom_summary or "Project Review"
            start = custom_start or (now + timedelta(days=3, hours=2)).isoformat()
            end = custom_end or (now + timedelta(days=3, hours=3)).isoformat()
            prev_start = (now + timedelta(days=1, hours=4)).isoformat()
            ref = source_ref or "google_calendar:primary:evt_review_101:1"
            return self.normalize_event({
                "id": "evt_review_101",
                "summary": summary,
                "description": "Rescheduled Project Review: Moved to Tuesday 11:00 AM.",
                "organizer": organizer,
                "attendees": attendees,
                "start": {"dateTime": start},
                "end": {"dateTime": end},
                "previous_start_time": prev_start,
                "rescheduled": True,
                "status": "confirmed",
                "sequence": 1,
                "source_ref": ref,
                "metadata": meta,
            })

        elif scenario_key in ["SCENARIO_C_CANCELLED", "SCENARIO_C", "MEETING_CANCELLED"]:
            summary = custom_summary or "Project Review"
            ref = source_ref or "google_calendar:primary:evt_review_101:2"
            return self.normalize_event({
                "id": "evt_review_101",
                "summary": summary,
                "description": "Project Review meeting has been cancelled.",
                "organizer": organizer,
                "attendees": attendees,
                "status": "cancelled",
                "cancelled": True,
                "sequence": 2,
                "source_ref": ref,
                "metadata": meta,
            })

        elif scenario_key in ["SCENARIO_D_ATTENDEE_ACCEPTED", "SCENARIO_D", "ATTENDEE_RESPONSE"]:
            summary = custom_summary or "Project Review"
            ref = source_ref or "google_calendar:primary:evt_review_101:3"
            return self.normalize_event({
                "id": "evt_review_101",
                "summary": summary,
                "description": "Rahul accepted the Project Review invitation.",
                "organizer": organizer,
                "attendees": [
                    {"email": "rahul@acme.com", "displayName": "Rahul", "responseStatus": "accepted"},
                    {"email": "ravi@acme.com", "displayName": "Ravi", "responseStatus": "accepted"},
                ],
                "status": "confirmed",
                "attendee_response": True,
                "sequence": 0,
                "source_ref": ref,
                "metadata": meta,
            })

        elif scenario_key in ["SCENARIO_E_MEETING_COMPLETED", "SCENARIO_E", "MEETING_COMPLETED"]:
            summary = custom_summary or "Project Review"
            past_start = (now - timedelta(hours=3)).isoformat()
            past_end = (now - timedelta(hours=2)).isoformat()
            ref = source_ref or "google_calendar:primary:evt_review_101:4"
            return self.normalize_event({
                "id": "evt_review_101",
                "summary": summary,
                "description": "Project Review meeting concluded.",
                "organizer": organizer,
                "attendees": attendees,
                "start": {"dateTime": past_start},
                "end": {"dateTime": past_end},
                "status": "confirmed",
                "completed": True,
                "sequence": 0,
                "source_ref": ref,
                "metadata": meta,
            })

        elif scenario_key in ["SCENARIO_F_UNRELATED", "SCENARIO_F", "UNRELATED"]:
            summary = custom_summary or "Personal Lunch"
            ref = source_ref or f"google_calendar:primary:evt_lunch_{uuid.uuid4().hex[:8]}:0"
            return self.normalize_event({
                "id": f"evt_lunch_{uuid.uuid4().hex[:8]}",
                "summary": summary,
                "description": "Lunch with college friend.",
                "organizer": organizer,
                "attendees": ["Friend <friend@external.com>"],
                "start": {"dateTime": (now + timedelta(hours=5)).isoformat()},
                "end": {"dateTime": (now + timedelta(hours=6)).isoformat()},
                "status": "confirmed",
                "source_ref": ref,
                "metadata": meta,
            })

        # Fallback generic scenario
        return self.normalize_event({
            "id": f"evt_scenario_{scenario.lower()}",
            "summary": custom_summary or f"Meeting: {scenario}",
            "organizer": organizer,
            "attendees": attendees,
            "source_ref": source_ref or f"google_calendar:primary:evt_{scenario.lower()}_{uuid.uuid4().hex[:8]}:0",
            "metadata": meta,
        })
