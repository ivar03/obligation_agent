"""
Phase 18 Workspace Invitation Service.

Manages the lifecycle of single-use, expirable workspace member invitations.
Enforces single-use token hashes, audit records, and RBAC safety.
"""

import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.core.status_machine import (
    WorkspaceRole,
    InvitationStatus,
    AuditAction,
    AuditSeverity,
    AuditResult,
    ROLE_HIERARCHY,
)
from app.models.auth import User, Workspace, WorkspaceMembership
from app.models.organization import WorkspaceInvitation
from app.schemas.organization import WorkspaceInvitationResponse
from app.services.audit_service import AuditService
from app.core.security import hash_password


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class InvitationService:
    """
    Manages single-use secure invitations to workspaces.
    """

    @classmethod
    async def create_invitation(
        cls,
        session: AsyncSession,
        workspace_id: str,
        caller_user_id: str,
        invited_email: str,
        role: WorkspaceRole = WorkspaceRole.MEMBER,
        expires_in_days: int = 7,
    ) -> WorkspaceInvitationResponse:
        # 1. Verify caller has ADMIN or OWNER role in the workspace
        stmt_mem = select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == caller_user_id,
        )
        caller_mem = (await session.execute(stmt_mem)).scalar_one_or_none()
        if not caller_mem or ROLE_HIERARCHY.get(caller_mem.role, 0) < ROLE_HIERARCHY.get(WorkspaceRole.ADMIN, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace ADMIN or OWNER can invite new members.",
            )

        clean_email = invited_email.strip().lower()

        # 2. Check if user is already a member
        stmt_existing = (
            select(WorkspaceMembership)
            .join(User, WorkspaceMembership.user_id == User.id)
            .where(
                WorkspaceMembership.workspace_id == workspace_id,
                User.email == clean_email,
            )
        )
        if (await session.execute(stmt_existing)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User '{clean_email}' is already a member of this workspace.",
            )

        # 3. Generate single-use random token and hash
        raw_token = secrets.token_urlsafe(32)
        token_digest = hash_token(raw_token)
        expires_at = utc_now() + timedelta(days=expires_in_days)

        # 4. Cancel any previous pending invitation for this email in this workspace
        stmt_prev = select(WorkspaceInvitation).where(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.invited_email == clean_email,
            WorkspaceInvitation.status == InvitationStatus.PENDING,
        )
        prev_inv = (await session.execute(stmt_prev)).scalar_one_or_none()
        if prev_inv:
            prev_inv.status = InvitationStatus.CANCELLED

        # 5. Create new invitation
        inv = WorkspaceInvitation(
            workspace_id=workspace_id,
            invited_email=clean_email,
            role=role,
            invited_by_user_id=caller_user_id,
            token_hash=token_digest,
            status=InvitationStatus.PENDING,
            expires_at=expires_at,
        )
        session.add(inv)
        await session.flush()
        await session.refresh(inv)

        # 6. Audit
        await AuditService.record(
            session=session,
            workspace_id=workspace_id,
            action=AuditAction.WORKSPACE_MEMBER_INVITED,
            actor_user_id=caller_user_id,
            actor_role=caller_mem.role.value,
            entity_type="workspace_invitation",
            entity_id=inv.id,
            reason=f"Invited '{clean_email}' as {role.value} (Expires in {expires_in_days}d)",
        )
        await session.commit()

        # Build response with raw token only for immediate display (never logged)
        resp = WorkspaceInvitationResponse(
            id=inv.id,
            workspace_id=inv.workspace_id,
            invited_email=inv.invited_email,
            role=inv.role,
            status=inv.status,
            expires_at=inv.expires_at,
            created_at=inv.created_at,
            invitation_token=raw_token,
            invitation_url=f"/onboarding/accept?token={raw_token}",
        )
        return resp

    @classmethod
    async def accept_invitation(
        cls,
        session: AsyncSession,
        raw_token: str,
        current_user: Optional[User] = None,
        display_name: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Tuple[WorkspaceMembership, User]:
        token_digest = hash_token(raw_token.strip())

        # 1. Look up invitation by token hash
        stmt = select(WorkspaceInvitation).where(
            WorkspaceInvitation.token_hash == token_digest,
        )
        inv = (await session.execute(stmt)).scalar_one_or_none()
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or expired invitation token.",
            )

        if inv.status != InvitationStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This invitation is no longer active (Status: {inv.status.value}).",
            )

        exp_at = inv.expires_at if (inv.expires_at and inv.expires_at.tzinfo) else inv.expires_at.replace(tzinfo=timezone.utc)
        if exp_at < utc_now():
            inv.status = InvitationStatus.EXPIRED
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invitation token has expired.",
            )

        # 2. Resolve User identity
        user = current_user
        if not user:
            # Check if user with invited email already exists
            stmt_u = select(User).where(User.email == inv.invited_email)
            user = (await session.execute(stmt_u)).scalar_one_or_none()

            if not user:
                if not password:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Password is required to create your new account.",
                    )
                # Create user account
                user = User(
                    email=inv.invited_email,
                    display_name=display_name or inv.invited_email.split("@")[0].capitalize(),
                    password_hash=hash_password(password),
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                await session.refresh(user)

        # 3. Create WorkspaceMembership
        stmt_mem = select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == inv.workspace_id,
            WorkspaceMembership.user_id == user.id,
        )
        mem = (await session.execute(stmt_mem)).scalar_one_or_none()
        if not mem:
            mem = WorkspaceMembership(
                workspace_id=inv.workspace_id,
                user_id=user.id,
                role=inv.role,
            )
            session.add(mem)

        # 4. Mark invitation accepted (single-use)
        inv.status = InvitationStatus.ACCEPTED
        inv.accepted_at = utc_now()
        await session.commit()

        return mem, user

    @classmethod
    async def list_invitations(
        cls,
        session: AsyncSession,
        workspace_id: str,
        user_id: str,
    ) -> List[WorkspaceInvitationResponse]:
        # Verify caller has ADMIN or OWNER role in workspace
        stmt_mem = select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        caller_mem = (await session.execute(stmt_mem)).scalar_one_or_none()
        if not caller_mem or ROLE_HIERARCHY.get(caller_mem.role, 0) < ROLE_HIERARCHY.get(WorkspaceRole.ADMIN, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace ADMIN or OWNER can view workspace invitations.",
            )

        stmt = (
            select(WorkspaceInvitation)
            .where(WorkspaceInvitation.workspace_id == workspace_id)
            .order_by(WorkspaceInvitation.created_at.desc())
        )
        invitations = (await session.execute(stmt)).scalars().all()
        return [
            WorkspaceInvitationResponse(
                id=i.id,
                workspace_id=i.workspace_id,
                invited_email=i.invited_email,
                role=i.role,
                status=i.status,
                expires_at=i.expires_at,
                created_at=i.created_at,
                invitation_token=None,
                invitation_url=None,
            )
            for i in invitations
        ]

    @classmethod
    async def cancel_invitation(
        cls,
        session: AsyncSession,
        workspace_id: str,
        user_id: str,
        invitation_id: str,
    ):
        stmt_mem = select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        caller_mem = (await session.execute(stmt_mem)).scalar_one_or_none()
        if not caller_mem or ROLE_HIERARCHY.get(caller_mem.role, 0) < ROLE_HIERARCHY.get(WorkspaceRole.ADMIN, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace ADMIN or OWNER can cancel workspace invitations.",
            )

        inv = await session.get(WorkspaceInvitation, invitation_id)
        if not inv or inv.workspace_id != workspace_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")
        inv.status = InvitationStatus.CANCELLED
        await session.commit()

        await session.commit()
