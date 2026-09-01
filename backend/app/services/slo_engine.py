"""
Phase 21 SLO / SLI & Error Budget Calculation Engine.

Calculates real service-level indicators, SLO compliance percentages,
and error-budget consumption rates across API, Event Processing, Execution, and LLM.
Returns INSUFFICIENT_DATA when sample counts are insufficient.
"""

from typing import List, Tuple, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import metrics
from app.models.event_inbox import EventInboxRecord, EventInboxStatus
from app.models.execution import ExecutionRecord
from app.models.llm_analysis import LLMAnalysisRecord
from app.schemas.observability import SLIReport, ErrorBudgetReport, SLOStatus


class SLOEngine:
    """
    Evaluates SLO compliance and calculates error budgets.
    """

    MIN_SAMPLES_THRESHOLD = 5

    @classmethod
    async def evaluate_slos(
        cls,
        workspace_id: str,
        session: AsyncSession,
    ) -> Tuple[List[SLIReport], List[ErrorBudgetReport]]:
        slis: List[SLIReport] = []
        budgets: List[ErrorBudgetReport] = []

        # ---------------------------------------------------------------------
        # 1. API Availability SLO (Target: 99.9%)
        # ---------------------------------------------------------------------
        api_reqs = metrics.get_counter("api.requests")
        api_errs = metrics.get_counter("api.errors")
        api_total = int(api_reqs)

        if api_total < cls.MIN_SAMPLES_THRESHOLD:
            api_status = SLOStatus.INSUFFICIENT_DATA
            api_actual = None
            api_consumed = None
            api_remaining = None
            reason = "Sample count below evaluation threshold (minimum 5 requests)."
        else:
            api_success = max(0, api_total - int(api_errs))
            api_actual = round((api_success / api_total) * 100, 2)
            target = 99.9
            total_budget = 0.1  # 100 - 99.9
            error_rate = 100.0 - api_actual
            api_consumed = round(min(100.0, (error_rate / total_budget) * 100), 1)
            api_remaining = max(0.0, round(100.0 - api_consumed, 1))

            if api_actual >= target:
                api_status = SLOStatus.HEALTHY
                reason = f"Operating within error budget ({api_remaining}% remaining)."
            elif api_remaining > 0:
                api_status = SLOStatus.WARNING
                reason = "Error budget partially consumed."
            else:
                api_status = SLOStatus.BREACHED
                reason = "Error budget completely exhausted."

        slis.append(
            SLIReport(
                name="API Availability",
                category="API",
                target_percentage=99.9,
                actual_percentage=api_actual,
                status=api_status,
                sample_count=api_total,
                details={"requests": api_total, "errors": int(api_errs)},
            )
        )
        budgets.append(
            ErrorBudgetReport(
                slo_name="API Availability",
                total_budget_percentage=0.1,
                consumed_percentage=api_consumed,
                remaining_percentage=api_remaining,
                status=api_status,
                status_reason=reason,
            )
        )

        # ---------------------------------------------------------------------
        # 2. Event Processing Success SLO (Target: 99.5%)
        # ---------------------------------------------------------------------
        inbox_stmt = (
            select(
                func.count(EventInboxRecord.id),
                func.count(EventInboxRecord.id).filter(EventInboxRecord.status == EventInboxStatus.PROCESSED),
                func.count(EventInboxRecord.id).filter(EventInboxRecord.status == EventInboxStatus.DEAD_LETTER),
            )
            .where(EventInboxRecord.workspace_id == workspace_id)
        )
        inbox_res = await session.execute(inbox_stmt)
        total_ev, proc_ev, dlq_ev = inbox_res.one()

        if total_ev < cls.MIN_SAMPLES_THRESHOLD:
            ev_status = SLOStatus.INSUFFICIENT_DATA
            ev_actual = None
            ev_consumed = None
            ev_remaining = None
            ev_reason = "Insufficient event throughput for SLO computation."
        else:
            ev_actual = round(((total_ev - dlq_ev) / total_ev) * 100, 2)
            target = 99.5
            total_budget = 0.5
            err_rate = 100.0 - ev_actual
            ev_consumed = round(min(100.0, (err_rate / total_budget) * 100), 1)
            ev_remaining = max(0.0, round(100.0 - ev_consumed, 1))
            ev_status = SLOStatus.HEALTHY if ev_actual >= target else (SLOStatus.WARNING if ev_remaining > 0 else SLOStatus.BREACHED)
            ev_reason = f"Event processing reliability: {ev_remaining}% budget remaining."

        slis.append(
            SLIReport(
                name="Event Processing Success Rate",
                category="EVENT_PROCESSING",
                target_percentage=99.5,
                actual_percentage=ev_actual,
                status=ev_status,
                sample_count=total_ev,
                details={"total_events": total_ev, "processed": proc_ev, "dead_letter": dlq_ev},
            )
        )
        budgets.append(
            ErrorBudgetReport(
                slo_name="Event Processing Success Rate",
                total_budget_percentage=0.5,
                consumed_percentage=ev_consumed,
                remaining_percentage=ev_remaining,
                status=ev_status,
                status_reason=ev_reason,
            )
        )

        # ---------------------------------------------------------------------
        # 3. LLM Availability & Grounding SLO (Target: 99.0%)
        # ---------------------------------------------------------------------
        llm_stmt = (
            select(
                func.count(LLMAnalysisRecord.id),
                func.count(LLMAnalysisRecord.id).filter(LLMAnalysisRecord.fallback_used == False),
                func.count(LLMAnalysisRecord.id).filter(LLMAnalysisRecord.grounding_status == "GROUNDED"),
            )
            .where(LLMAnalysisRecord.workspace_id == workspace_id)
        )
        llm_res = await session.execute(llm_stmt)
        total_llm, non_fb_llm, grounded_llm = llm_res.one()

        if total_llm < cls.MIN_SAMPLES_THRESHOLD:
            llm_status = SLOStatus.INSUFFICIENT_DATA
            llm_actual = None
            llm_consumed = None
            llm_remaining = None
            llm_reason = "Insufficient LLM analysis volume."
        else:
            llm_actual = round((non_fb_llm / total_llm) * 100, 2)
            target = 99.0
            total_budget = 1.0
            err_rate = 100.0 - llm_actual
            llm_consumed = round(min(100.0, (err_rate / total_budget) * 100), 1)
            llm_remaining = max(0.0, round(100.0 - llm_consumed, 1))
            llm_status = SLOStatus.HEALTHY if llm_actual >= target else (SLOStatus.WARNING if llm_remaining > 0 else SLOStatus.BREACHED)
            llm_reason = f"LLM inference reliability: {llm_remaining}% budget remaining."

        slis.append(
            SLIReport(
                name="LLM Service Reliability",
                category="LLM",
                target_percentage=99.0,
                actual_percentage=llm_actual,
                status=llm_status,
                sample_count=total_llm,
                details={"total_requests": total_llm, "non_fallback": non_fb_llm, "grounded": grounded_llm},
            )
        )
        budgets.append(
            ErrorBudgetReport(
                slo_name="LLM Service Reliability",
                total_budget_percentage=1.0,
                consumed_percentage=llm_consumed,
                remaining_percentage=llm_remaining,
                status=llm_status,
                status_reason=llm_reason,
            )
        )

        return slis, budgets
