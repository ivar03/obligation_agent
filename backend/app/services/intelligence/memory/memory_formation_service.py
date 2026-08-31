"""
Memory Formation Service — Phase 16

Transforms authoritative system events (obligation completion, intervention outcomes,
dependency resolutions, negative blockers, and ingested events) into durable,
immutable OrganizationalMemory records with idempotency.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.obligation import Obligation, Intervention
from app.models.memory import OrganizationalMemory
from app.core.status_machine import (
    MemoryType,
    ObligationStatus,
)
from app.schemas.memory import OrganizationalMemoryCreate
from app.services.intelligence.memory.semantic_context_engine import SemanticContextEngine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MemoryFormationService:
    """
    Handles deterministic formation and append-only persistence of organizational memories.
    """

    @classmethod
    async def create_memory(
        cls,
        session: AsyncSession,
        payload: OrganizationalMemoryCreate,
        workspace_id: str = "ws-default",
    ) -> OrganizationalMemory:
        """
        Creates and persists an immutable OrganizationalMemory record.
        """
        mem = OrganizationalMemory(
            workspace_id=workspace_id,
            memory_type=payload.memory_type,
            source_type=payload.source_type,
            source_ref=payload.source_ref,
            obligation_id=payload.obligation_id,
            event_id=payload.event_id,
            owner_id=payload.owner_id,
            content=payload.content,
            semantic_summary=payload.semantic_summary,
            semantic_labels=payload.semantic_labels,
            entities=payload.entities,
            topics=payload.topics,
            outcome=payload.outcome,
            observed_at=payload.observed_at or utc_now(),
            metadata_json=payload.metadata_json or {},
            importance_score=payload.importance_score,
            confidence=payload.confidence,
            is_active=True,
        )
        session.add(mem)
        await session.commit()
        await session.refresh(mem)
        return mem

    @classmethod
    async def record_obligation_completion(
        cls,
        session: AsyncSession,
        obligation: Obligation,
        completion_time: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> Optional[OrganizationalMemory]:
        """
        Forms an OBLIGATION_OUTCOME memory when an obligation completes.
        Idempotent: will not create duplicate completion memory for same obligation.
        """
        # Idempotency check
        stmt = select(OrganizationalMemory).where(
            and_(
                OrganizationalMemory.obligation_id == obligation.id,
                OrganizationalMemory.memory_type == MemoryType.OBLIGATION_OUTCOME,
            )
        )
        res = await session.execute(stmt)
        existing = res.scalars().first()
        if existing:
            return existing

        obs_time = completion_time or utc_now()
        if obs_time.tzinfo is None:
            obs_time = obs_time.replace(tzinfo=timezone.utc)

        # Calculate delay if deadline existed
        delay_hours = 0.0
        is_late = False
        if obligation.deadline:
            dl = obligation.deadline if obligation.deadline.tzinfo else obligation.deadline.replace(tzinfo=timezone.utc)
            diff_sec = (obs_time - dl).total_seconds()
            delay_hours = diff_sec / 3600.0
            is_late = delay_hours > 0.5  # half hour grace period

        outcome = "COMPLETED_LATE" if is_late else "COMPLETED_ON_TIME"
        if obligation.status == ObligationStatus.CANCELLED:
            outcome = "CANCELLED"

        # Semantic parsing
        sem = SemanticContextEngine.extract_semantic_representation(
            text=obligation.action,
            owner=obligation.owner,
            deadline=obligation.deadline,
            obligation_type=obligation.obligation_type.value if hasattr(obligation.obligation_type, "value") else str(obligation.obligation_type),
        )

        content = f"Obligation '{obligation.action}' owned by {obligation.owner or 'Unassigned'} reached outcome {outcome}."
        if is_late:
            content += f" Completed {delay_hours:.1f} hours after deadline."
        else:
            content += " Completed on schedule."
        if notes:
            content += f" Notes: {notes}"

        summary = f"{obligation.owner}: {sem.deliverable or obligation.action} ({outcome})"

        payload = OrganizationalMemoryCreate(
            memory_type=MemoryType.OBLIGATION_OUTCOME,
            source_type="obligation",
            source_ref=f"obligation:{obligation.id}",
            obligation_id=obligation.id,
            owner_id=obligation.owner,
            content=content,
            semantic_summary=summary,
            semantic_labels=[outcome, sem.obligation_type or "OWED_BY_ME"] + ([sem.action] if sem.action else []),
            entities=sem.entities,
            topics=sem.topics,
            outcome=outcome,
            observed_at=obs_time,
            metadata_json={
                "delay_hours": delay_hours,
                "is_late": is_late,
                "deadline": obligation.deadline.isoformat() if obligation.deadline else None,
                "beneficiary": obligation.beneficiary,
                "action": sem.action,
                "deliverable": sem.deliverable,
            },
            importance_score=0.7 if is_late else 0.5,
            confidence=1.0,
        )

        return await cls.create_memory(session, payload, workspace_id=obligation.workspace_id)

    @classmethod
    async def record_intervention_outcome(
        cls,
        session: AsyncSession,
        intervention: Intervention,
        outcome_status: str,
        response_summary: Optional[str] = None,
    ) -> Optional[OrganizationalMemory]:
        """
        Forms an INTERVENTION_OUTCOME memory when human intervention outcome is recorded.
        Idempotent for the specific intervention.
        """
        stmt = select(OrganizationalMemory).where(
            and_(
                OrganizationalMemory.source_ref == f"intervention:{intervention.id}",
                OrganizationalMemory.memory_type == MemoryType.INTERVENTION_OUTCOME,
            )
        )
        res = await session.execute(stmt)
        existing = res.scalars().first()
        if existing:
            return existing

        sem = SemanticContextEngine.extract_semantic_representation(text=intervention.title or intervention.rationale or "")

        content = (
            f"Intervention '{intervention.title}' ({intervention.intervention_type}) targeted {intervention.target_owner}. "
            f"Resulted in outcome: {outcome_status}. {response_summary or ''}"
        )
        summary = f"Intervention for {intervention.target_owner} ➔ {outcome_status}"

        payload = OrganizationalMemoryCreate(
            memory_type=MemoryType.INTERVENTION_OUTCOME,
            source_type="intervention",
            source_ref=f"intervention:{intervention.id}",
            obligation_id=intervention.obligation_id,
            owner_id=intervention.target_owner,
            content=content.strip(),
            semantic_summary=summary,
            semantic_labels=[str(intervention.intervention_type), outcome_status],
            entities=sem.entities,
            topics=sem.topics,
            outcome=outcome_status,
            observed_at=utc_now(),
            metadata_json={
                "intervention_type": str(intervention.intervention_type),
                "urgency": intervention.urgency,
                "chain_depth": intervention.chain_depth,
            },
            importance_score=0.6,
            confidence=1.0,
        )
        return await cls.create_memory(session, payload, workspace_id=intervention.workspace_id)

    @classmethod
    async def record_dependency_resolution(
        cls,
        session: AsyncSession,
        upstream_obligation: Obligation,
        downstream_obligations: List[Obligation],
        workspace_id: str = "ws-default",
    ) -> OrganizationalMemory:
        """
        Forms a DEPENDENCY_PATTERN memory recording how resolving an upstream obligation
        unblocked downstream dependents.
        """
        downstream_names = [d.action for d in downstream_obligations]
        content = (
            f"Completion of upstream '{upstream_obligation.action}' by {upstream_obligation.owner} "
            f"unblocked {len(downstream_obligations)} downstream commitments: {', '.join(downstream_names)}."
        )
        summary = f"Upstream '{upstream_obligation.action}' unblocked {len(downstream_obligations)} dependent(s)"

        sem = SemanticContextEngine.extract_semantic_representation(text=upstream_obligation.action)

        payload = OrganizationalMemoryCreate(
            memory_type=MemoryType.DEPENDENCY_PATTERN,
            source_type="graph_cascade",
            source_ref=f"dependency_cascade:{upstream_obligation.id}",
            obligation_id=upstream_obligation.id,
            owner_id=upstream_obligation.owner,
            content=content,
            semantic_summary=summary,
            semantic_labels=["DEPENDENCY_CASCADE", "UNBLOCKED"],
            entities=sem.entities,
            topics=sem.topics,
            outcome="UNBLOCKED_CASCADE",
            observed_at=utc_now(),
            metadata_json={
                "upstream_owner": upstream_obligation.owner,
                "unblocked_count": len(downstream_obligations),
                "downstream_ids": [d.id for d in downstream_obligations],
                "downstream_owners": list(set([d.owner for d in downstream_obligations if d.owner])),
            },
            importance_score=0.7,
            confidence=1.0,
        )
        return await cls.create_memory(session, payload, workspace_id=workspace_id)

    @classmethod
    async def record_blocker_pattern(
        cls,
        session: AsyncSession,
        obligation: Obligation,
        blocker_reason: str,
        error_details: Optional[Dict[str, Any]] = None,
        workspace_id: str = "ws-default",
    ) -> OrganizationalMemory:
        """
        Forms a BLOCKER_PATTERN memory capturing an observed impediment.
        """
        sem = SemanticContextEngine.extract_semantic_representation(text=f"{obligation.action} - {blocker_reason}")

        content = f"Obligation '{obligation.action}' (Owner: {obligation.owner}) was impeded by blocker: {blocker_reason}."
        summary = f"Blocker on '{obligation.action}': {blocker_reason}"

        payload = OrganizationalMemoryCreate(
            memory_type=MemoryType.BLOCKER_PATTERN,
            source_type="blocker_observation",
            source_ref=f"blocker:{obligation.id}:{int(utc_now().timestamp())}",
            obligation_id=obligation.id,
            owner_id=obligation.owner,
            content=content,
            semantic_summary=summary,
            semantic_labels=["BLOCKER"] + sem.blocker_terms,
            entities=sem.entities,
            topics=sem.topics,
            outcome="BLOCKED",
            observed_at=utc_now(),
            metadata_json={
                "blocker_reason": blocker_reason,
                "blocker_terms": sem.blocker_terms,
                "error_details": error_details or {},
            },
            importance_score=0.8,
            confidence=0.9,
        )
        return await cls.create_memory(session, payload, workspace_id=workspace_id)
