"""
Phase 18 Workspace Settings & Onboarding Progress Service.
"""

from typing import Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.core.status_machine import (
    WorkspaceRole,
    OnboardingStep,
    AuditAction,
    ROLE_HIERARCHY,
)
from app.models.auth import WorkspaceMembership
from app.models.organization import WorkspaceSettings
from app.schemas.organization import (
    WorkspaceSettingsResponse,
    WorkspaceSettingsUpdateRequest,
    OnboardingProgressResponse,
)
from app.services.audit_service import AuditService

STEP_ORDER = [
    OnboardingStep.WELCOME,
    OnboardingStep.CREATE_WORKSPACE,
    OnboardingStep.INVITE_TEAM,
    OnboardingStep.CONNECT_SLACK,
    OnboardingStep.MONITORING_PREFS,
    OnboardingStep.IMPORT_OBLIGATIONS,
    OnboardingStep.COMPLETED,
]


class WorkspaceSettingsService:

    @classmethod
    async def get_or_create_settings(
        cls,
        session: AsyncSession,
        workspace_id: str,
    ) -> WorkspaceSettings:
        stmt = select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == workspace_id)
        settings = (await session.execute(stmt)).scalar_one_or_none()
        if not settings:
            settings = WorkspaceSettings(
                workspace_id=workspace_id,
                timezone="UTC",
                onboarding_step=OnboardingStep.WELCOME,
                notification_preferences={
                    "critical_risk_detected": True,
                    "evidence_awaiting_confirmation": True,
                    "decision_plan_awaiting_approval": True,
                    "execution_failed": True,
                    "integration_disconnected": True,
                    "obligation_approaching_deadline": True,
                },
                retention_days=90,
                custom_settings={},
            )
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return settings

    @classmethod
    async def get_settings(
        cls,
        session: AsyncSession,
        workspace_id: str,
    ) -> WorkspaceSettingsResponse:
        settings = await cls.get_or_create_settings(session, workspace_id)
        return WorkspaceSettingsResponse.model_validate(settings)

    @classmethod
    async def update_settings(
        cls,
        session: AsyncSession,
        workspace_id: str,
        user_id: str,
        req: WorkspaceSettingsUpdateRequest,
    ) -> WorkspaceSettingsResponse:
        # Check permissions (ADMIN or OWNER)
        stmt_mem = select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        mem = (await session.execute(stmt_mem)).scalar_one_or_none()
        if not mem or ROLE_HIERARCHY.get(mem.role, 0) < ROLE_HIERARCHY.get(WorkspaceRole.ADMIN, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace ADMIN or OWNER can update workspace settings.",
            )

        settings = await cls.get_or_create_settings(session, workspace_id)
        if req.timezone is not None:
            settings.timezone = req.timezone
        if req.onboarding_step is not None:
            settings.onboarding_step = req.onboarding_step
        if req.notification_preferences is not None:
            current = dict(settings.notification_preferences or {})
            current.update(req.notification_preferences)
            settings.notification_preferences = current
        if req.retention_days is not None:
            settings.retention_days = req.retention_days
        if req.custom_settings is not None:
            current_custom = dict(settings.custom_settings or {})
            current_custom.update(req.custom_settings)
            settings.custom_settings = current_custom

        await AuditService.record(
            session=session,
            workspace_id=workspace_id,
            action=AuditAction.WORKSPACE_UPDATED,
            actor_user_id=user_id,
            actor_role=mem.role.value,
            entity_type="workspace_settings",
            entity_id=settings.id,
            reason="Updated workspace settings and preferences",
        )
        await session.commit()
        await session.refresh(settings)
        return WorkspaceSettingsResponse.model_validate(settings)

    @classmethod
    async def get_onboarding_progress(
        cls,
        session: AsyncSession,
        workspace_id: str,
    ) -> OnboardingProgressResponse:
        settings = await cls.get_or_create_settings(session, workspace_id)
        curr = settings.onboarding_step
        try:
            idx = STEP_ORDER.index(curr)
        except ValueError:
            idx = 0
        completed = [s.value for s in STEP_ORDER[:idx]]
        is_done = curr == OnboardingStep.COMPLETED

        return OnboardingProgressResponse(
            workspace_id=workspace_id,
            current_step=curr,
            completed_steps=completed,
            is_completed=is_done,
        )

    @classmethod
    async def update_onboarding_step(
        cls,
        session: AsyncSession,
        workspace_id: str,
        step: OnboardingStep,
    ) -> OnboardingProgressResponse:
        settings = await cls.get_or_create_settings(session, workspace_id)
        settings.onboarding_step = step
        await session.commit()
        return await cls.get_onboarding_progress(session, workspace_id)
