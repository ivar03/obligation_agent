"""
Phase 18 Organization, Invitations, Settings & In-App Notification Database Models.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Boolean,
    Integer,
    Enum as SQLEnum,
    ForeignKey,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.status_machine import (
    WorkspaceRole,
    InvitationStatus,
    NotificationCategory,
    NotificationSeverity,
    OnboardingStep,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class WorkspaceInvitation(Base):
    """
    Tracks pending, accepted, or expired team member invitations for a workspace.
    Tokens are single-use and stored strictly as SHA-256 hashes.
    """
    __tablename__ = "workspace_invitations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "invited_email", "status", name="uq_workspace_email_pending_invite"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invited_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    role: Mapped[WorkspaceRole] = mapped_column(
        SQLEnum(WorkspaceRole, name="workspace_role_enum", native_enum=False),
        nullable=False,
        default=WorkspaceRole.MEMBER,
    )
    invited_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    status: Mapped[InvitationStatus] = mapped_column(
        SQLEnum(InvitationStatus, name="invitation_status_enum", native_enum=False),
        nullable=False,
        default=InvitationStatus.PENDING,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class WorkspaceSettings(Base):
    """
    Stores product-level workspace settings, timezone, notification policies,
    retention windows, and persistent onboarding progress.
    """
    __tablename__ = "workspace_settings"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    timezone: Mapped[str] = mapped_column(
        String(100),
        default="UTC",
        nullable=False,
    )
    onboarding_step: Mapped[OnboardingStep] = mapped_column(
        SQLEnum(OnboardingStep, name="onboarding_step_enum", native_enum=False),
        default=OnboardingStep.WELCOME,
        nullable=False,
    )
    notification_preferences: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=lambda: {
            "critical_risk_detected": True,
            "evidence_awaiting_confirmation": True,
            "decision_plan_awaiting_approval": True,
            "execution_failed": True,
            "integration_disconnected": True,
            "obligation_approaching_deadline": True,
        },
        nullable=False,
    )
    retention_days: Mapped[int] = mapped_column(
        Integer,
        default=90,
        nullable=False,
    )
    custom_settings: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class InAppNotification(Base):
    """
    In-app alert and notification records for human operators and workspace members.
    """
    __tablename__ = "in_app_notifications"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    category: Mapped[NotificationCategory] = mapped_column(
        SQLEnum(NotificationCategory, name="notification_category_enum", native_enum=False),
        nullable=False,
        default=NotificationCategory.INFORMATION,
        index=True,
    )
    severity: Mapped[NotificationSeverity] = mapped_column(
        SQLEnum(NotificationSeverity, name="notification_severity_enum", native_enum=False),
        nullable=False,
        default=NotificationSeverity.INFO,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    link: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
