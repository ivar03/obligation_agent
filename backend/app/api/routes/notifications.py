"""
Phase 18 In-App Notifications API Endpoints.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.auth import WorkspaceMembership, User
from app.core.auth_deps import get_current_membership, get_current_user
from app.services.notification_service import NotificationService
from app.schemas.organization import NotificationListResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = Query(False, description="Filter unread only"),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
):
    """
    Lists in-app notifications and alerts for the current user and workspace.
    """
    return await NotificationService.list_notifications(
        session=session,
        workspace_id=membership.workspace_id,
        user_id=user.id,
        unread_only=unread_only,
        limit=limit,
    )


@router.patch("/{id}/read", status_code=status.HTTP_200_OK)
async def mark_notification_read(
    id: str,
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
):
    """
    Marks a single notification as read.
    """
    await NotificationService.mark_read(session, id, membership.workspace_id)
    return {"message": "Notification marked as read."}


@router.post("/read-all", status_code=status.HTTP_200_OK)
async def mark_all_notifications_read(
    user: User = Depends(get_current_user),
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
):
    """
    Marks all notifications for the workspace/user as read.
    """
    await NotificationService.mark_all_read(session, membership.workspace_id, user.id)
    return {"message": "All notifications marked as read."}
