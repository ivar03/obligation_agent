import re
import uuid
from typing import Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User, Workspace, WorkspaceMembership
from app.core.status_machine import WorkspaceRole
from app.core.security import hash_password, verify_password, create_session_token
from app.schemas.auth import (
    UserResponse,
    WorkspaceResponse,
    AuthResponse,
)


def slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", slug) or "workspace"


class AuthService:
    """
    Core authentication service managing user registration, credential authentication,
    session tokens, and development provisioning.
    """

    @classmethod
    async def ensure_default_dev_user(cls, session: AsyncSession) -> Tuple[User, Workspace, WorkspaceMembership]:
        """
        Ensures the default demo/development user and workspace exist for local dev and legacy tests.
        """
        user_stmt = select(User).where(User.id == "usr-default")
        user_res = await session.execute(user_stmt)
        user = user_res.scalar_one_or_none()

        ws_stmt = select(Workspace).where(Workspace.id == "ws-default")
        ws_res = await session.execute(ws_stmt)
        ws = ws_res.scalar_one_or_none()

        if not ws:
            ws = Workspace(
                id="ws-default",
                name="Default Workspace",
                slug="default-workspace",
            )
            session.add(ws)
            await session.commit()

        if not user:
            default_hash = hash_password("demo1234")
            user = User(
                id="usr-default",
                email="demo@obligation.local",
                password_hash=default_hash,
                display_name="Demo User",
                is_active=True,
            )
            session.add(user)
            await session.commit()

        mem_stmt = select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == "ws-default",
            WorkspaceMembership.user_id == "usr-default",
        )
        mem_res = await session.execute(mem_stmt)
        mem = mem_res.scalar_one_or_none()

        if not mem:
            mem = WorkspaceMembership(
                id="mem-default",
                workspace_id="ws-default",
                user_id="usr-default",
                role=WorkspaceRole.OWNER,
            )
            session.add(mem)
            await session.commit()

        return user, ws, mem

    @classmethod
    async def register_user(
        cls,
        session: AsyncSession,
        email: str,
        password: str,
        display_name: str,
        workspace_name: Optional[str] = None,
    ) -> AuthResponse:
        """
        Registers a new user and provisions their initial default workspace as OWNER.
        """
        clean_email = email.strip().lower()
        if not clean_email or "@" not in clean_email:
            raise ValueError("A valid email address is required.")
        if not password or len(password) < 6:
            raise ValueError("Password must be at least 6 characters long.")
        if not display_name.strip():
            raise ValueError("Display name is required.")

        # Check unique email
        existing_stmt = select(User).where(User.email == clean_email)
        existing_res = await session.execute(existing_stmt)
        if existing_res.scalar_one_or_none():
            raise ValueError(f"User with email '{clean_email}' already exists.")

        # Create user
        user = User(
            email=clean_email,
            password_hash=hash_password(password),
            display_name=display_name.strip(),
            is_active=True,
        )
        session.add(user)
        await session.flush()

        # Create workspace
        ws_title = workspace_name.strip() if workspace_name and workspace_name.strip() else f"{display_name}'s Workspace"
        base_slug = slugify(ws_title)
        slug = base_slug

        # Ensure unique slug
        slug_check = await session.execute(select(Workspace).where(Workspace.slug == slug))
        if slug_check.scalar_one_or_none():
            slug = f"{base_slug}-{str(uuid.uuid4())[:6]}"

        ws = Workspace(
            name=ws_title,
            slug=slug,
        )
        session.add(ws)
        await session.flush()

        # Create membership
        membership = WorkspaceMembership(
            workspace_id=ws.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
        )
        session.add(membership)
        await session.commit()

        token = create_session_token(user.id, ws.id)

        # Record audit events for workspace creation and session creation
        from app.services.audit_service import AuditService
        from app.core.status_machine import AuditAction, AuditResult
        await AuditService.record(
            session=session,
            workspace_id=ws.id,
            action=AuditAction.WORKSPACE_CREATED,
            actor_user_id=user.id,
            actor_role=WorkspaceRole.OWNER.value,
            entity_type="workspace",
            entity_id=ws.id,
            after_state={"name": ws.name, "slug": ws.slug},
            reason="User registered initial workspace",
        )
        await AuditService.record_auth_event(
            session=session,
            workspace_id=ws.id,
            action=AuditAction.AUTH_SESSION_CREATED,
            actor_user_id=user.id,
            email=user.email,
            result=AuditResult.SUCCESS,
            reason="Account created and session issued",
        )
        await session.commit()

        return AuthResponse(
            user=UserResponse(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
                is_active=user.is_active,
                created_at=user.created_at,
            ),
            current_workspace=WorkspaceResponse(
                id=ws.id,
                name=ws.name,
                slug=ws.slug,
                role=WorkspaceRole.OWNER.value,
                created_at=ws.created_at,
            ),
            token=token,
            role=WorkspaceRole.OWNER.value,
            workspaces=[
                WorkspaceResponse(
                    id=ws.id,
                    name=ws.name,
                    slug=ws.slug,
                    role=WorkspaceRole.OWNER.value,
                    created_at=ws.created_at,
                )
            ],
        )

    @classmethod
    async def authenticate_user(
        cls,
        session: AsyncSession,
        email: str,
        password: str,
    ) -> AuthResponse:
        """
        Authenticates credentials and returns user and active workspace.
        """
        clean_email = email.strip().lower()
        stmt = select(User).where(User.email == clean_email)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            from app.services.audit_service import AuditService
            from app.core.status_machine import AuditAction, AuditResult
            await AuditService.record_auth_event(
                session=session,
                workspace_id="ws-default",
                action=AuditAction.AUTH_LOGIN_FAILED,
                actor_user_id=user.id if user else None,
                email=clean_email,
                result=AuditResult.FAILED,
                reason="Invalid email or password",
            )
            await session.commit()
            raise ValueError("Invalid email or password.")
        if not user.is_active:
            raise ValueError("User account is disabled.")

        # Find user's workspaces
        mem_stmt = select(WorkspaceMembership, Workspace).join(
            Workspace, WorkspaceMembership.workspace_id == Workspace.id
        ).where(WorkspaceMembership.user_id == user.id)
        mem_res = await session.execute(mem_stmt)
        rows = mem_res.all()

        if not rows:
            # Create a personal workspace if user somehow has none
            ws = Workspace(
                name=f"{user.display_name}'s Workspace",
                slug=f"workspace-{str(uuid.uuid4())[:8]}",
            )
            session.add(ws)
            await session.flush()
            mem = WorkspaceMembership(
                workspace_id=ws.id,
                user_id=user.id,
                role=WorkspaceRole.OWNER,
            )
            session.add(mem)
            await session.commit()
            active_ws = ws
            active_role = WorkspaceRole.OWNER.value
            all_workspaces = [
                WorkspaceResponse(
                    id=ws.id,
                    name=ws.name,
                    slug=ws.slug,
                    role=active_role,
                    created_at=ws.created_at,
                )
            ]
        else:
            primary_mem, primary_ws = rows[0]
            active_ws = primary_ws
            active_role = primary_mem.role.value if hasattr(primary_mem.role, "value") else str(primary_mem.role)
            all_workspaces = [
                WorkspaceResponse(
                    id=w.id,
                    name=w.name,
                    slug=w.slug,
                    role=m.role.value if hasattr(m.role, "value") else str(m.role),
                    created_at=w.created_at,
                )
                for m, w in rows
            ]

        token = create_session_token(user.id, active_ws.id)

        from app.services.audit_service import AuditService
        from app.core.status_machine import AuditAction, AuditResult
        await AuditService.record_auth_event(
            session=session,
            workspace_id=active_ws.id,
            action=AuditAction.AUTH_LOGIN,
            actor_user_id=user.id,
            email=user.email,
            result=AuditResult.SUCCESS,
            reason="User authenticated successfully with valid credentials",
        )
        await session.commit()

        return AuthResponse(
            user=UserResponse(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
                is_active=user.is_active,
                created_at=user.created_at,
            ),
            current_workspace=WorkspaceResponse(
                id=active_ws.id,
                name=active_ws.name,
                slug=active_ws.slug,
                role=active_role,
                created_at=active_ws.created_at,
            ),
            token=token,
            role=active_role,
            workspaces=all_workspaces,
        )

    @classmethod
    async def get_user_profile(
        cls,
        session: AsyncSession,
        user: User,
        workspace_id: Optional[str] = None,
    ) -> AuthResponse:
        """
        Retrieves user profile and current workspace context.
        """
        mem_stmt = select(WorkspaceMembership, Workspace).join(
            Workspace, WorkspaceMembership.workspace_id == Workspace.id
        ).where(WorkspaceMembership.user_id == user.id)
        mem_res = await session.execute(mem_stmt)
        rows = mem_res.all()

        all_workspaces = [
            WorkspaceResponse(
                id=w.id,
                name=w.name,
                slug=w.slug,
                role=m.role.value if hasattr(m.role, "value") else str(m.role),
                created_at=w.created_at,
            )
            for m, w in rows
        ]

        # Select target workspace if requested and user is a member
        target_row = None
        if workspace_id:
            target_row = next((r for r in rows if r[1].id == workspace_id), None)

        if not target_row and rows:
            target_row = rows[0]

        if target_row:
            active_mem, active_ws = target_row
            active_role = active_mem.role.value if hasattr(active_mem.role, "value") else str(active_mem.role)
        else:
            active_ws = Workspace(id="ws-default", name="Default Workspace", slug="default-workspace")
            active_role = WorkspaceRole.MEMBER.value

        token = create_session_token(user.id, active_ws.id)

        return AuthResponse(
            user=UserResponse(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
                is_active=user.is_active,
                created_at=user.created_at,
            ),
            current_workspace=WorkspaceResponse(
                id=active_ws.id,
                name=active_ws.name,
                slug=active_ws.slug,
                role=active_role,
                created_at=active_ws.created_at,
            ),
            token=token,
            role=active_role,
            workspaces=all_workspaces,
        )
