import uuid
from typing import List, Optional
from sqlalchemy import select, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User, Workspace, WorkspaceMembership
from app.core.status_machine import WorkspaceRole, ROLE_HIERARCHY
from app.schemas.auth import (
    WorkspaceResponse,
    WorkspaceMemberResponse,
)
from app.services.auth_service import slugify


class WorkspaceService:
    """
    Workspace administration service managing multi-tenant workspaces, memberships,
    and role authorizations.
    """

    @classmethod
    async def list_workspaces(cls, session: AsyncSession, user_id: str) -> List[WorkspaceResponse]:
        """
        Lists all workspaces where the user has active membership.
        """
        stmt = select(WorkspaceMembership, Workspace).join(
            Workspace, WorkspaceMembership.workspace_id == Workspace.id
        ).where(WorkspaceMembership.user_id == user_id)
        res = await session.execute(stmt)
        rows = res.all()

        return [
            WorkspaceResponse(
                id=w.id,
                name=w.name,
                slug=w.slug,
                role=m.role.value if hasattr(m.role, "value") else str(m.role),
                created_at=w.created_at,
            )
            for m, w in rows
        ]

    @classmethod
    async def create_workspace(
        cls,
        session: AsyncSession,
        user_id: str,
        name: str,
        slug: Optional[str] = None,
    ) -> WorkspaceResponse:
        """
        Creates a new workspace and sets the creating user as OWNER.
        """
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Workspace name cannot be empty.")

        base_slug = slug.strip().lower() if slug and slug.strip() else slugify(clean_name)
        final_slug = base_slug

        existing_slug = await session.execute(select(Workspace).where(Workspace.slug == final_slug))
        if existing_slug.scalar_one_or_none():
            final_slug = f"{base_slug}-{str(uuid.uuid4())[:6]}"

        ws = Workspace(
            name=clean_name,
            slug=final_slug,
        )
        session.add(ws)
        await session.flush()

        membership = WorkspaceMembership(
            workspace_id=ws.id,
            user_id=user_id,
            role=WorkspaceRole.OWNER,
        )
        session.add(membership)
        await session.flush()

        from app.services.audit_service import AuditService
        from app.core.status_machine import AuditAction
        await AuditService.record(
            session=session,
            workspace_id=ws.id,
            action=AuditAction.WORKSPACE_CREATED,
            actor_user_id=user_id,
            actor_role=WorkspaceRole.OWNER.value,
            entity_type="workspace",
            entity_id=ws.id,
            after_state={"name": ws.name, "slug": ws.slug},
            reason="Workspace created by owner",
        )
        await session.commit()

        return WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            role=WorkspaceRole.OWNER.value,
            created_at=ws.created_at,
        )

    @classmethod
    async def get_workspace(
        cls,
        session: AsyncSession,
        workspace_id: str,
        user_id: str,
    ) -> WorkspaceResponse:
        """
        Retrieves a workspace if the user is a valid member.
        """
        stmt = select(WorkspaceMembership, Workspace).join(
            Workspace, WorkspaceMembership.workspace_id == Workspace.id
        ).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        res = await session.execute(stmt)
        row = res.first()
        if not row:
            raise ValueError(f"Workspace '{workspace_id}' not found or access denied.")

        mem, ws = row
        return WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            role=mem.role.value if hasattr(mem.role, "value") else str(mem.role),
            created_at=ws.created_at,
        )

    @classmethod
    async def update_workspace(
        cls,
        session: AsyncSession,
        workspace_id: str,
        user_id: str,
        name: Optional[str] = None,
    ) -> WorkspaceResponse:
        """
        Updates workspace properties (requires ADMIN or OWNER role).
        """
        mem_stmt = select(WorkspaceMembership, Workspace).join(
            Workspace, WorkspaceMembership.workspace_id == Workspace.id
        ).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        res = await session.execute(mem_stmt)
        row = res.first()
        if not row:
            raise ValueError("Workspace not found or access denied.")

        mem, ws = row
        if ROLE_HIERARCHY.get(mem.role, 0) < ROLE_HIERARCHY[WorkspaceRole.ADMIN]:
            raise PermissionError("Only workspace Admins or Owners can update workspace settings.")

        if name and name.strip():
            old_name = ws.name
            ws.name = name.strip()
            session.add(ws)
            await session.flush()

            from app.services.audit_service import AuditService
            from app.core.status_machine import AuditAction
            await AuditService.record(
                session=session,
                workspace_id=ws.id,
                action=AuditAction.WORKSPACE_RENAMED,
                actor_user_id=user_id,
                actor_role=mem.role.value if hasattr(mem.role, "value") else str(mem.role),
                entity_type="workspace",
                entity_id=ws.id,
                before_state={"name": old_name},
                after_state={"name": ws.name},
                reason="Workspace renamed by administrator",
            )
            await session.commit()

        return WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            role=mem.role.value if hasattr(mem.role, "value") else str(mem.role),
            created_at=ws.created_at,
        )

    @classmethod
    async def delete_workspace(
        cls,
        session: AsyncSession,
        workspace_id: str,
        user_id: str,
    ) -> None:
        """
        Deletes a workspace (requires OWNER role).
        """
        mem_stmt = select(WorkspaceMembership, Workspace).join(
            Workspace, WorkspaceMembership.workspace_id == Workspace.id
        ).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        res = await session.execute(mem_stmt)
        row = res.first()
        if not row:
            raise ValueError("Workspace not found or access denied.")

        mem, ws = row
        if mem.role != WorkspaceRole.OWNER:
            raise PermissionError("Only the workspace Owner can delete a workspace.")

        await session.delete(ws)
        await session.commit()

    @classmethod
    async def get_members(
        cls,
        session: AsyncSession,
        workspace_id: str,
        user_id: str,
    ) -> List[WorkspaceMemberResponse]:
        """
        Lists all members of a workspace (requires membership).
        """
        # Verify requesting user is member
        check_stmt = select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        check_res = await session.execute(check_stmt)
        if not check_res.scalar_one_or_none():
            raise ValueError("Workspace not found or access denied.")

        stmt = select(WorkspaceMembership, User).join(
            User, WorkspaceMembership.user_id == User.id
        ).where(WorkspaceMembership.workspace_id == workspace_id)
        res = await session.execute(stmt)
        rows = res.all()

        return [
            WorkspaceMemberResponse(
                id=m.id,
                user_id=u.id,
                workspace_id=m.workspace_id,
                email=u.email,
                display_name=u.display_name,
                role=m.role.value if hasattr(m.role, "value") else str(m.role),
                joined_at=m.created_at,
            )
            for m, u in rows
        ]

    @classmethod
    async def add_member(
        cls,
        session: AsyncSession,
        workspace_id: str,
        user_id: str,
        email: str,
        role: str = "MEMBER",
    ) -> WorkspaceMemberResponse:
        """
        Adds or invites a user to the workspace (requires ADMIN or OWNER).
        """
        # Verify inviter role
        mem_stmt = select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        mem_res = await session.execute(mem_stmt)
        inviter_mem = mem_res.scalar_one_or_none()
        if not inviter_mem or ROLE_HIERARCHY.get(inviter_mem.role, 0) < ROLE_HIERARCHY[WorkspaceRole.ADMIN]:
            raise PermissionError("Only Admins or Owners can add workspace members.")

        # Parse target role
        target_role_str = role.upper().strip()
        try:
            target_role = WorkspaceRole[target_role_str]
        except KeyError:
            target_role = WorkspaceRole.MEMBER

        # Only OWNER can invite another OWNER
        if target_role == WorkspaceRole.OWNER and inviter_mem.role != WorkspaceRole.OWNER:
            raise PermissionError("Only workspace Owners can assign the Owner role.")

        clean_email = email.strip().lower()
        user_stmt = select(User).where(User.email == clean_email)
        user_res = await session.execute(user_stmt)
        target_user = user_res.scalar_one_or_none()

        if not target_user:
            # Auto-provision user account with temp password if user doesn't exist
            from app.core.security import hash_password
            target_user = User(
                email=clean_email,
                password_hash=hash_password(str(uuid.uuid4())),
                display_name=clean_email.split("@")[0].capitalize(),
                is_active=True,
            )
            session.add(target_user)
            await session.flush()

        # Check existing membership
        existing_mem = await session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == target_user.id,
            )
        )
        if existing_mem.scalar_one_or_none():
            raise ValueError(f"User '{clean_email}' is already a member of this workspace.")

        new_mem = WorkspaceMembership(
            workspace_id=workspace_id,
            user_id=target_user.id,
            role=target_role,
        )
        session.add(new_mem)
        await session.flush()

        from app.services.audit_service import AuditService
        from app.core.status_machine import AuditAction
        await AuditService.record(
            session=session,
            workspace_id=workspace_id,
            action=AuditAction.WORKSPACE_MEMBER_INVITED,
            actor_user_id=user_id,
            actor_role=inviter_mem.role.value if hasattr(inviter_mem.role, "value") else str(inviter_mem.role),
            entity_type="workspace_membership",
            entity_id=new_mem.id,
            after_state={"user_id": target_user.id, "email": target_user.email, "role": target_role.value},
            reason="Member invited to workspace",
        )
        await session.commit()

        return WorkspaceMemberResponse(
            id=new_mem.id,
            user_id=target_user.id,
            workspace_id=workspace_id,
            email=target_user.email,
            display_name=target_user.display_name,
            role=target_role.value,
            joined_at=new_mem.created_at,
        )

    @classmethod
    async def update_member_role(
        cls,
        session: AsyncSession,
        workspace_id: str,
        user_id: str,
        target_member_id: str,
        new_role: str,
    ) -> WorkspaceMemberResponse:
        """
        Updates a member's role (requires ADMIN or OWNER).
        """
        actor_mem = await session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id,
            )
        )
        actor = actor_mem.scalar_one_or_none()
        if not actor or ROLE_HIERARCHY.get(actor.role, 0) < ROLE_HIERARCHY[WorkspaceRole.ADMIN]:
            raise PermissionError("Only Admins or Owners can modify member roles.")

        target_stmt = select(WorkspaceMembership, User).join(
            User, WorkspaceMembership.user_id == User.id
        ).where(
            or_(
                WorkspaceMembership.id == target_member_id,
                WorkspaceMembership.user_id == target_member_id,
            ),
            WorkspaceMembership.workspace_id == workspace_id,
        )
        target_res = await session.execute(target_stmt)
        row = target_res.first()
        if not row:
            raise ValueError(f"Member with ID '{target_member_id}' not found in this workspace.")

        target_mem, target_user = row
        old_role = target_mem.role.value if hasattr(target_mem.role, "value") else str(target_mem.role)

        role_enum = WorkspaceRole[new_role.upper().strip()]
        if role_enum == WorkspaceRole.OWNER and actor.role != WorkspaceRole.OWNER:
            raise PermissionError("Only an Owner can transfer or grant the Owner role.")

        target_mem.role = role_enum
        session.add(target_mem)
        await session.flush()

        from app.services.audit_service import AuditService
        from app.core.status_machine import AuditAction
        audit_act = AuditAction.WORKSPACE_OWNERSHIP_TRANSFERRED if role_enum == WorkspaceRole.OWNER else AuditAction.WORKSPACE_MEMBER_ROLE_CHANGED

        await AuditService.record(
            session=session,
            workspace_id=workspace_id,
            action=audit_act,
            actor_user_id=user_id,
            actor_role=actor.role.value if hasattr(actor.role, "value") else str(actor.role),
            entity_type="workspace_membership",
            entity_id=target_mem.id,
            before_state={"role": old_role},
            after_state={"role": role_enum.value},
            reason="Member role changed by administrator",
        )
        await session.commit()

        return WorkspaceMemberResponse(
            id=target_mem.id,
            user_id=target_user.id,
            workspace_id=workspace_id,
            email=target_user.email,
            display_name=target_user.display_name,
            role=role_enum.value,
            joined_at=target_mem.created_at,
        )

    @classmethod
    async def remove_member(
        cls,
        session: AsyncSession,
        workspace_id: str,
        user_id: str,
        target_member_id: str,
    ) -> None:
        """
        Removes a member from the workspace (requires ADMIN or OWNER).
        """
        actor_mem = await session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id,
            )
        )
        actor = actor_mem.scalar_one_or_none()
        if not actor or ROLE_HIERARCHY.get(actor.role, 0) < ROLE_HIERARCHY[WorkspaceRole.ADMIN]:
            raise PermissionError("Only Admins or Owners can remove members.")

        target_stmt = select(WorkspaceMembership).where(
            or_(
                WorkspaceMembership.id == target_member_id,
                WorkspaceMembership.user_id == target_member_id,
            ),
            WorkspaceMembership.workspace_id == workspace_id,
        )
        target_res = await session.execute(target_stmt)
        target_mem = target_res.scalar_one_or_none()
        if not target_mem:
            raise ValueError(f"Member with ID '{target_member_id}' not found in this workspace.")

        # Prevent removing last owner
        if target_mem.role == WorkspaceRole.OWNER:
            owners_stmt = select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.role == WorkspaceRole.OWNER,
            )
            owners_res = await session.execute(owners_stmt)
            if len(owners_res.scalars().all()) <= 1:
                raise ValueError("Cannot remove the sole Owner of a workspace.")

        target_user_id = target_mem.user_id
        target_mem_id = target_mem.id
        await session.delete(target_mem)
        await session.flush()

        from app.services.audit_service import AuditService
        from app.core.status_machine import AuditAction
        await AuditService.record(
            session=session,
            workspace_id=workspace_id,
            action=AuditAction.WORKSPACE_MEMBER_REMOVED,
            actor_user_id=user_id,
            actor_role=actor.role.value if hasattr(actor.role, "value") else str(actor.role),
            entity_type="workspace_membership",
            entity_id=target_mem_id,
            before_state={"removed_user_id": target_user_id},
            reason="Member removed from workspace",
        )
        await session.commit()
