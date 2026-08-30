import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.core.logging import logger
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EventSemanticRole,
    CorrelationStatus,
    ReconciliationStatus,
    ReconciliationResolutionAction,
    ActionType,
    validate_status_transition,
)
from app.models.obligation import (
    Obligation,
    Evidence,
    IngestedEventRecord,
    ReconciliationRecord,
)
from app.schemas.obligation import (
    ReconciliationRecordResponse,
    ReconciliationListResponse,
    ReconciliationResolutionRequest,
    ReconciliationDismissRequest,
    EvidenceProvenanceDetail,
)
from app.services.graph_service import GraphService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_tz(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ReconciliationService:
    """
    Cross-Provider Reconciliation & Contradiction Intelligence Engine.
    Evaluates multi-source evidence clusters (Slack, Gmail, Calendar, Direct/Mock),
    identifies reinforcing consistency or semantic/temporal contradictions,
    and manages the auditable human review workflow.
    """

    @classmethod
    async def reconcile_obligation(
        cls, session: AsyncSession, obligation_id: str, workspace_id: Optional[str] = None
    ) -> Optional[ReconciliationRecord]:
        """
        Main reconciliation entry point. Evaluates all evidence records for the obligation,
        detects contradictions or reinforcing consistency, and updates/creates the active ReconciliationRecord.
        """
        obligation = await session.get(Obligation, obligation_id)
        if not obligation:
            return None
        if workspace_id and obligation.workspace_id != workspace_id:
            return None

        # Fetch all evidence records for this obligation ordered chronologically
        ev_stmt = (
            select(Evidence)
            .where(Evidence.obligation_id == obligation_id)
            .order_by(Evidence.observed_at.asc())
        )
        ev_res = await session.execute(ev_stmt)
        evidence_list = list(ev_res.scalars().all())

        if not evidence_list:
            return None

        # Fetch any active (unresolved) reconciliation record
        rec_stmt = (
            select(ReconciliationRecord)
            .where(
                and_(
                    ReconciliationRecord.obligation_id == obligation_id,
                    ReconciliationRecord.status.in_([
                        ReconciliationStatus.AMBIGUOUS,
                        ReconciliationStatus.CONSISTENT,
                        ReconciliationStatus.CONFLICTING,
                    ])
                )
            )
            .order_by(desc(ReconciliationRecord.created_at))
        )
        rec_res = await session.execute(rec_stmt)
        existing_rec = rec_res.scalars().first()

        # Perform semantic & temporal cross-provider analysis
        analysis = await cls._analyze_evidence_cluster(session, obligation, evidence_list)

        if existing_rec:
            # Update active record
            existing_rec.status = analysis["status"]
            existing_rec.confidence = analysis["confidence"]
            existing_rec.consistency_score = analysis["consistency_score"]
            existing_rec.contradiction_score = analysis["contradiction_score"]
            existing_rec.supporting_evidence_ids = analysis["supporting_evidence_ids"]
            existing_rec.conflicting_evidence_ids = analysis["conflicting_evidence_ids"]
            existing_rec.supporting_event_ids = analysis["supporting_event_ids"]
            existing_rec.conflicting_event_ids = analysis["conflicting_event_ids"]
            existing_rec.explanation = analysis["explanation"]
            existing_rec.recommended_action = analysis["recommended_action"]
            existing_rec.updated_at = utc_now()
            await session.flush()
            await session.refresh(existing_rec)
            return existing_rec
        else:
            new_rec = ReconciliationRecord(
                workspace_id=obligation.workspace_id,
                obligation_id=obligation_id,
                status=analysis["status"],
                confidence=analysis["confidence"],
                consistency_score=analysis["consistency_score"],
                contradiction_score=analysis["contradiction_score"],
                supporting_evidence_ids=analysis["supporting_evidence_ids"],
                conflicting_evidence_ids=analysis["conflicting_evidence_ids"],
                supporting_event_ids=analysis["supporting_event_ids"],
                conflicting_event_ids=analysis["conflicting_event_ids"],
                explanation=analysis["explanation"],
                recommended_action=analysis["recommended_action"],
            )
            session.add(new_rec)
            await session.flush()
            await session.refresh(new_rec)
            return new_rec

    @classmethod
    async def _analyze_evidence_cluster(
        cls, session: AsyncSession, obligation: Obligation, evidence_list: List[Evidence]
    ) -> Dict[str, Any]:
        """
        Core reasoning engine. Identifies:
        - Completion candidates vs Progress updates vs Negative/Blocker signals
        - Multi-provider reinforcement vs Contradictions
        - Temporal sequence ordering
        - Dependency / conditional state conflicts
        """
        supporting_ev_ids: List[str] = []
        conflicting_ev_ids: List[str] = []
        supporting_evt_ids: List[str] = []
        conflicting_evt_ids: List[str] = []
        explanations: List[str] = []

        completion_evs: List[Evidence] = []
        progress_evs: List[Evidence] = []
        negative_evs: List[Evidence] = []
        contextual_evs: List[Evidence] = []

        distinct_providers = set()

        for ev in evidence_list:
            p_name = ev.source_type or "unknown"
            if isinstance(ev.extra_metadata, dict) and ev.extra_metadata.get("source_provider"):
                p_name = ev.extra_metadata["source_provider"]
            distinct_providers.add(p_name)

            role = ev.semantic_role
            if role == EventSemanticRole.COMPLETION_SIGNAL:
                completion_evs.append(ev)
            elif role == EventSemanticRole.PROGRESS_UPDATE:
                progress_evs.append(ev)
            elif role == EventSemanticRole.NON_COMPLETION_SIGNAL:
                negative_evs.append(ev)
            else:
                contextual_evs.append(ev)

        # Baseline scores
        consistency_score = 0.50
        contradiction_score = 0.0
        confidence = 0.70

        # Pattern A & C: COMPLETION vs NEGATIVE_BLOCKER or LATER NEGATIVE SIGNAL
        if completion_evs and negative_evs:
            # Sort each
            latest_completion = max(completion_evs, key=lambda e: normalize_tz(e.observed_at) or utc_now())
            latest_negative = max(negative_evs, key=lambda e: normalize_tz(e.observed_at) or utc_now())

            supporting_ev_ids.extend([e.id for e in completion_evs])
            conflicting_ev_ids.extend([e.id for e in negative_evs])

            comp_time = normalize_tz(latest_completion.observed_at) or utc_now()
            neg_time = normalize_tz(latest_negative.observed_at) or utc_now()

            comp_provider = latest_completion.source_type.capitalize()
            neg_provider = latest_negative.source_type.capitalize()

            if neg_time > comp_time:
                # Later negative signal after completion!
                contradiction_score = 0.90
                consistency_score = 0.15
                confidence = 0.92
                explanations.append(
                    f"{comp_provider} indicates completion ('{latest_completion.content[:60]}...')."
                )
                explanations.append(
                    f"A later {neg_provider} event indicates the deliverable was not received or encountered an issue ('{latest_negative.content[:60]}...')."
                )
                explanations.append(
                    f"Temporal contradiction detected: Negative signal occurred after the reported completion."
                )
                status_val = ReconciliationStatus.CONFLICTING
                recommended = ActionType.REVIEW_CONFLICTING_EVIDENCE.value
            else:
                # Concurrent or earlier negative blocker
                contradiction_score = 0.75
                consistency_score = 0.25
                confidence = 0.85
                explanations.append(
                    f"Conflicting signals: {comp_provider} reported completion while {neg_provider} reported a blocker or failure."
                )
                status_val = ReconciliationStatus.CONFLICTING
                recommended = ActionType.REVIEW_CONFLICTING_EVIDENCE.value

            return {
                "status": status_val,
                "confidence": confidence,
                "consistency_score": consistency_score,
                "contradiction_score": contradiction_score,
                "supporting_evidence_ids": supporting_ev_ids,
                "conflicting_evidence_ids": conflicting_ev_ids,
                "supporting_event_ids": supporting_evt_ids,
                "conflicting_event_ids": conflicting_evt_ids,
                "explanation": explanations,
                "recommended_action": recommended,
            }

        # Pattern B & E: COMPLETION vs PROGRESS (Temporal Reversal check)
        if completion_evs and progress_evs:
            latest_completion = max(completion_evs, key=lambda e: normalize_tz(e.observed_at) or utc_now())
            latest_progress = max(progress_evs, key=lambda e: normalize_tz(e.observed_at) or utc_now())

            comp_time = normalize_tz(latest_completion.observed_at) or utc_now()
            prog_time = normalize_tz(latest_progress.observed_at) or utc_now()

            comp_provider = latest_completion.source_type.capitalize()
            prog_provider = latest_progress.source_type.capitalize()

            if prog_time > comp_time + timedelta(minutes=5):
                # Later progress after completion -> Contradiction / Reopening signal
                supporting_ev_ids.extend([e.id for e in completion_evs])
                conflicting_ev_ids.extend([e.id for e in progress_evs])
                contradiction_score = 0.80
                consistency_score = 0.30
                confidence = 0.88
                explanations.append(
                    f"{comp_provider} reported completion, but a later {prog_provider} message indicates work is still ongoing."
                )
                explanations.append(
                    "Temporal inconsistency: Activity indicating in-progress work was observed after the completion signal."
                )
                return {
                    "status": ReconciliationStatus.CONFLICTING,
                    "confidence": confidence,
                    "consistency_score": consistency_score,
                    "contradiction_score": contradiction_score,
                    "supporting_evidence_ids": supporting_ev_ids,
                    "conflicting_evidence_ids": conflicting_ev_ids,
                    "supporting_event_ids": supporting_evt_ids,
                    "conflicting_event_ids": conflicting_evt_ids,
                    "explanation": explanations,
                    "recommended_action": ActionType.REVIEW_STALE_SIGNAL.value,
                }
            else:
                # Earlier progress followed by later completion -> Perfectly consistent normal workflow!
                supporting_ev_ids.extend([e.id for e in evidence_list])
                consistency_score = 0.88
                contradiction_score = 0.05
                confidence = 0.90
                explanations.append(
                    f"Progress updates in {prog_provider} were followed by a high-confidence completion deliverable in {comp_provider}."
                )
                explanations.append(
                    "Temporal sequence is coherent (Progress -> Deliverable Sent)."
                )
                return {
                    "status": ReconciliationStatus.CONSISTENT,
                    "confidence": confidence,
                    "consistency_score": consistency_score,
                    "contradiction_score": contradiction_score,
                    "supporting_evidence_ids": supporting_ev_ids,
                    "conflicting_evidence_ids": [],
                    "supporting_event_ids": supporting_evt_ids,
                    "conflicting_event_ids": [],
                    "explanation": explanations,
                    "recommended_action": ActionType.CONFIRM_COMPLETION_EVIDENCE.value,
                }

        # Pattern D: CONDITIONAL / DEPENDENCY PREREQUISITE CONFLICT
        if completion_evs and obligation.status == ObligationStatus.BLOCKED:
            supporting_ev_ids.extend([e.id for e in completion_evs])
            contradiction_score = 0.65
            consistency_score = 0.35
            confidence = 0.80
            explanations.append(
                "A completion signal was received, but this obligation currently has active prerequisite dependencies or is marked BLOCKED."
            )
            explanations.append(
                "Verify whether prerequisite commitments were actually completed out-of-band before confirming."
            )
            return {
                "status": ReconciliationStatus.AMBIGUOUS,
                "confidence": confidence,
                "consistency_score": consistency_score,
                "contradiction_score": contradiction_score,
                "supporting_evidence_ids": supporting_ev_ids,
                "conflicting_evidence_ids": [],
                "supporting_event_ids": supporting_evt_ids,
                "conflicting_event_ids": [],
                "explanation": explanations,
                "recommended_action": ActionType.RESOLVE_DEPENDENCY.value,
            }

        # Pattern F: MULTIPLE CONSISTENT COMPLETION SIGNALS ACROSS PROVIDERS
        if len(completion_evs) >= 1:
            supporting_ev_ids.extend([e.id for e in completion_evs])
            comp_providers = list({e.source_type.capitalize() for e in completion_evs})

            if len(comp_providers) > 1:
                # Multi-provider reinforcement!
                consistency_score = 0.95
                contradiction_score = 0.0
                confidence = 0.96
                explanations.append(
                    f"Multiple independent providers ({', '.join(comp_providers)}) corroborate that the deliverable was completed."
                )
                explanations.append(
                    "High-confidence multi-source agreement detected. Ready for authoritative human confirmation."
                )
                return {
                    "status": ReconciliationStatus.CONSISTENT,
                    "confidence": confidence,
                    "consistency_score": consistency_score,
                    "contradiction_score": contradiction_score,
                    "supporting_evidence_ids": supporting_ev_ids,
                    "conflicting_evidence_ids": [],
                    "supporting_event_ids": supporting_evt_ids,
                    "conflicting_event_ids": [],
                    "explanation": explanations,
                    "recommended_action": ActionType.CONFIRM_COMPLETION_EVIDENCE.value,
                }
            else:
                # Single provider completion signal
                consistency_score = 0.80
                contradiction_score = 0.05
                confidence = 0.85
                explanations.append(
                    f"Completion deliverable detected via {comp_providers[0]}."
                )
                return {
                    "status": ReconciliationStatus.CONSISTENT,
                    "confidence": confidence,
                    "consistency_score": consistency_score,
                    "contradiction_score": contradiction_score,
                    "supporting_evidence_ids": supporting_ev_ids,
                    "conflicting_evidence_ids": [],
                    "supporting_event_ids": supporting_evt_ids,
                    "conflicting_event_ids": [],
                    "explanation": explanations,
                    "recommended_action": ActionType.REVIEW_EVIDENCE.value,
                }

        # Negative signals without completion
        if negative_evs:
            conflicting_ev_ids.extend([e.id for e in negative_evs])
            contradiction_score = 0.50
            consistency_score = 0.40
            confidence = 0.80
            explanations.append(
                "Activity indicates an unresolved blocker, rejection, or delivery failure."
            )
            return {
                "status": ReconciliationStatus.CONFLICTING,
                "confidence": confidence,
                "consistency_score": consistency_score,
                "contradiction_score": contradiction_score,
                "supporting_evidence_ids": [],
                "conflicting_evidence_ids": conflicting_ev_ids,
                "supporting_event_ids": [],
                "conflicting_event_ids": conflicting_evt_ids,
                "explanation": explanations,
                "recommended_action": ActionType.KEEP_ACTIVE.value,
            }

        # Progress / contextual signals only
        supporting_ev_ids.extend([e.id for e in progress_evs + contextual_evs])
        explanations.append("Observed activity reflects normal in-progress execution across connected providers.")
        return {
            "status": ReconciliationStatus.CONSISTENT,
            "confidence": 0.70,
            "consistency_score": 0.70,
            "contradiction_score": 0.0,
            "supporting_evidence_ids": supporting_ev_ids,
            "conflicting_evidence_ids": [],
            "supporting_event_ids": supporting_evt_ids,
            "conflicting_event_ids": [],
            "explanation": explanations,
            "recommended_action": ActionType.START_WORK.value,
        }

    # =========================================================================
    # HUMAN REVIEW & DECISION WORKFLOW
    # =========================================================================

    @classmethod
    async def resolve_reconciliation(
        cls,
        session: AsyncSession,
        reconciliation_id: str,
        request: ReconciliationResolutionRequest,
        workspace_id: Optional[str] = None,
        actor_user_id: Optional[str] = None,
    ) -> ReconciliationRecordResponse:
        """
        Executes human operator decision on a reconciliation record.
        Maintains authoritative safety boundaries, validates state machine transitions,
        and triggers Phase 3 graph propagation when an obligation completes.
        """
        rec = await session.get(ReconciliationRecord, reconciliation_id)
        if not rec or (workspace_id and rec.workspace_id != workspace_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reconciliation record '{reconciliation_id}' not found in active workspace.",
            )

        obligation = await session.get(Obligation, rec.obligation_id)
        if not obligation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Associated obligation '{rec.obligation_id}' not found.",
            )

        old_rec_status = rec.status
        old_ob_status = obligation.status
        operator = request.operator or "Operator"
        action = request.action
        now = utc_now()

        resolution_data = {
            "action": action.value,
            "operator": operator,
            "notes": request.notes or "",
            "previous_obligation_status": old_ob_status.value,
            "resulting_obligation_status": old_ob_status.value,
            "timestamp": now.isoformat(),
            "selected_evidence_id": request.selected_evidence_id,
        }

        # 1. CONFIRM_COMPLETION: Transition obligation to COMPLETED and cascade graph
        if action == ReconciliationResolutionAction.CONFIRM_COMPLETION:
            validate_status_transition(old_ob_status, ObligationStatus.COMPLETED)
            obligation.status = ObligationStatus.COMPLETED
            obligation.block_reason = None
            resolution_data["resulting_obligation_status"] = ObligationStatus.COMPLETED.value

            # Update selected evidence or primary supporting evidence to CONFIRMED
            target_ev_id = request.selected_evidence_id or (rec.supporting_evidence_ids[0] if rec.supporting_evidence_ids else None)
            if target_ev_id:
                ev = await session.get(Evidence, target_ev_id)
                if ev:
                    ev.correlation_status = CorrelationStatus.CONFIRMED

            # Append audit entry to obligation.evidence
            current_audit = list(obligation.evidence or [])
            current_audit.append({
                "type": "reconciliation_resolution",
                "event": "OBLIGATION_COMPLETED_VIA_RECONCILIATION",
                "reconciliation_id": rec.id,
                "decision": action.value,
                "operator": operator,
                "notes": request.notes,
                "recorded_at": now.isoformat(),
                "status_transition": f"{old_ob_status.value} -> COMPLETED",
            })
            obligation.evidence = current_audit

            rec.status = ReconciliationStatus.RESOLVED_SUPPORTING
            await session.flush()

            # Trigger Phase 3 Authoritative Graph Propagation to unblock dependents
            dependents = await GraphService.get_dependents(session, obligation.id)
            for dep in dependents:
                await GraphService.evaluate_and_propagate(session, dep.id)

        # 2. CONFIRM_NOT_COMPLETED: Acknowledge deliverable is missing/invalid, keep active
        elif action == ReconciliationResolutionAction.CONFIRM_NOT_COMPLETED:
            rec.status = ReconciliationStatus.RESOLVED_CONFLICTING
            # Mark suggested completion evidence as rejected if present
            if rec.supporting_evidence_ids:
                for eid in rec.supporting_evidence_ids:
                    ev = await session.get(Evidence, eid)
                    if ev and ev.correlation_status == CorrelationStatus.SUGGESTED:
                        ev.correlation_status = CorrelationStatus.REJECTED

            current_audit = list(obligation.evidence or [])
            current_audit.append({
                "type": "reconciliation_resolution",
                "event": "RECONCILIATION_NOT_COMPLETED_CONFIRMED",
                "reconciliation_id": rec.id,
                "decision": action.value,
                "operator": operator,
                "notes": request.notes,
                "recorded_at": now.isoformat(),
            })
            obligation.evidence = current_audit

        # 3. KEEP_OBLIGATION_ACTIVE: Preserve active status
        elif action == ReconciliationResolutionAction.KEEP_OBLIGATION_ACTIVE:
            rec.status = ReconciliationStatus.RESOLVED_CONFLICTING
            current_audit = list(obligation.evidence or [])
            current_audit.append({
                "type": "reconciliation_resolution",
                "event": "RECONCILIATION_KEPT_ACTIVE",
                "reconciliation_id": rec.id,
                "operator": operator,
                "notes": request.notes,
                "recorded_at": now.isoformat(),
            })
            obligation.evidence = current_audit

        # 4. MARK_AS_STALE: Mark conflicting evidence as stale/superseded
        elif action == ReconciliationResolutionAction.MARK_AS_STALE:
            rec.status = ReconciliationStatus.RESOLVED_SUPPORTING
            if rec.conflicting_evidence_ids:
                for eid in rec.conflicting_evidence_ids:
                    ev = await session.get(Evidence, eid)
                    if ev:
                        ev.correlation_status = CorrelationStatus.REJECTED

            current_audit = list(obligation.evidence or [])
            current_audit.append({
                "type": "reconciliation_resolution",
                "event": "CONFLICTING_EVIDENCE_MARKED_STALE",
                "reconciliation_id": rec.id,
                "operator": operator,
                "notes": request.notes,
                "recorded_at": now.isoformat(),
            })
            obligation.evidence = current_audit

        # 5. DISMISS_CONTRADICTION
        elif action == ReconciliationResolutionAction.DISMISS_CONTRADICTION:
            rec.status = ReconciliationStatus.DISMISSED

        # 6. REOPEN_OBLIGATION
        elif action == ReconciliationResolutionAction.REOPEN_OBLIGATION:
            if old_ob_status == ObligationStatus.COMPLETED:
                validate_status_transition(old_ob_status, ObligationStatus.IN_PROGRESS)
                obligation.status = ObligationStatus.IN_PROGRESS
                resolution_data["resulting_obligation_status"] = ObligationStatus.IN_PROGRESS.value
                rec.status = ReconciliationStatus.RESOLVED_CONFLICTING
                await session.flush()
                # Re-evaluate downstream graph
                dependents = await GraphService.get_dependents(session, obligation.id)
                for dep in dependents:
                    await GraphService.evaluate_and_propagate(session, dep.id)

        rec.resolution = resolution_data
        rec.resolved_by = operator
        rec.resolved_at = now
        rec.updated_at = now
        if actor_user_id:
            rec.actor_user_id = actor_user_id

        await session.flush()

        from app.services.audit_service import AuditService
        from app.core.status_machine import AuditAction
        await AuditService.record(
            session=session,
            workspace_id=rec.workspace_id,
            action=AuditAction.RECONCILIATION_RESOLVED,
            actor_user_id=actor_user_id,
            entity_type="reconciliation",
            entity_id=rec.id,
            before_state={"status": old_rec_status.value},
            after_state={"status": rec.status.value, "decision": action.value},
            reason=request.notes or f"Contradiction resolved with action {action.value}",
        )

        await session.refresh(rec)
        await session.refresh(obligation)

        logger.info(
            f"ReconciliationResolved: Rec [{rec.id}] for Ob [{obligation.id}] resolved with [{action.value}] by [{operator}]."
        )
        return await cls._enrich_response(session, rec)

    @classmethod
    async def dismiss_reconciliation(
        cls,
        session: AsyncSession,
        reconciliation_id: str,
        request: ReconciliationDismissRequest,
        workspace_id: Optional[str] = None,
        actor_user_id: Optional[str] = None,
    ) -> ReconciliationRecordResponse:
        """Dismisses an active contradiction record."""
        rec = await session.get(ReconciliationRecord, reconciliation_id)
        if not rec or (workspace_id and rec.workspace_id != workspace_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reconciliation record '{reconciliation_id}' not found in active workspace.",
            )

        now = utc_now()
        rec.status = ReconciliationStatus.DISMISSED
        rec.resolved_by = request.operator or "Operator"
        rec.resolved_at = now
        if actor_user_id:
            rec.actor_user_id = actor_user_id
        rec.resolution = {
            "action": "DISMISSED",
            "operator": request.operator or "Operator",
            "reason": request.reason or "Dismissed by operator",
            "timestamp": now.isoformat(),
        }
        rec.updated_at = now
        await session.flush()

        from app.services.audit_service import AuditService
        from app.core.status_machine import AuditAction
        await AuditService.record(
            session=session,
            workspace_id=rec.workspace_id,
            action=AuditAction.RECONCILIATION_DISMISSED,
            actor_user_id=actor_user_id,
            entity_type="reconciliation",
            entity_id=rec.id,
            after_state={"status": ReconciliationStatus.DISMISSED.value},
            reason=request.reason or "Contradiction dismissed by operator",
        )

        await session.refresh(rec)

        return await cls._enrich_response(session, rec)

    @classmethod
    async def get_reconciliation(
        cls, session: AsyncSession, reconciliation_id: str, workspace_id: Optional[str] = None
    ) -> ReconciliationRecordResponse:
        """Retrieves a single reconciliation record by ID with full provenance timeline."""
        rec = await session.get(ReconciliationRecord, reconciliation_id)
        if not rec or (workspace_id and rec.workspace_id != workspace_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reconciliation record '{reconciliation_id}' not found in active workspace.",
            )
        return await cls._enrich_response(session, rec)

    @classmethod
    async def get_by_obligation(
        cls, session: AsyncSession, obligation_id: str, workspace_id: Optional[str] = None
    ) -> Optional[ReconciliationRecordResponse]:
        """Retrieves the latest reconciliation record for a specific obligation."""
        stmt = (
            select(ReconciliationRecord)
            .where(ReconciliationRecord.obligation_id == obligation_id)
        )
        if workspace_id:
            stmt = stmt.where(ReconciliationRecord.workspace_id == workspace_id)
        stmt = stmt.order_by(desc(ReconciliationRecord.created_at))
        res = await session.execute(stmt)
        rec = res.scalars().first()
        if not rec:
            return None
        return await cls._enrich_response(session, rec)

    @classmethod
    async def list_reconciliations(
        cls,
        session: AsyncSession,
        status_filter: Optional[ReconciliationStatus] = None,
        obligation_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        workspace_id: Optional[str] = None,
    ) -> ReconciliationListResponse:
        """Lists reconciliation records with optional status and obligation filtering within a workspace."""
        query = select(ReconciliationRecord)
        if workspace_id:
            query = query.where(ReconciliationRecord.workspace_id == workspace_id)
        if status_filter:
            query = query.where(ReconciliationRecord.status == status_filter)
        if obligation_id:
            query = query.where(ReconciliationRecord.obligation_id == obligation_id)

        query = query.order_by(desc(ReconciliationRecord.updated_at))
        res = await session.execute(query)
        all_recs = list(res.scalars().all())

        conflicting_cnt = sum(1 for r in all_recs if r.status == ReconciliationStatus.CONFLICTING)
        consistent_cnt = sum(1 for r in all_recs if r.status == ReconciliationStatus.CONSISTENT)
        ambiguous_cnt = sum(1 for r in all_recs if r.status == ReconciliationStatus.AMBIGUOUS)
        resolved_cnt = sum(1 for r in all_recs if r.status in [ReconciliationStatus.RESOLVED_SUPPORTING, ReconciliationStatus.RESOLVED_CONFLICTING, ReconciliationStatus.DISMISSED])

        paginated = all_recs[offset: offset + limit]
        items = []
        for r in paginated:
            items.append(await cls._enrich_response(session, r))

        return ReconciliationListResponse(
            items=items,
            total=len(all_recs),
            conflicting_count=conflicting_cnt,
            consistent_count=consistent_cnt,
            ambiguous_count=ambiguous_cnt,
            resolved_count=resolved_cnt,
        )

    @classmethod
    async def _enrich_response(
        cls, session: AsyncSession, rec: ReconciliationRecord
    ) -> ReconciliationRecordResponse:
        """Enriches the response with obligation details and full chronological evidence provenance timeline."""
        obligation = await session.get(Obligation, rec.obligation_id)
        
        # Build chronological evidence timeline
        timeline: List[EvidenceProvenanceDetail] = []
        ev_stmt = (
            select(Evidence)
            .where(Evidence.obligation_id == rec.obligation_id)
            .order_by(Evidence.observed_at.asc())
        )
        ev_res = await session.execute(ev_stmt)
        evidence_list = list(ev_res.scalars().all())

        sup_set = set(rec.supporting_evidence_ids or [])
        conf_set = set(rec.conflicting_evidence_ids or [])

        for ev in evidence_list:
            prov = ev.source_type
            recips = []
            if isinstance(ev.extra_metadata, dict):
                prov = ev.extra_metadata.get("source_provider") or prov
                recips = ev.extra_metadata.get("recipients") or []

            timeline.append(
                EvidenceProvenanceDetail(
                    evidence_id=ev.id,
                    source_type=ev.source_type,
                    source_ref=ev.source_ref,
                    provider=prov,
                    actor=ev.actor,
                    recipients=recips,
                    semantic_role=ev.semantic_role,
                    correlation_confidence=ev.correlation_confidence,
                    content=ev.content,
                    observed_at=ev.observed_at,
                    is_supporting=ev.id in sup_set or ev.semantic_role == EventSemanticRole.COMPLETION_SIGNAL,
                    is_conflicting=ev.id in conf_set or ev.semantic_role == EventSemanticRole.NON_COMPLETION_SIGNAL,
                    reasoning=ev.reasoning,
                )
            )

        resp = ReconciliationRecordResponse.model_validate(rec)
        resp.evidence_timeline = timeline
        if obligation:
            resp.obligation_action = obligation.action
            resp.obligation_owner = obligation.owner
            resp.obligation_beneficiary = obligation.beneficiary
            resp.obligation_status = obligation.status

        return resp
