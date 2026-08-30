from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.auth import User, WorkspaceMembership
from app.core.auth_deps import get_current_user, get_current_membership
from app.services.auth_service import AuthService
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    """
    Registers a new user and provisions an initial tenant workspace as OWNER.
    Sets an HTTP-only authentication session cookie.
    """
    try:
        auth_res = await AuthService.register_user(
            session=session,
            email=req.email,
            password=req.password,
            display_name=req.display_name,
            workspace_name=req.workspace_name,
        )
        # Set HTTP-only cookie
        response.set_cookie(
            key="obligation_session",
            value=auth_res.token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 7,
            path="/",
        )
        return auth_res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=AuthResponse)
async def login(
    req: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    """
    Authenticates a user via email and password, setting an HTTP-only session cookie.
    """
    try:
        auth_res = await AuthService.authenticate_user(
            session=session,
            email=req.email,
            password=req.password,
        )
        response.set_cookie(
            key="obligation_session",
            value=auth_res.token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 7,
            path="/",
        )
        return auth_res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/logout")
async def logout(response: Response):
    """
    Logs out the current session and clears the authentication cookie.
    """
    response.delete_cookie(key="obligation_session", path="/")
    response.delete_cookie(key="obligation_workspace", path="/")
    return {"message": "Successfully logged out."}


@router.get("/me", response_model=AuthResponse)
async def get_me(
    user: User = Depends(get_current_user),
    membership: WorkspaceMembership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_db),
):
    """
    Returns the authenticated user's profile, active workspace, active role, and all workspace memberships.
    """
    return await AuthService.get_user_profile(
        session=session,
        user=user,
        workspace_id=membership.workspace_id,
    )
