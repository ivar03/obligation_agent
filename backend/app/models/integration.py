import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Text,
    DateTime,
    JSON,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IntegrationConnection(Base):
    """
    First-class model representing an external provider connection (e.g., Slack workspace).
    Stores safe connection metadata and isolates credentials behind an abstraction.
    """
    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint("workspace_id", "provider", "external_account_id", name="uq_workspace_provider_account"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        default="ws-default",
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    external_account_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    external_account_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="CONNECTED",
        index=True,
    )
    encrypted_credentials: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    scopes: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    connection_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
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
