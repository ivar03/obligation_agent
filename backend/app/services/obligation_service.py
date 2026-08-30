from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, func, or_, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.core.logging import logger
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    EvidenceType,
    CorrelationStatus,
    EventSemanticRole,
    RiskLevel,
    validate_status_transition,
)
from app.models.obligation import Obligation, ObligationEdge, Evidence
from app.schemas.obligation import (
    ObligationCreate,
    ObligationUpdate,
    ObligationStatusUpdate,
    ObligationResponse,
    ObligationListResponse,
    DashboardSummaryResponse,
    ObligationEdgeCreate,
    ObligationEdgeResponse,
    ObligationGraphResponse,
    EvidenceResponse,
    RiskAssessmentResponse,
    BulkRiskResponse,
)


def is_obligation_at_risk(obligation: Obligation) -> bool:
    if obligation.status in [ObligationStatus.COMPLETED, ObligationStatus.CANCELLED]:
        return False
    if obligation.status in [ObligationStatus.OVERDUE, ObligationStatus.BLOCKED]:
        return True
    if obligation.deadline:
        now = datetime.now(timezone.utc)
        deadline_tz = obligation.deadline
        if deadline_tz.tzinfo is None:
            deadline_tz = deadline_tz.replace(tzinfo=timezone.utc)
        # Overdue
        if deadline_tz < now:
            return True
        # Approaching deadline within 48 hours
        if deadline_tz <= now + timedelta(hours=48):
            return True
    return False


def to_response_dto(obligation: Obligation) -> ObligationResponse:
    at_risk = is_obligation_at_risk(obligation)
    return ObligationResponse(
        id=obligation.id,
        owner=obligation.owner,
        beneficiary=obligation.beneficiary,
        action=obligation.action,
        deadline=obligation.deadline,
        conditions=obligation.conditions,
        evidence=obligation.evidence,
        status=obligation.status,
        next_action=obligation.next_action,
        block_reason=obligation.block_reason,
        source_ref=obligation.source_ref,
        obligation_type=obligation.obligation_type,
        confidence=obligation.confidence,
        created_at=obligation.created_at,
        updated_at=obligation.updated_at,
        is_at_risk=at_risk,
    )


