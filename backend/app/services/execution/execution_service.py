"""
Execution Service for Phase 16.
Manages the complete controlled execution lifecycle: idempotency, provider dispatch, retry policy, receipts, and auditability.
"""

import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.core.logging import logger
from app.core.status_machine import (
    ExecutionStatus,
    ExecutionType,
    ExecutionOutcome,
    ExecutionFailureCode,
    DecisionPlanStatus,
    validate_execution_transition,
    AuditAction,
    AuditSource,
)
from app.core.intervention_status import InterventionStatus
from app.models.decision import DecisionPlan
from app.models.obligation import Obligation, Intervention
from app.models.execution import ExecutionRecord
from app.models.auth import User
from app.schemas.execution import (
    ExecutionAuthorizeRequest,
    ExecutionExecuteRequest,
    ExecutionRecordResponse,
    ExecutionReceiptResponse,
    ExecutionQueueItem,
    ExecutionQueueResponse,
)
from app.services.execution.base_execution_provider import (
    BaseExecutionProvider,
    ExecutionActionPayload,
    ExecutionProviderReceipt,
)
from app.services.execution.mock_execution_provider import MockExecutionProvider
from app.services.execution.slack_execution_provider import SlackExecutionProvider
from app.services.execution.execution_authorization_service import ExecutionAuthorizationService
from app.services.audit_service import AuditService
from app.core.concurrency import concurrency_guard
from app.services.audit_service import AuditService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExecutionService:
    """
    Controlled execution service enforcing idempotency, provider abstraction,
    execution receipts, and delivery guarantees.
    """

    _providers: Dict[str, BaseExecutionProvider] = {
        "mock": MockExecutionProvider(),
        "slack": SlackExecutionProvider(),
    }

    @classmethod
    def get_provider(cls, provider_name: str) -> BaseExecutionProvider:
        name = provider_name.lower()
        if name not in cls._providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported execution provider: '{provider_name}'. Supported providers: {list(cls._providers.keys())}",
            )
        return cls._providers[name]

    @classmethod
    def compute_idempotency_key(
        cls,
        workspace_id: str,
        decision_plan_id: str,
        intervention_id: Optional[str],
        plan_version: int,
        recipient: str,
        message: str,
    ) -> str:
        raw = f"{workspace_id}:{decision_plan_id}:{intervention_id or 'none'}:{plan_version}:{recipient.strip().lower()}:{message.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def compute_payload_hash(cls, recipient: str, message: str) -> str:
        raw = f"{recipient.strip().lower()}:{message.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    async def authorize(
        cls,
        session: AsyncSession,
        plan_id: str,
        user: Optional[User] = None,
        workspace_id: str = "ws-default",
        request: Optional[ExecutionAuthorizeRequest] = None,
    ) -> ExecutionRecordResponse:
        async with concurrency_guard.acquire_lock("decision_execution", plan_id):
            # Fast Idempotency: Return existing execution for this plan if one already exists
            existing_plan_stmt = select(ExecutionRecord).where(
                and_(
                    ExecutionRecord.workspace_id == workspace_id,
                    ExecutionRecord.decision_plan_id == plan_id,
                )
            )
            existing_plan_res = await session.execute(existing_plan_stmt)
            existing_plan_rec = existing_plan_res.scalars().first()
            if existing_plan_rec:
                logger.info(f"Execution record already exists for plan [{plan_id}]. Returning record [{existing_plan_rec.id}].")
                return ExecutionRecordResponse.model_validate(existing_plan_rec)

            provider_name = (request.provider if request and request.provider else "mock").lower()
            plan, ob, intervention = await ExecutionAuthorizationService.validate_authorization(
                session=session,
                plan_id=plan_id,
                workspace_id=workspace_id,
                requested_provider=provider_name,
            )

            rec_actions = plan.recommended_actions or {}
            recipient = (
                rec_actions.get("target_owner")
                or (intervention.target_owner if intervention else None)
                or ob.owner
                or "Unassigned"
            )
            message = (
                rec_actions.get("action_summary")
                or (intervention.approved_message or intervention.message_draft if intervention else None)
                or f"Follow up on commitment: {ob.action}"
            )

            idempotency_key = cls.compute_idempotency_key(
                workspace_id=workspace_id,
                decision_plan_id=plan.id,
                intervention_id=intervention.id if intervention else None,
                plan_version=plan.plan_version,
                recipient=recipient,
                message=message,
            )
            payload_hash = cls.compute_payload_hash(recipient, message)

            # Check existing execution by idempotency key
            existing_stmt = select(ExecutionRecord).where(
                and_(
                    ExecutionRecord.workspace_id == workspace_id,
                    ExecutionRecord.idempotency_key == idempotency_key,
                )
            )
            existing_res = await session.execute(existing_stmt)
            existing_rec = existing_res.scalar_one_or_none()
            if existing_rec:
                logger.info(f"Execution record already exists for idempotency key [{idempotency_key}]. Returning record [{existing_rec.id}].")
                return ExecutionRecordResponse.model_validate(existing_rec)

            now = utc_now()
            actor_name = user.display_name if user else "Human Operator"

            # Create new execution record in AUTHORIZED status
            execution_rec = ExecutionRecord(
                workspace_id=workspace_id,
                decision_plan_id=plan.id,
                intervention_id=intervention.id if intervention else None,
                obligation_id=ob.id,
                execution_type=ExecutionType.INTERVENTION_MESSAGE,
                provider=provider_name,
                provider_version="1.0.0",
                status=ExecutionStatus.AUTHORIZED,
                authorized_by=actor_name,
                authorized_at=now,
                idempotency_key=idempotency_key,
                request_payload_hash=payload_hash,
                safe_request_metadata={
                    "recipient": recipient,
                    "message_snippet": message[:100],
                    "strategy_name": rec_actions.get("strategy_name", "Primary Strategy"),
                    "plan_version": plan.plan_version,
                    "mock_behavior": rec_actions.get("mock_behavior"),
                    "notes": request.notes if request else None,
                },
                retry_count=0,
                max_retries=3,
            )
            session.add(execution_rec)
            await session.flush()
            await session.refresh(execution_rec)

            # Audit
            await AuditService.record(
                session=session,
                workspace_id=workspace_id,
                action=AuditAction.INTERVENTION_APPROVED,
                actor_user_id=user.id if user else None,
                actor_role=getattr(user, "role", "OPERATOR") if user else "OPERATOR",
                entity_type="execution",
                entity_id=execution_rec.id,
                source=AuditSource.API,
                after_state={
                    "status": execution_rec.status.value,
                    "provider": execution_rec.provider,
                    "decision_plan_id": plan.id,
                    "recipient": recipient,
                },
                reason=f"Authorized execution of Decision Plan v{plan.plan_version}",
            )
            await session.commit()

            return ExecutionRecordResponse.model_validate(execution_rec)

    @classmethod
    async def execute(
        cls,
        session: AsyncSession,
        plan_id: str,
        user: Optional[User] = None,
        workspace_id: str = "ws-default",
        request: Optional[ExecutionExecuteRequest] = None,
    ) -> ExecutionRecordResponse:
        # 1. Authorize / retrieve execution record
        auth_res = await cls.authorize(
            session=session,
            plan_id=plan_id,
            user=user,
            workspace_id=workspace_id,
            request=ExecutionAuthorizeRequest(
                provider=request.provider if request else "mock",
                notes=request.notes if request else None,
            ),
        )

        exec_rec = await session.get(ExecutionRecord, auth_res.id)
        if not exec_rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution record not found.")

        # 2. Strict Idempotency Check: if already executed or in flight, return existing record without duplicate provider call
        if exec_rec.status in [
            ExecutionStatus.DELIVERED,
            ExecutionStatus.RESPONSE_PENDING,
            ExecutionStatus.OUTCOME_DETECTED,
            ExecutionStatus.RESOLVED,
        ]:
            logger.info(f"Execution [{exec_rec.id}] is already in status '{exec_rec.status.value}'. Returning existing record idempotently.")
            return ExecutionRecordResponse.model_validate(exec_rec)

        # 3. Transition to EXECUTING
        validate_execution_transition(exec_rec.status, ExecutionStatus.EXECUTING)
        exec_rec.status = ExecutionStatus.EXECUTING
        await session.flush()

        # 4. Prepare Action Payload
        metadata = dict(exec_rec.safe_request_metadata or {})
        recipient = metadata.get("recipient", "Recipient")
        message = metadata.get("message_snippet", "Notification regarding obligation.")

        action_payload = ExecutionActionPayload(
            recipient=recipient,
            message=message,
            channel=metadata.get("channel"),
            action_type="INTERVENTION_MESSAGE",
            metadata=metadata,
        )

        # 5. Dispatch to Provider Adapter
        provider = cls.get_provider(exec_rec.provider)
        receipt: ExecutionProviderReceipt = await provider.execute(action_payload)

        now = utc_now()
        exec_rec.executed_at = now
        exec_rec.provider_execution_ref = receipt.provider_ref

        if receipt.success:
            validate_execution_transition(exec_rec.status, ExecutionStatus.DELIVERED)
            exec_rec.status = ExecutionStatus.DELIVERED
            exec_rec.delivery_status = receipt.delivery_status
            exec_rec.safe_request_metadata = {
                **metadata,
                **receipt.raw_metadata,
            }

            # Advance to RESPONSE_PENDING if waiting for recipient reply
            validate_execution_transition(exec_rec.status, ExecutionStatus.RESPONSE_PENDING)
            exec_rec.status = ExecutionStatus.RESPONSE_PENDING

            # Update associated intervention to EXECUTED
            if exec_rec.intervention_id:
                inv = await session.get(Intervention, exec_rec.intervention_id)
                if inv:
                    inv.status = InterventionStatus.EXECUTED
                    inv.executed_at = now
                    audit_trail = list(inv.audit_trail or [])
                    audit_trail.append({
                        "event": "EXECUTION_DELIVERED",
                        "provider": exec_rec.provider,
                        "provider_ref": receipt.provider_ref,
                        "timestamp": now.isoformat(),
                    })
                    inv.audit_trail = audit_trail

        else:
            # Failure handling
            exec_rec.delivery_status = receipt.delivery_status
            exec_rec.failure_code = receipt.failure_code
            exec_rec.failure_reason = receipt.failure_reason

            if receipt.is_transient_failure and exec_rec.retry_count < exec_rec.max_retries:
                validate_execution_transition(exec_rec.status, ExecutionStatus.DELIVERY_FAILED)
                exec_rec.status = ExecutionStatus.DELIVERY_FAILED
                validate_execution_transition(exec_rec.status, ExecutionStatus.RETRY_SCHEDULED)
                exec_rec.status = ExecutionStatus.RETRY_SCHEDULED
                exec_rec.retry_count += 1
                exec_rec.next_retry_at = now + timedelta(seconds=15 * exec_rec.retry_count)
            else:
                validate_execution_transition(exec_rec.status, ExecutionStatus.FAILED)
                exec_rec.status = ExecutionStatus.FAILED

        await session.flush()
        await session.refresh(exec_rec)

        # Audit event
        await AuditService.record(
            session=session,
            workspace_id=workspace_id,
            action=AuditAction.INTERVENTION_EXECUTED if receipt.success else AuditAction.INTERVENTION_CANCELLED,
            actor_user_id=user.id if user else None,
            actor_role=getattr(user, "role", "SYSTEM") if user else "SYSTEM",
            entity_type="execution",
            entity_id=exec_rec.id,
            source=AuditSource.SYSTEM_WORKER,
            after_state={
                "status": exec_rec.status.value,
                "provider": exec_rec.provider,
                "provider_execution_ref": exec_rec.provider_execution_ref,
                "delivery_status": exec_rec.delivery_status,
            },
            reason=f"Executed Decision Plan action through {exec_rec.provider} provider (Ref: {exec_rec.provider_execution_ref})",
        )
        await session.commit()

        return ExecutionRecordResponse.model_validate(exec_rec)

    @classmethod
    async def get_by_id(
        cls,
        session: AsyncSession,
        execution_id: str,
        workspace_id: str = "ws-default",
    ) -> ExecutionRecordResponse:
        rec = await session.get(ExecutionRecord, execution_id)
        if not rec or rec.workspace_id != workspace_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution record not found.")
        return ExecutionRecordResponse.model_validate(rec)

    @classmethod
    async def get_receipt(
        cls,
        session: AsyncSession,
        execution_id: str,
        workspace_id: str = "ws-default",
    ) -> ExecutionReceiptResponse:
        rec = await session.get(ExecutionRecord, execution_id)
        if not rec or rec.workspace_id != workspace_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution record not found.")

        ob = await session.get(Obligation, rec.obligation_id)
        plan = await session.get(DecisionPlan, rec.decision_plan_id)

        safe_metadata = dict(rec.safe_request_metadata or {})
        # Redact any accidental credential keys
        for sensitive_key in ["token", "secret", "password", "key", "authorization"]:
            if sensitive_key in safe_metadata:
                del safe_metadata[sensitive_key]

        return ExecutionReceiptResponse(
            execution_id=rec.id,
            workspace_id=rec.workspace_id,
            decision_plan_id=rec.decision_plan_id,
            plan_version=plan.plan_version if plan else 1,
            intervention_id=rec.intervention_id,
            obligation_id=rec.obligation_id,
            obligation_action=ob.action if ob else "Unknown obligation",
            target_owner=ob.owner if ob else None,
            provider=rec.provider,
            provider_execution_ref=rec.provider_execution_ref,
            delivery_status=rec.delivery_status or "UNKNOWN",
            status=rec.status,
            authorized_by=rec.authorized_by,
            authorized_at=rec.authorized_at,
            executed_at=rec.executed_at,
            retry_count=rec.retry_count,
            failure_code=rec.failure_code.value if rec.failure_code else None,
            failure_reason=rec.failure_reason,
            safe_metadata=safe_metadata,
            receipt_generated_at=utc_now(),
        )

    @classmethod
    async def cancel(
        cls,
        session: AsyncSession,
        execution_id: str,
        user: Optional[User] = None,
        reason: str = "Cancelled by operator",
        workspace_id: str = "ws-default",
    ) -> ExecutionRecordResponse:
        rec = await session.get(ExecutionRecord, execution_id)
        if not rec or rec.workspace_id != workspace_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution record not found.")

        validate_execution_transition(rec.status, ExecutionStatus.CANCELLED)
        rec.status = ExecutionStatus.CANCELLED
        rec.failure_reason = reason
        await session.flush()
        await session.refresh(rec)

        await AuditService.record(
            session=session,
            workspace_id=workspace_id,
            action=AuditAction.INTERVENTION_CANCELLED,
            actor_user_id=user.id if user else None,
            actor_role=getattr(user, "role", "OPERATOR") if user else "OPERATOR",
            entity_type="execution",
            entity_id=rec.id,
            source=AuditSource.API,
            after_state={"status": rec.status.value, "reason": reason},
            reason=f"Cancelled execution: {reason}",
        )

        return ExecutionRecordResponse.model_validate(rec)

    @classmethod
    async def retry(
        cls,
        session: AsyncSession,
        execution_id: str,
        user: Optional[User] = None,
        workspace_id: str = "ws-default",
    ) -> ExecutionRecordResponse:
        rec = await session.get(ExecutionRecord, execution_id)
        if not rec or rec.workspace_id != workspace_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution record not found.")

        if rec.retry_count >= rec.max_retries:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Execution has reached maximum retry limit ({rec.max_retries}).",
            )

        validate_execution_transition(rec.status, ExecutionStatus.EXECUTING)
        rec.status = ExecutionStatus.EXECUTING
        rec.retry_count += 1
        await session.flush()

        metadata = dict(rec.safe_request_metadata or {})
        recipient = metadata.get("recipient", "Recipient")
        message = metadata.get("message_snippet", "Follow up notification.")

        action_payload = ExecutionActionPayload(
            recipient=recipient,
            message=message,
            channel=metadata.get("channel"),
            metadata=metadata,
        )

        provider = cls.get_provider(rec.provider)
        receipt = await provider.execute(action_payload)

        now = utc_now()
        rec.executed_at = now
        rec.provider_execution_ref = receipt.provider_ref

        if receipt.success:
            validate_execution_transition(rec.status, ExecutionStatus.DELIVERED)
            rec.status = ExecutionStatus.DELIVERED
            validate_execution_transition(rec.status, ExecutionStatus.RESPONSE_PENDING)
            rec.status = ExecutionStatus.RESPONSE_PENDING
            rec.delivery_status = receipt.delivery_status
        else:
            rec.delivery_status = receipt.delivery_status
            rec.failure_code = receipt.failure_code
            rec.failure_reason = receipt.failure_reason
            validate_execution_transition(rec.status, ExecutionStatus.FAILED)
            rec.status = ExecutionStatus.FAILED

        await session.flush()
        await session.refresh(rec)
        return ExecutionRecordResponse.model_validate(rec)

    @classmethod
    async def get_history_for_plan(
        cls,
        session: AsyncSession,
        plan_id: str,
        workspace_id: str = "ws-default",
    ) -> List[ExecutionRecordResponse]:
        stmt = (
            select(ExecutionRecord)
            .where(
                and_(
                    ExecutionRecord.workspace_id == workspace_id,
                    ExecutionRecord.decision_plan_id == plan_id,
                )
            )
            .order_by(desc(ExecutionRecord.created_at))
        )
        res = await session.execute(stmt)
        return [ExecutionRecordResponse.model_validate(r) for r in res.scalars().all()]

    @classmethod
    async def get_queue(
        cls,
        session: AsyncSession,
        workspace_id: str = "ws-default",
    ) -> ExecutionQueueResponse:
        stmt = (
            select(ExecutionRecord, Obligation, DecisionPlan)
            .join(Obligation, ExecutionRecord.obligation_id == Obligation.id)
            .join(DecisionPlan, ExecutionRecord.decision_plan_id == DecisionPlan.id)
            .where(ExecutionRecord.workspace_id == workspace_id)
            .order_by(desc(ExecutionRecord.created_at))
        )
        res = await session.execute(stmt)
        rows = res.all()

        items: List[ExecutionQueueItem] = []
        pending_auth = 0
        executing = 0
        delivered = 0
        awaiting_resp = 0
        resolved = 0
        failed = 0

        for exec_rec, ob, plan in rows:
            if exec_rec.status == ExecutionStatus.PENDING_AUTHORIZATION:
                pending_auth += 1
            elif exec_rec.status in [ExecutionStatus.AUTHORIZED, ExecutionStatus.QUEUED, ExecutionStatus.EXECUTING]:
                executing += 1
            elif exec_rec.status == ExecutionStatus.DELIVERED:
                delivered += 1
            elif exec_rec.status in [ExecutionStatus.RESPONSE_PENDING, ExecutionStatus.OUTCOME_DETECTED]:
                awaiting_resp += 1
            elif exec_rec.status == ExecutionStatus.RESOLVED:
                resolved += 1
            elif exec_rec.status in [ExecutionStatus.FAILED, ExecutionStatus.DELIVERY_FAILED]:
                failed += 1

            items.append(
                ExecutionQueueItem(
                    execution=ExecutionRecordResponse.model_validate(exec_rec),
                    obligation_action=ob.action,
                    obligation_owner=ob.owner,
                    plan_urgency=plan.overall_urgency,
                    plan_risk=plan.overall_risk,
                )
            )

        return ExecutionQueueResponse(
            pending_authorization_count=pending_auth,
            executing_count=executing,
            delivered_count=delivered,
            awaiting_response_count=awaiting_resp,
            resolved_count=resolved,
            failed_count=failed,
            items=items,
        )
