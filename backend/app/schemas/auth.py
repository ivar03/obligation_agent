from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    is_active: bool
    created_at: datetime


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str
    workspace_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    role: Optional[str] = None
    created_at: datetime


class WorkspaceCreateRequest(BaseModel):
    name: str
    slug: Optional[str] = None


class WorkspaceUpdateRequest(BaseModel):
    name: Optional[str] = None


class WorkspaceMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    workspace_id: str
    email: str
    display_name: str
    role: str
    joined_at: datetime


class AddMemberRequest(BaseModel):
    email: str
    role: str = "MEMBER"


class UpdateMemberRoleRequest(BaseModel):
    role: str


class AuthResponse(BaseModel):
    user: UserResponse
    current_workspace: WorkspaceResponse
    token: str
    role: str
    workspaces: List[WorkspaceResponse] = Field(default_factory=list)
