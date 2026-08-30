from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, or_, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    validate_status_transition,
)
from app.models.obligation import Obligation, ObligationEdge
from app.schemas.obligation import (
    ObligationCreate,
    ObligationUpdate,
    ObligationStatusUpdate,
    ObligationResponse,
    ObligationListResponse,
    DashboardSummaryResponse,
    ObligationEdgeCreate,
    ObligationEdgeResponse,
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
        limit: int = 50,
        offset: int = 0,
    ) -> ObligationListResponse:
        query = select(Obligation)

        if obligation_type:
            query = query.where(Obligation.obligation_type == obligation_type)

        if status:
            query = query.where(Obligation.status == status)

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
        query = select(Obligation).where(Obligation.id == obligation_id)
        result = await session.execute(query)
        obligation = result.scalar_one_or_none()
        if not obligation:
            return None

        # Validate controlled status transition
        validate_status_transition(obligation.status, status_data.status)
        obligation.status = status_data.status

        # If evidence was supplied (e.g. during completion), attach it
        if status_data.evidence:
            current_evidence = list(obligation.evidence or [])
            evidence_entry = {
                **status_data.evidence,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "status_transition": status_data.status.value,
            }
            current_evidence.append(evidence_entry)
            obligation.evidence = current_evidence

        await session.flush()
        await session.refresh(obligation)
        return to_response_dto(obligation)

    @staticmethod
    async def delete(session: AsyncSession, obligation_id: str) -> bool:
        query = select(Obligation).where(Obligation.id == obligation_id)
        result = await session.execute(query)
        obligation = result.scalar_one_or_none()
        if not obligation:
            return False
        await session.delete(obligation)
        await session.flush()
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

        return DashboardSummaryResponse(
            you_owe_count=len(you_owe),
            others_owe_count=len(others_owe),
            at_risk_count=len(at_risk),
            completed_count=len(completed),
            you_owe_obligations=you_owe[:10],
            others_owe_obligations=others_owe[:10],
            at_risk_obligations=at_risk[:10],
        )

    @staticmethod
    async def create_edge(session: AsyncSession, data: ObligationEdgeCreate) -> ObligationEdgeResponse:
        edge = ObligationEdge(
            from_obligation_id=data.from_obligation_id,
            to_obligation_id=data.to_obligation_id,
            edge_type=data.edge_type,
        )
        session.add(edge)
        await session.flush()
        await session.refresh(edge)
        return ObligationEdgeResponse.model_validate(edge)
