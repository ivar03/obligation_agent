import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from app.core.logging import logger
from app.schemas.obligation import DeadlineType, DeadlineResolution, MessageContext


class BaseDeadlineAgent(ABC):
    """Abstract interface for deadline reasoning agent."""

    @abstractmethod
    async def resolve(self, text: str, context: MessageContext) -> DeadlineResolution:
        pass


class DevMockDeadlineAgent(BaseDeadlineAgent):
    """
    Rule-based temporal & condition reasoning agent.
    Accurately classifies deadlines as EXPLICIT, RELATIVE, CONDITIONAL, or UNKNOWN,
    and resolves relative time offsets against a supplied timezone-aware reference datetime.
    """

    async def resolve(self, text: str, context: MessageContext) -> DeadlineResolution:
        cleaned = text.strip()
        lower = cleaned.lower()
        ref_time = context.reference_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        # 1. Conditional Deadlines (e.g. "once Rahul sends...", "after Ravi submits...", "when client approves...")
        cond_match = re.search(
            r"\b(once|after|when|if|provided that|conditional on|before\s+[a-zA-Z]+\s+can)\s+([^.,;\n]+)",
            cleaned,
            re.IGNORECASE
        )
        if cond_match:
            trigger_keyword = cond_match.group(1).lower()
            trigger_clause = cond_match.group(2).strip()
            full_condition = f"{trigger_keyword.capitalize()} {trigger_clause}"
            logger.info(f"DeadlineAgent detected conditional dependency: '{full_condition}'")
            return DeadlineResolution(
                deadline_type=DeadlineType.CONDITIONAL,
                resolved_deadline=None,
                condition_trigger=full_condition,
                confidence=0.94,
                reasoning=f"Conditional dependency identified ('{full_condition}'). Duty is gated by a trigger event rather than a static calendar date.",
                ambiguous=False,
                raw_expression=cond_match.group(0)
            )

        # 2. Vague / Ambiguous Deadlines (e.g. "sometime soon", "whenever you can", "eventually")
        vague_patterns = [
            r"\bsometime soon\b", r"\bwhenever\b", r"\blater\b", r"\basap\b",
            r"\bat some point\b", r"\bin the near future\b", r"\bwhen you get a chance\b",
            r"\bwhen possible\b"
        ]
        for v_pat in vague_patterns:
            v_match = re.search(v_pat, lower)
            if v_match:
                raw_expr = v_match.group(0)
                logger.info(f"DeadlineAgent detected vague/ambiguous deadline: '{raw_expr}'")
                return DeadlineResolution(
                    deadline_type=DeadlineType.UNKNOWN,
                    resolved_deadline=None,
                    condition_trigger=None,
                    confidence=0.30,
                    reasoning=f"Vague temporal phrase '{raw_expr}' lacks a concrete date, time, or trigger condition.",
                    ambiguous=True,
                    raw_expression=raw_expr
                )

        # 3. Explicit Time + Day (e.g. "by 5 PM Friday", "before 10:00 AM on Monday")
        explicit_time_match = re.search(r"\bby\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s+(?:on\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today)\b", lower)
        if explicit_time_match:
            time_str = explicit_time_match.group(1).strip()
            day_str = explicit_time_match.group(2).strip()
            hour, minute = self._parse_time(time_str)
            target_date = self._resolve_weekday_or_relative(day_str, ref_time)
            resolved = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            logger.info(f"DeadlineAgent resolved explicit deadline: {resolved.isoformat()}")
            return DeadlineResolution(
                deadline_type=DeadlineType.EXPLICIT,
                resolved_deadline=resolved,
                condition_trigger=None,
                confidence=0.96,
                reasoning=f"Explicit deadline resolved to {resolved.strftime('%A, %B %d, %Y at %I:%M %p %Z')}.",
                ambiguous=False,
                raw_expression=explicit_time_match.group(0)
            )

        # 4. Explicit Month & Day (e.g. "September 12", "12th of September", "due on Oct 5")
        month_day_match = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?\b", lower)
        if month_day_match:
            month_str = month_day_match.group(1)
            day_num = int(month_day_match.group(2))
            month_num = self._parse_month(month_str)
            target_year = ref_time.year
            try:
                resolved = datetime(target_year, month_num, day_num, 17, 0, 0, tzinfo=ref_time.tzinfo)
                if resolved < ref_time:
                    resolved = resolved.replace(year=target_year + 1)
                logger.info(f"DeadlineAgent resolved explicit date: {resolved.isoformat()}")
                return DeadlineResolution(
                    deadline_type=DeadlineType.EXPLICIT,
                    resolved_deadline=resolved,
                    condition_trigger=None,
                    confidence=0.95,
                    reasoning=f"Explicit calendar date resolved to {resolved.strftime('%B %d, %Y')}.",
                    ambiguous=False,
                    raw_expression=month_day_match.group(0)
                )
            except ValueError:
                pass

        # 5. Relative Deadlines ("tomorrow", "today", "next Friday", "in 3 days", "next week")
        if "tomorrow" in lower:
            resolved = (ref_time + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)
            return DeadlineResolution(
                deadline_type=DeadlineType.RELATIVE,
                resolved_deadline=resolved,
                condition_trigger=None,
                confidence=0.95,
                reasoning=f"Relative 'tomorrow' resolved against reference date ({ref_time.strftime('%Y-%m-%d')}) to {resolved.strftime('%A, %B %d, %Y')}.",
                ambiguous=False,
                raw_expression="tomorrow"
            )

        if "today" in lower or "tonight" in lower or "eod" in lower or "end of day" in lower:
            resolved = ref_time.replace(hour=18, minute=0, second=0, microsecond=0)
            return DeadlineResolution(
                deadline_type=DeadlineType.RELATIVE,
                resolved_deadline=resolved,
                condition_trigger=None,
                confidence=0.95,
                reasoning=f"Relative 'today / EOD' resolved to {resolved.strftime('%A, %B %d, %Y at 6:00 PM')}.",
                ambiguous=False,
                raw_expression="today"
            )

        days_in_match = re.search(r"\bin\s+(\d+|two|three|four|five)\s+days\b", lower)
        if days_in_match:
            val = days_in_match.group(1)
            num_map = {"two": 2, "three": 3, "four": 4, "five": 5}
            days_count = num_map.get(val, int(val) if val.isdigit() else 3)
            resolved = (ref_time + timedelta(days=days_count)).replace(hour=17, minute=0, second=0, microsecond=0)
            return DeadlineResolution(
                deadline_type=DeadlineType.RELATIVE,
                resolved_deadline=resolved,
                condition_trigger=None,
                confidence=0.90,
                reasoning=f"Relative 'in {days_count} days' resolved to {resolved.strftime('%A, %B %d, %Y')}.",
                ambiguous=False,
                raw_expression=days_in_match.group(0)
            )

        for weekday_name in ["friday", "monday", "tuesday", "wednesday", "thursday", "saturday", "sunday"]:
            if weekday_name in lower:
                target_date = self._resolve_weekday_or_relative(weekday_name, ref_time)
                resolved = target_date.replace(hour=17, minute=0, second=0, microsecond=0)
                return DeadlineResolution(
                    deadline_type=DeadlineType.RELATIVE,
                    resolved_deadline=resolved,
                    condition_trigger=None,
                    confidence=0.90,
                    reasoning=f"Relative weekday '{weekday_name.capitalize()}' resolved to {resolved.strftime('%A, %B %d, %Y')}.",
                    ambiguous=False,
                    raw_expression=weekday_name
                )

        if "next week" in lower:
            resolved = (ref_time + timedelta(days=7)).replace(hour=17, minute=0, second=0, microsecond=0)
            return DeadlineResolution(
                deadline_type=DeadlineType.RELATIVE,
                resolved_deadline=resolved,
                condition_trigger=None,
                confidence=0.82,
                reasoning=f"Relative 'next week' resolved to {resolved.strftime('%A, %B %d, %Y')}.",
                ambiguous=False,
                raw_expression="next week"
            )

        # 6. No Deadline specified
        return DeadlineResolution(
            deadline_type=DeadlineType.UNKNOWN,
            resolved_deadline=None,
            condition_trigger=None,
            confidence=0.90,
            reasoning="No deadline or time constraint specified in message.",
            ambiguous=False,
            raw_expression=None
        )

    def _parse_time(self, time_str: str) -> Tuple[int, int]:
        clean = time_str.lower().strip()
        is_pm = "pm" in clean
        is_am = "am" in clean
        digits = re.sub(r"[^\d:]", "", clean)
        parts = digits.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0

        if is_pm and hour < 12:
            hour += 12
        elif is_am and hour == 12:
            hour = 0
        return hour, minute

    def _resolve_weekday_or_relative(self, day_str: str, ref_time: datetime) -> datetime:
        day_str = day_str.lower()
        if day_str == "tomorrow":
            return ref_time + timedelta(days=1)
        if day_str == "today":
            return ref_time

        weekday_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
        }
        target_idx = weekday_map.get(day_str, 4)
        current_idx = ref_time.weekday()
        days_ahead = (target_idx - current_idx + 7) % 7
        if days_ahead == 0:
            days_ahead = 7
        return ref_time + timedelta(days=days_ahead)

    def _parse_month(self, month_str: str) -> int:
        months = {
            "jan": 1, "january": 1, "feb": 2, "february": 2,
            "mar": 3, "march": 3, "apr": 4, "april": 4,
            "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
            "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
            "oct": 10, "october": 10, "nov": 11, "november": 11,
            "dec": 12, "december": 12
        }
        return months.get(month_str.lower(), 9)
