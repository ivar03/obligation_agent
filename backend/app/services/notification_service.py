"""
Phase 18 In-App Notification Service.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import InAppNotification
from app.core.status_machine import NotificationCategory, NotificationSeverity
from app.schemas.organization import InAppNotificationResponse, NotificationListResponse


class NotificationService:
    """
    Manages in-app notifications and alerts.
    """

    @classmethod
    async def create_notification(
        cls,
        session: AsyncSession,
        workspace_id: str,
        category: NotificationCategory,
        severity: NotificationSeverity,
        title: str,
        message: str,
        link: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InAppNotification:
        notification = InAppNotification(
            workspace_id=workspace_id,
            user_id=user_id,
            category=category,
            severity=severity,
            title=title,
            message=message,
            link=link,
            metadata_payload=metadata or {},
        )
        session.add(notification)
        await session.commit()
        await session.refresh(notification)
        return notification

    @classmethod
    async def list_notifications(
        cls,
        session: AsyncSession,
        workspace_id: str,
        user_id: Optional[str] = None,
        unread_only: bool = False,
        limit: int = 50,
    ) -> NotificationListResponse:
        stmt = (
            select(InAppNotification)
            .where(
                and_(
                    InAppNotification.workspace_id == workspace_id,
                    (InAppNotification.user_id == user_id) | (InAppNotification.user_id.is_(None)),
                )
            )
        )
        if unread_only:
            stmt = stmt.where(InAppNotification.is_read == False)

        stmt = stmt.order_by(InAppNotification.created_at.desc()).limit(limit)
        items = (await session.execute(stmt)).scalars().all()

        # Unread count
        stmt_unread = select(InAppNotification).where(
            and_(
                InAppNotification.workspace_id == workspace_id,
                InAppNotification.is_read == False,
                (InAppNotification.user_id == user_id) | (InAppNotification.user_id.is_(None)),
            )
        )
        unread_items = (await session.execute(stmt_unread)).scalars().all()

        return NotificationListResponse(
            items=[InAppNotificationResponse.model_validate(i) for i in items],
            unread_count=len(unread_items),
            total_count=len(items),
        )

    @classmethod
    async def mark_read(
        cls,
        session: AsyncSession,
        notification_id: str,
        workspace_id: str,
    ):
        notif = await session.get(InAppNotification, notification_id)
        if notif and notif.workspace_id == workspace_id:
            notif.is_read = True
            await session.commit()

    @classmethod
    async def mark_all_read(
        cls,
        session: AsyncSession,
        workspace_id: str,
        user_id: Optional[str] = None,
    ):
        stmt = (
            update(InAppNotification)
            .where(
                and_(
                    InAppNotification.workspace_id == workspace_id,
                    (InAppNotification.user_id == user_id) | (InAppNotification.user_id.is_(None)),
                    InAppNotification.is_read == False,
                )
            )
            .values(is_read=True)
        )
        await session.execute(stmt)
        await session.commit()
