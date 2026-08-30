from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.core.logging import logger
from app.core.status_machine import (
    ObligationStatus,
    EvidenceType,
    CorrelationStatus,
    EventSemanticRole,
)
from app.core.intervention_status import InterventionStatus, InterventionOutcome
from app.models.obligation import Obligation, Evidence, Intervention, IngestedEventRecord
from app.schemas.obligation import (
    ExternalEvent,
    EventAnalysisResponse,
    EventIngestionResponse,
    EvidenceResponse,
    CorrelationMatch,
    IngestedEventResponse,
    IngestedEventListResponse,
    IngestionResultResponse,
    EventSimulateRequest,
)
from app.services.correlation_service import EvidenceCorrelationService
from app.services.providers.registry import provider_registry


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventIngestionService:
    """
    Central orchestration service for continuous event ingestion, provider normalization,
    deduplication, semantic classification, evidence candidate generation, closed-loop
    intervention correlation, and immutable event audit logging.
    """

    @staticmethod
    async def get_candidate_obligations(session: AsyncSession) -> List[Obligation]:
        """Fetches active obligations eligible for evidence correlation."""
        stmt = (
            select(Obligation)
            .where(
                Obligation.status.notin_([
                    ObligationStatus.COMPLETED,
                    ObligationStatus.CANCELLED,
                ])
            )
            .order_by(desc(Obligation.created_at))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def analyze_event(session: AsyncSession, event: ExternalEvent) -> EventAnalysisResponse:
        """
        Stateless event analysis.
        Scores correlation against active obligations without saving to the database.
        """
        candidates = await EventIngestionService.get_candidate_obligations(session)
        return EvidenceCorrelationService.correlate(event, candidates)

    @classmethod
    async def ingest_from_provider(
        cls,
        session: AsyncSession,
        provider_name: str,
        raw_payload: Dict[str, Any],
    ) -> IngestionResultResponse:
        """
        Ingests an event from a specific registered provider (Mock, Slack, Webhook, etc.).
        Normalizes the provider-specific payload and runs the core ingestion pipeline.
        """
        provider = provider_registry.get(provider_name)
        normalized_event = provider.normalize_event(raw_payload)
        return await cls.ingest_normalized_event(
            session=session,
            event=normalized_event,
            provider_name=provider.provider_name,
            raw_payload=raw_payload,
        )

    @classmethod
    async def ingest_normalized_event(
        cls,
        session: AsyncSession,
        event: ExternalEvent,
        provider_name: str = "direct",
        raw_payload: Optional[Dict[str, Any]] = None,
    ) -> IngestionResultResponse:
        """
        Core idempotent ingestion pipeline:
        1. Validates event payload.
        2. Deduplicates against existing ingested events.
        3. Classifies semantic role and calculates correlation against active obligations.
        4. Persists suggested evidence candidates (Human confirmation preserved).
        5. Updates active interventions if a response/progress signal is detected.
        6. Persists immutable IngestedEventRecord audit trail.
        7. Returns comprehensive IngestionResultResponse.
        """
        observed_time = event.timestamp or utc_now()

        # 1. Validation check
        if not event.content or not event.content.strip():
            audit_record = IngestedEventRecord(
                provider=provider_name,
                source_type=event.source_type,
                source_ref=event.source_ref,
                sender=event.sender,
                recipients=event.recipients,
                content="",
                semantic_role=EventSemanticRole.IRRELEVANT,
                processing_status="REJECTED",
                match_explanation="Empty event content",
                action_taken="NONE",
                raw_payload=raw_payload,
                received_at=observed_time,
            )
            session.add(audit_record)
            await session.flush()
            return IngestionResultResponse(
                status="REJECTED",
                event_id=audit_record.id,
                provider=provider_name,
                semantic_role=EventSemanticRole.IRRELEVANT,
                matches=[],
                evidence_records=[],
                affected_obligation_ids=[],
                updated_intervention_ids=[],
                message="Event rejected: empty content.",
            )

        # 2. Idempotent Deduplication Check
        if event.source_ref:
            dup_stmt = select(IngestedEventRecord).where(
                and_(
                    IngestedEventRecord.provider == provider_name,
                    IngestedEventRecord.source_ref == event.source_ref,
                )
            )
            dup_res = await session.execute(dup_stmt)
            existing_event = dup_res.scalar_one_or_none()
            if existing_event:
                logger.info(
                    f"Duplicate event ignored: Provider={provider_name}, Ref={event.source_ref} (Event ID={existing_event.id})"
                )
                # Retrieve existing evidence records for this source_ref
                existing_ev_stmt = select(Evidence).where(Evidence.source_ref == event.source_ref)
                existing_ev_res = await session.execute(existing_ev_stmt)
                existing_evs = [EvidenceResponse.model_validate(e) for e in existing_ev_res.scalars().all()]

                return IngestionResultResponse(
                    status="DUPLICATE",
                    event_id=existing_event.id,
                    provider=provider_name,
                    semantic_role=existing_event.semantic_role,
                    matches=[],
                    evidence_records=existing_evs,
                    affected_obligation_ids=[existing_event.correlated_obligation_id] if existing_event.correlated_obligation_id else [],
                    updated_intervention_ids=[existing_event.resolved_intervention_id] if existing_event.resolved_intervention_id else [],
                    message=f"Duplicate event detected for {provider_name}:{event.source_ref}. Already processed.",
                )

        # 3. Correlation & Classification
        candidates = await cls.get_candidate_obligations(session)
        analysis = EvidenceCorrelationService.correlate(event, candidates)

        # Map source_type to EvidenceType enum
        ev_type = EvidenceType.MESSAGE
        if event.source_type.lower() in ["file", "document", "attachment"]:
            ev_type = EvidenceType.FILE
        elif event.source_type.lower() in ["audit_log", "system"]:
            ev_type = EvidenceType.SYSTEM

        created_evidence: List[EvidenceResponse] = []
        affected_obligation_ids: List[str] = []
        updated_intervention_ids: List[str] = []
        primary_evidence_id: Optional[str] = None
        primary_obligation_id: Optional[str] = None
        primary_confidence: Optional[float] = None

        # 4. Evidence Persistence for Correlated Obligations
        for match in analysis.matches:
            if match.correlation_confidence >= 0.50 or (
                match.correlation_confidence >= 0.30 and match.semantic_role in [EventSemanticRole.NON_COMPLETION_SIGNAL, EventSemanticRole.PROGRESS_UPDATE]
            ):
                affected_obligation_ids.append(match.obligation_id)
                if not primary_obligation_id:
                    primary_obligation_id = match.obligation_id
                    primary_confidence = match.correlation_confidence

                # Deduplicate evidence per obligation
                if event.source_ref:
                    ev_dup_stmt = select(Evidence).where(
                        and_(
                            Evidence.source_type == event.source_type,
                            Evidence.source_ref == event.source_ref,
                            Evidence.obligation_id == match.obligation_id,
                        )
                    )
                    ev_dup_res = await session.execute(ev_dup_stmt)
                    existing_ev = ev_dup_res.scalar_one_or_none()
                    if existing_ev:
                        created_evidence.append(EvidenceResponse.model_validate(existing_ev))
                        if not primary_evidence_id:
                            primary_evidence_id = existing_ev.id
                        continue

                # Create suggested evidence record
                new_evidence = Evidence(
                    obligation_id=match.obligation_id,
                    evidence_type=ev_type,
                    source_type=event.source_type,
                    source_ref=event.source_ref,
                    content=event.content,
                    correlation_status=CorrelationStatus.SUGGESTED,
                    correlation_confidence=match.correlation_confidence,
                    semantic_role=match.semantic_role,
                    reasoning=match.reasoning,
                    extra_metadata=event.metadata,
                    actor=event.sender,
                    observed_at=observed_time,
                )
                session.add(new_evidence)
                await session.flush()
                await session.refresh(new_evidence)

                if not primary_evidence_id:
                    primary_evidence_id = new_evidence.id
                created_evidence.append(EvidenceResponse.model_validate(new_evidence))

                # 5. Closed-Loop Intervention Integration
                inv_stmt = select(Intervention).where(
                    and_(
                        Intervention.obligation_id == match.obligation_id,
                        Intervention.status.in_([
                            InterventionStatus.PENDING_REVIEW,
                            InterventionStatus.APPROVED,
                            InterventionStatus.SCHEDULED,
                            InterventionStatus.READY_TO_EXECUTE,
                            InterventionStatus.EXECUTED,
                        ])
                    )
                )
                inv_res = await session.execute(inv_stmt)
                active_interventions = list(inv_res.scalars().all())

                for active_inv in active_interventions:
                    audit_trail = list(active_inv.audit_trail or [])

                    if match.semantic_role == EventSemanticRole.PROGRESS_UPDATE:
                        active_inv.outcome = InterventionOutcome.PROGRESS_REPORTED
                        if active_inv.status in [InterventionStatus.EXECUTED, InterventionStatus.READY_TO_EXECUTE]:
                            active_inv.status = InterventionStatus.ACKNOWLEDGED
                        audit_trail.append({
                            "event": "PROGRESS_DETECTED",
                            "actor": event.sender or "EXTERNAL_EVENT",
                            "timestamp": utc_now().isoformat(),
                            "details": {"source_ref": event.source_ref, "content_snippet": event.content[:80]},
                        })
                        active_inv.audit_trail = audit_trail
                        updated_intervention_ids.append(active_inv.id)

                    elif match.semantic_role == EventSemanticRole.COMPLETION_SIGNAL:
                        audit_trail.append({
                            "event": "COMPLETION_SIGNAL_RECEIVED",
                            "actor": event.sender or "EXTERNAL_EVENT",
                            "timestamp": utc_now().isoformat(),
                            "details": {"source_ref": event.source_ref, "evidence_id": new_evidence.id},
                        })
                        active_inv.audit_trail = audit_trail
                        updated_intervention_ids.append(active_inv.id)

        # 6. Determine Audit Processing Status & Action Taken
        processing_status = "PROCESSED" if (len(created_evidence) > 0 or len(analysis.matches) > 0) else "NO_MATCH"
        action_taken = "SUGGESTED_EVIDENCE_CREATED" if len(created_evidence) > 0 else (
            "INTERVENTION_UPDATED" if len(updated_intervention_ids) > 0 else "NONE"
        )

        # 7. Persist IngestedEventRecord
        audit_record = IngestedEventRecord(
            provider=provider_name,
            source_type=event.source_type,
            source_ref=event.source_ref,
            sender=event.sender,
            recipients=event.recipients,
            content=event.content,
            semantic_role=analysis.semantic_role,
            processing_status=processing_status,
            candidate_obligation_ids=[o.id for o in candidates],
            correlated_obligation_id=primary_obligation_id,
            evidence_id=primary_evidence_id,
            correlation_confidence=primary_confidence,
            match_explanation=analysis.summary,
            action_taken=action_taken,
            resolved_intervention_id=updated_intervention_ids[0] if updated_intervention_ids else None,
            raw_payload=raw_payload,
            received_at=observed_time,
        )
        session.add(audit_record)
        await session.flush()
        await session.refresh(audit_record)

        logger.info(
            f"Event ingested successfully: ID={audit_record.id} Provider={provider_name} Role={analysis.semantic_role.value} Status={processing_status}"
        )

        return IngestionResultResponse(
            status=processing_status,
            event_id=audit_record.id,
            provider=provider_name,
            semantic_role=analysis.semantic_role,
            matches=analysis.matches,
            evidence_records=created_evidence,
            affected_obligation_ids=list(set(affected_obligation_ids)),
            updated_intervention_ids=list(set(updated_intervention_ids)),
            message=analysis.summary,
        )

    @staticmethod
    async def list_events(
        session: AsyncSession,
        provider: Optional[str] = None,
        semantic_role: Optional[EventSemanticRole] = None,
        processing_status: Optional[str] = None,
        source_ref: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> IngestedEventListResponse:
        """Queries historical ingested event audit records with filtering."""
        query = select(IngestedEventRecord)

        if provider:
            query = query.where(IngestedEventRecord.provider == provider.lower())
        if semantic_role:
            query = query.where(IngestedEventRecord.semantic_role == semantic_role)
        if processing_status:
            query = query.where(IngestedEventRecord.processing_status == processing_status)
        if source_ref:
            query = query.where(IngestedEventRecord.source_ref == source_ref)

        # Count total
        count_stmt = select(func.count()).select_from(query.subquery())
        count_res = await session.execute(count_stmt)
        total = count_res.scalar_one()

        # Fetch records
        query = query.order_by(desc(IngestedEventRecord.received_at)).offset(offset).limit(limit)
        res = await session.execute(query)
        records = list(res.scalars().all())

        return IngestedEventListResponse(
            items=[IngestedEventResponse.model_validate(r) for r in records],
            total=total,
        )

    @staticmethod
    async def get_event_by_id(session: AsyncSession, event_id: str) -> IngestedEventResponse:
        """Retrieves a single ingested event audit record by ID."""
        stmt = select(IngestedEventRecord).where(IngestedEventRecord.id == event_id)
        res = await session.execute(stmt)
        record = res.scalar_one_or_none()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ingested event '{event_id}' not found.",
            )
        return IngestedEventResponse.model_validate(record)

    @classmethod
    async def simulate_scenario(
        cls,
        session: AsyncSession,
        payload: EventSimulateRequest,
    ) -> IngestionResultResponse:
        """
        Triggers a development simulation of a canonical scenario using MockProvider.
        """
        raw = {
            "scenario": payload.scenario,
            "sender": payload.sender,
            "recipients": payload.recipients,
            "content": payload.content,
            "metadata": payload.metadata,
        }
        return await cls.ingest_from_provider(
            session=session,
            provider_name="mock",
            raw_payload=raw,
        )

    # Legacy method for backwards compatibility with Phase 4 tests
    @staticmethod
    async def ingest_event(session: AsyncSession, event: ExternalEvent) -> EventIngestionResponse:
        """
        Backwards-compatible bridge for Phase 4 legacy endpoints and tests.
        """
        result = await EventIngestionService.ingest_normalized_event(
            session=session,
            event=event,
            provider_name="direct",
        )
        return EventIngestionResponse(
            ingested=len(result.evidence_records) > 0,
            semantic_role=result.semantic_role,
            evidence_records=result.evidence_records,
            matches=result.matches,
            message=result.message,
        )
