"""
Phase 19 System Integrity Checker.

Read-only invariant verification for obligations, evidence, decisions, executions,
and audit records to ensure complete safety and human-in-the-loop adherence.
"""

from typing import Dict, Any, List
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.obligation import Obligation, Evidence
from app.models.decision import DecisionPlan
from app.models.execution import ExecutionRecord
from app.models.audit import AuditEvent


class IntegrityViolation:
    def __init__(self, rule_id: str, severity: str, entity_type: str, entity_id: str, description: str):
        self.rule_id = rule_id
        self.severity = severity  # "CRITICAL", "WARNING", "INFO"
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "description": self.description,
        }


class IntegrityChecker:
    """
    Scans the database for invariant compliance without altering state.
    """

    @classmethod
    async def verify_all(cls, session: AsyncSession, workspace_id: str = None) -> Dict[str, Any]:
        violations: List[IntegrityViolation] = []

        # 1. Check Obligations
        ob_stmt = select(Obligation)
        if workspace_id:
            ob_stmt = ob_stmt.where(Obligation.workspace_id == workspace_id)
        res = await session.execute(ob_stmt)
        obligations = res.scalars().all()

        for ob in obligations:
            # Invariant: Completed obligation must have completed_at timestamp
            if ob.status == "COMPLETE" and not ob.completed_at:
                violations.append(IntegrityViolation(
                    rule_id="OB_COMPLETED_NO_TIMESTAMP",
                    severity="WARNING",
                    entity_type="obligation",
                    entity_id=ob.id,
                    description=f"Obligation [{ob.id}] is marked COMPLETE but lacks completed_at timestamp.",
                ))

        # 2. Check Evidence
        ev_stmt = select(Evidence)
        if workspace_id:
            ev_stmt = ev_stmt.where(Evidence.workspace_id == workspace_id)
        ev_res = await session.execute(ev_stmt)
        evidences = ev_res.scalars().all()

        for ev in evidences:
            corr_status = getattr(ev.correlation_status, "value", str(ev.correlation_status))
            if corr_status == "CONFIRMED" and not getattr(ev, "confirmed_at", None) and not ev.observed_at:
                violations.append(IntegrityViolation(
                    rule_id="EV_CONFIRMED_NO_TIMESTAMP",
                    severity="WARNING",
                    entity_type="evidence",
                    entity_id=ev.id,
                    description=f"Evidence [{ev.id}] is confirmed but has no observed timestamp.",
                ))

        # 3. Check Decision Plans
        dp_stmt = select(DecisionPlan)
        if workspace_id:
            dp_stmt = dp_stmt.where(DecisionPlan.workspace_id == workspace_id)
        dp_res = await session.execute(dp_stmt)
        plans = dp_res.scalars().all()

        for plan in plans:
            plan_status = getattr(plan.status, "value", str(plan.status))
            if plan_status == "APPROVED" and not plan.approved_at:
                violations.append(IntegrityViolation(
                    rule_id="PLAN_APPROVED_NO_TIMESTAMP",
                    severity="CRITICAL",
                    entity_type="decision_plan",
                    entity_id=plan.id,
                    description=f"Decision Plan [{plan.id}] is marked APPROVED but lacks approved_at timestamp.",
                ))

        # 4. Check Execution Records
        ex_stmt = select(ExecutionRecord)
        if workspace_id:
            ex_stmt = ex_stmt.where(ExecutionRecord.workspace_id == workspace_id)
        ex_res = await session.execute(ex_stmt)
        executions = ex_res.scalars().all()

        for ex in executions:
            ex_status = getattr(ex.status, "value", str(ex.status))
            if ex_status == "DELIVERED":
                if not ex.executed_at:
                    violations.append(IntegrityViolation(
                        rule_id="EXEC_DELIVERED_NO_TIMESTAMP",
                        severity="CRITICAL",
                        entity_type="execution_record",
                        entity_id=ex.id,
                        description=f"Execution [{ex.id}] is DELIVERED but lacks executed_at timestamp.",
                    ))
                if not ex.provider_execution_ref:
                    violations.append(IntegrityViolation(
                        rule_id="EXEC_DELIVERED_NO_REF",
                        severity="CRITICAL",
                        entity_type="execution_record",
                        entity_id=ex.id,
                        description=f"Execution [{ex.id}] is DELIVERED but lacks provider_execution_ref.",
                    ))

        # 5. Check Audit Log Leakage
        audit_stmt = select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(200)
        if workspace_id:
            audit_stmt = audit_stmt.where(AuditEvent.workspace_id == workspace_id)
        audit_res = await session.execute(audit_stmt)
        audits = audit_res.scalars().all()

        from app.core.sanitizer import is_sensitive_key
        for a in audits:
            metadata = a.audit_metadata or {}
            for k in metadata.keys():
                if is_sensitive_key(k) and metadata[k] != "[REDACTED]":
                    violations.append(IntegrityViolation(
                        rule_id="AUDIT_UNREDACTED_SECRET",
                        severity="CRITICAL",
                        entity_type="audit_event",
                        entity_id=str(a.id),
                        description=f"Audit Event [{a.id}] contains unredacted sensitive key '{k}'.",
                    ))

        critical_count = sum(1 for v in violations if v.severity == "CRITICAL")
        warning_count = sum(1 for v in violations if v.severity == "WARNING")

        return {
            "status": "passed" if critical_count == 0 else "failed",
            "critical_violations": critical_count,
            "warning_violations": warning_count,
            "total_violations": len(violations),
            "scanned": {
                "obligations": len(obligations),
                "evidence": len(evidences),
                "decision_plans": len(plans),
                "executions": len(executions),
                "audits_sampled": len(audits),
            },
            "violations": [v.to_dict() for v in violations],
        }
