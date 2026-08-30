from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.auth import User
from app.core.auth_deps import get_current_user
from app.services.workspace_service import WorkspaceService
from app.schemas.auth import (
    WorkspaceResponse,
    WorkspaceCreateRequest,
    WorkspaceUpdateRequest,
    WorkspaceMemberResponse,
    AddMemberRequest,
    UpdateMemberRoleRequest,
)

router = APIRouter(prefix="/workspaces", tags=["Workspace Administration"])


@router.get("", response_model=List[WorkspaceResponse])
async def list_user_workspaces(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Lists all workspaces accessible to the authenticated user.
    """
    return await WorkspaceService.list_workspaces(session, user.id)


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    req: WorkspaceCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Creates a new multi-tenant workspace and assigns the caller as OWNER.
    """
    try:
        return await WorkspaceService.create_workspace(
            session=session,
            user_id=user.id,
            name=req.name,
            slug=req.slug,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{id}", response_model=WorkspaceResponse)
async def get_workspace(
    id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieves metadata for a specific workspace if the user is an authorized member.
    """
    try:
        return await WorkspaceService.get_workspace(session, id, user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{id}", response_model=WorkspaceResponse)
async def update_workspace(
    id: str,
    req: WorkspaceUpdateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Updates workspace metadata (requires ADMIN or OWNER role).
    """
    try:
        return await WorkspaceService.update_workspace(session, id, user.id, name=req.name)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{id}", status_code=status.HTTP_200_OK)
async def delete_workspace(
    id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Deletes a workspace (strictly requires OWNER role).
    """
    try:
        await WorkspaceService.delete_workspace(session, id, user.id)
        return {"message": f"Workspace '{id}' successfully deleted."}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{id}/members", response_model=List[WorkspaceMemberResponse])
async def get_workspace_members(
    id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Lists all members and their roles within a workspace.
    """
    try:
        return await WorkspaceService.get_members(session, id, user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{id}/members", response_model=WorkspaceMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_workspace_member(
    id: str,
    req: AddMemberRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Invites/adds a member to the workspace (requires ADMIN or OWNER role).
    """
    try:
        return await WorkspaceService.add_member(
            session=session,
            workspace_id=id,
            user_id=user.id,
            email=req.email,
            role=req.role,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{id}/members/{member_id}", response_model=WorkspaceMemberResponse)
async def update_member_role(
    id: str,
    member_id: str,
    req: UpdateMemberRoleRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Updates the role of a workspace member (requires ADMIN or OWNER role).
    """
    try:
        return await WorkspaceService.update_member_role(
            session=session,
            workspace_id=id,
            user_id=user.id,
            target_member_id=member_id,
            new_role=req.role,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{id}/members/{member_id}", status_code=status.HTTP_200_OK)
async def remove_workspace_member(
    id: str,
    member_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Removes a member from the workspace (requires ADMIN or OWNER role).
    """
    try:
        await WorkspaceService.remove_member(
            session=session,
            workspace_id=id,
            user_id=user.id,
            target_member_id=member_id,
        )
        return {"message": f"Member '{member_id}' successfully removed from workspace."}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