class ObligationService:

    @staticmethod
    async def create(session: AsyncSession, data: ObligationCreate) -> ObligationResponse:
        logger.info(f"Creating obligation: {data.owner} -> {data.beneficiary}: {data.action}")
        obligation = Obligation(
            owner=data.owner,
            beneficiary=data.beneficiary,
            action=data.action,
            deadline=data.deadline,
            conditions=data.conditions,
            evidence=data.evidence or [],
            status=data.status,
            next_action=data.next_action,
            block_reason=None,
            source_ref=data.source_ref,
            obligation_type=data.obligation_type,
            confidence=data.confidence,
        )
        session.add(obligation)
        await session.flush()
        await session.refresh(obligation)
        return to_response_dto(obligation)

    @staticmethod
    async def get_by_id(session: AsyncSession, obligation_id: str) -> Optional[ObligationResponse]:
        query = select(Obligation).where(Obligation.id == obligation_id)
        result = await session.execute(query)
        obligation = result.scalar_one_or_none()
        if not obligation:
            return None
        return to_response_dto(obligation)

    @staticmethod
    async def list_all(
        session: AsyncSession,
        obligation_type: Optional[ObligationType] = None,
        status: Optional[ObligationStatus] = None,
        search: Optional[str] = None,
        is_at_risk: Optional[bool] = None,
        is_blocked: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ObligationListResponse:
        query = select(Obligation)

        if obligation_type:
            query = query.where(Obligation.obligation_type == obligation_type)

        if status:
            query = query.where(Obligation.status == status)

        if is_blocked is True:
            query = query.where(Obligation.status == ObligationStatus.BLOCKED)

        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Obligation.action.ilike(search_pattern),
                    Obligation.owner.ilike(search_pattern),
                    Obligation.beneficiary.ilike(search_pattern),
                    Obligation.next_action.ilike(search_pattern),
                )
            )

        query = query.order_by(desc(Obligation.created_at))
        result = await session.execute(query)
        obligations = result.scalars().all()

        dtos = [to_response_dto(ob) for ob in obligations]

        if is_at_risk is not None:
            dtos = [d for d in dtos if d.is_at_risk == is_at_risk]

        total = len(dtos)
        paginated = dtos[offset: offset + limit]

        return ObligationListResponse(items=paginated, total=total)

    @staticmethod
    async def update(session: AsyncSession, obligation_id: str, data: ObligationUpdate) -> Optional[ObligationResponse]:
        query = select(Obligation).where(Obligation.id == obligation_id)
        result = await session.execute(query)
        obligation = result.scalar_one_or_none()
        if not obligation:
            return None

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(obligation, key, value)

        await session.flush()
        await session.refresh(obligation)
        return to_response_dto(obligation)

    @staticmethod
    async def update_status(
        session: AsyncSession, obligation_id: str, status_data: ObligationStatusUpdate
    ) -> Optional[ObligationResponse]:
        from app.services.graph_service import GraphService

        query = select(Obligation).where(Obligation.id == obligation_id)
        result = await session.execute(query)
        obligation = result.scalar_one_or_none()
        if not obligation:
            return None

        # Validate controlled status transition
        validate_status_transition(obligation.status, status_data.status)
        old_status = obligation.status
        obligation.status = status_data.status

        # If evidence was supplied, record it
        current_evidence = list(obligation.evidence or [])
        evidence_entry = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "status_transition": f"{old_status.value} -> {status_data.status.value}",
        }
        if status_data.evidence:
            evidence_entry.update(status_data.evidence)
        if status_data.reason:
            evidence_entry["reason"] = status_data.reason

        current_evidence.append(evidence_entry)
        obligation.evidence = current_evidence

        # If transitioning to COMPLETED, clear block_reason and auto-resolve active interventions
        if status_data.status == ObligationStatus.COMPLETED:
            obligation.block_reason = None
            from app.services.intervention_service import InterventionService
            await InterventionService.auto_resolve_for_obligation(session, obligation_id, reason="Obligation completed via status transition.")

        await session.flush()

        # Authoritative graph propagation: cascade changes to dependents & re-evaluate
        dependents = await GraphService.get_dependents(session, obligation_id)
        for dep in dependents:
            await GraphService.evaluate_and_propagate(session, dep.id)

        await session.refresh(obligation)
        return to_response_dto(obligation)

    @staticmethod
    async def delete(session: AsyncSession, obligation_id: str) -> bool:
        from app.services.graph_service import GraphService

        query = select(Obligation).where(Obligation.id == obligation_id)
        result = await session.execute(query)
        obligation = result.scalar_one_or_none()
        if not obligation:
            return False

        # Find dependents before deletion so we can re-evaluate them
        dependents = await GraphService.get_dependents(session, obligation_id)

        await session.delete(obligation)
        await session.flush()

        # Re-evaluate dependents now that the obligation is deleted
        for dep in dependents:
            await GraphService.evaluate_and_propagate(session, dep.id)

        return True

    @staticmethod
    async def get_dashboard_summary(session: AsyncSession) -> DashboardSummaryResponse:
        query = select(Obligation).order_by(desc(Obligation.created_at))
        result = await session.execute(query)
        all_obligations = result.scalars().all()

        all_dtos = [to_response_dto(ob) for ob in all_obligations]

        active_obligations = [
            ob for ob in all_dtos
            if ob.status not in [ObligationStatus.COMPLETED, ObligationStatus.CANCELLED]
        ]

        you_owe = [ob for ob in active_obligations if ob.obligation_type == ObligationType.OWED_BY_ME]
        others_owe = [ob for ob in active_obligations if ob.obligation_type == ObligationType.OWED_TO_ME]
        at_risk = [ob for ob in active_obligations if ob.is_at_risk]
        completed = [ob for ob in all_dtos if ob.status == ObligationStatus.COMPLETED]
        blocked = [ob for ob in all_dtos if ob.status == ObligationStatus.BLOCKED]

        # Pending suggested evidence count
        ev_query = select(func.count(Evidence.id)).where(Evidence.correlation_status == CorrelationStatus.SUGGESTED)
        ev_res = await session.execute(ev_query)
        pending_ev_count = ev_res.scalar_one() or 0

        return DashboardSummaryResponse(
            you_owe_count=len(you_owe),
            others_owe_count=len(others_owe),
            at_risk_count=len(at_risk),
            completed_count=len(completed),
            blocked_count=len(blocked),
            pending_evidence_count=pending_ev_count,
            you_owe_obligations=you_owe[:10],
            others_owe_obligations=others_owe[:10],
            at_risk_obligations=at_risk[:10],
        )

    @staticmethod
    async def create_edge(session: AsyncSession, data: ObligationEdgeCreate) -> ObligationEdgeResponse:
        from app.services.graph_service import GraphService
        return await GraphService.create_edge(session, data)

    @staticmethod
    async def delete_edge(session: AsyncSession, edge_id: str) -> bool:
        from app.services.graph_service import GraphService
        return await GraphService.remove_edge(session, edge_id)

    @staticmethod
    async def get_graph(session: AsyncSession, obligation_id: str) -> ObligationGraphResponse:
        from app.services.graph_service import GraphService
        return await GraphService.get_graph_for_obligation(session, obligation_id)

    # ==========================================
    # PHASE 4: EVIDENCE MANAGEMENT & CONFIRMATION
    # ==========================================

    @staticmethod
    async def get_evidence(session: AsyncSession, obligation_id: str) -> List[EvidenceResponse]:
        stmt = (
            select(Evidence)
            .where(Evidence.obligation_id == obligation_id)
            .order_by(desc(Evidence.observed_at))
        )
        result = await session.execute(stmt)
        records = result.scalars().all()
        return [EvidenceResponse.model_validate(r) for r in records]

    @staticmethod
    async def confirm_evidence(
        session: AsyncSession, obligation_id: str, evidence_id: str, notes: Optional[str] = None
    ) -> Tuple[ObligationResponse, EvidenceResponse]:
        from app.services.graph_service import GraphService

        # 1. Fetch obligation and evidence
        obligation = await session.get(Obligation, obligation_id)
        evidence = await session.get(Evidence, evidence_id)

        if not obligation or not evidence or evidence.obligation_id != obligation_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Obligation or Evidence record not found.",
            )

        # 2. Validate controlled transition to COMPLETED
        validate_status_transition(obligation.status, ObligationStatus.COMPLETED)

        # 3. Update evidence state
        evidence.correlation_status = CorrelationStatus.CONFIRMED

        # 4. Transition obligation status
        old_status = obligation.status
        obligation.status = ObligationStatus.COMPLETED
        obligation.block_reason = None

        # 5. Attach audit entry
        current_ev = list(obligation.evidence or [])
        evidence_entry = {
            "type": "evidence_confirmation",
            "event": "OBLIGATION_COMPLETED_VIA_EVIDENCE",
            "evidence_id": evidence.id,
            "evidence_content": evidence.content,
            "source_type": evidence.source_type,
            "source_ref": evidence.source_ref,
            "confidence": evidence.correlation_confidence,
            "notes": notes,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "status_transition": f"{old_status.value} -> COMPLETED",
        }
        current_ev.append(evidence_entry)
        obligation.evidence = current_ev

        await session.flush()

        # 6. Auto-resolve active interventions for completed obligation
        from app.services.intervention_service import InterventionService
        await InterventionService.auto_resolve_for_obligation(
            session, obligation_id, reason="Obligation completed via evidence confirmation."
        )

        # 7. Authoritative graph propagation: unblock downstream dependents
        dependents = await GraphService.get_dependents(session, obligation_id)
        for dep in dependents:
            await GraphService.evaluate_and_propagate(session, dep.id)

        await session.refresh(obligation)
        await session.refresh(evidence)

        logger.info(
            f"EvidenceConfirmed: Obligation [{obligation_id}] fulfilled via Evidence [{evidence_id}]."
        )
        return to_response_dto(obligation), EvidenceResponse.model_validate(evidence)

    @staticmethod
    async def reject_evidence(
        session: AsyncSession, obligation_id: str, evidence_id: str
    ) -> EvidenceResponse:
        evidence = await session.get(Evidence, evidence_id)
        if not evidence or evidence.obligation_id != obligation_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence record not found for this obligation.",
            )

        evidence.correlation_status = CorrelationStatus.REJECTED
        await session.flush()
        await session.refresh(evidence)

        logger.info(f"EvidenceRejected: Evidence [{evidence_id}] rejected.")
        return EvidenceResponse.model_validate(evidence)

    # ==========================================
    # PHASE 5: PROACTIVE RISK ASSESSMENT
    # ==========================================

    @staticmethod
    async def get_risk_assessment(
        session: AsyncSession, obligation_id: str
    ) -> Optional[RiskAssessmentResponse]:
        from app.services.risk_engine import RiskEngine
        return await RiskEngine.assess_obligation(session, obligation_id)

    @staticmethod
    async def get_bulk_risks(
        session: AsyncSession,
        risk_level: Optional[RiskLevel] = None,
        owner: Optional[str] = None,
        obligation_type: Optional[ObligationType] = None,
        status: Optional[ObligationStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> BulkRiskResponse:
        from app.services.risk_engine import RiskEngine

        query = select(Obligation).where(
            Obligation.status.notin_([ObligationStatus.COMPLETED, ObligationStatus.CANCELLED])
        )

        if owner:
            query = query.where(Obligation.owner.ilike(f"%{owner}%"))
        if obligation_type:
            query = query.where(Obligation.obligation_type == obligation_type)
        if status:
            query = query.where(Obligation.status == status)

        query = query.order_by(desc(Obligation.created_at))
        result = await session.execute(query)
        obligations = list(result.scalars().all())

        assessments: List[RiskAssessmentResponse] = []
        for ob in obligations:
            assessment = await RiskEngine.assess_obligation(session, ob.id)
            if assessment:
                if risk_level is None or assessment.risk_level == risk_level:
                    assessments.append(assessment)

        # Sort by priority score descending
        assessments.sort(key=lambda a: (a.priority_score, a.risk_score), reverse=True)

        critical_count = sum(1 for a in assessments if a.risk_level == RiskLevel.CRITICAL)
        high_count = sum(1 for a in assessments if a.risk_level == RiskLevel.HIGH)
        medium_count = sum(1 for a in assessments if a.risk_level == RiskLevel.MEDIUM)
        low_count = sum(1 for a in assessments if a.risk_level == RiskLevel.LOW)

        paginated = assessments[offset: offset + limit]

        return BulkRiskResponse(
            total_at_risk=len(assessments),
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            items=paginated,
        )
