"""
Phase 18 Pydantic Schemas for Organization, Settings, Invitations & In-App Notifications.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, EmailStr

from app.core.status_machine import (
    WorkspaceRole,
    InvitationStatus,
    NotificationCategory,
    NotificationSeverity,
    OnboardingStep,
)


class WorkspaceInvitationCreate(BaseModel):
    invited_email: str
    role: WorkspaceRole = WorkspaceRole.MEMBER


class WorkspaceInvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    invited_email: str
    role: WorkspaceRole
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime
    invitation_token: Optional[str] = None
    invitation_url: Optional[str] = None


class AcceptInvitationRequest(BaseModel):
    token: str
    display_name: Optional[str] = None
    password: Optional[str] = None


class WorkspaceSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    timezone: str
    onboarding_step: OnboardingStep
    notification_preferences: Dict[str, Any]
    retention_days: int
    custom_settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class WorkspaceSettingsUpdateRequest(BaseModel):
    timezone: Optional[str] = None
    onboarding_step: Optional[OnboardingStep] = None
    notification_preferences: Optional[Dict[str, Any]] = None
    retention_days: Optional[int] = None
    custom_settings: Optional[Dict[str, Any]] = None


class OnboardingProgressResponse(BaseModel):
    workspace_id: str
    current_step: OnboardingStep
    completed_steps: List[str]
    is_completed: bool


class UpdateOnboardingStepRequest(BaseModel):
    step: OnboardingStep


class InAppNotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    user_id: Optional[str] = None
    category: NotificationCategory
    severity: NotificationSeverity
    title: str
    message: str
    link: Optional[str] = None
    is_read: bool
    metadata_payload: Dict[str, Any]
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: List[InAppNotificationResponse]
    unread_count: int
    total_count: int
