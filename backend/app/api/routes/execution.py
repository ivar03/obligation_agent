"""
FastAPI Routes for Phase 16 Controlled Decision Execution Layer.
Mounted at /api/intelligence/execution/
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.auth import User, Workspace
from app.core.auth_deps import get_current_user, get_current_workspace
from app.schemas.execution import (
    ExecutionAuthorizeRequest,
    ExecutionExecuteRequest,
    ExecutionRecordResponse,
    ExecutionReceiptResponse,
    ExecutionCancelRequest,
    ExecutionRetryRequest,
    ExecutionQueueResponse,
)
from app.services.execution.execution_service import ExecutionService

router = APIRouter(prefix="/intelligence/execution", tags=["Controlled Decision Execution"])


@router.post("/{plan_id}/authorize", response_model=ExecutionRecordResponse, status_code=status.HTTP_200_OK)
async def authorize_decision_execution(
    plan_id: str,
    payload: Optional[ExecutionAuthorizeRequest] = None,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Explicitly authorizes execution of an approved Decision Plan.
    Validates 10 safety conditions before creating or returning an AUTHORIZED ExecutionRecord.
    """
    return await ExecutionService.authorize(
        session=session,
        plan_id=plan_id,
        user=current_user,
        workspace_id=workspace.id,
        request=payload,
    )


@router.post("/{plan_id}/execute", response_model=ExecutionRecordResponse, status_code=status.HTTP_200_OK)
async def execute_decision_plan(
    plan_id: str,
    payload: Optional[ExecutionExecuteRequest] = None,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Executes an authorized Decision Plan through the designated provider adapter.
    Strongly idempotent: repeated requests return the existing execution record without duplicate provider calls.
    """
    return await ExecutionService.execute(
        session=session,
        plan_id=plan_id,
        user=current_user,
        workspace_id=workspace.id,
        request=payload,
    )


@router.get("/queue", response_model=ExecutionQueueResponse, status_code=status.HTTP_200_OK)
async def get_execution_queue(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Returns workspace-wide execution queue with aggregated metrics.
    """
    return await ExecutionService.get_queue(session=session, workspace_id=workspace.id)


@router.get("/{execution_id}", response_model=ExecutionRecordResponse, status_code=status.HTTP_200_OK)
async def get_execution_record(
    execution_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Retrieves a single execution record by ID.
    """
    return await ExecutionService.get_by_id(
        session=session,
        execution_id=execution_id,
        workspace_id=workspace.id,
    )


@router.get("/{execution_id}/receipt", response_model=ExecutionReceiptResponse, status_code=status.HTTP_200_OK)
async def get_execution_receipt(
    execution_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Retrieves an immutable execution receipt for audit and operator review.
    """
    return await ExecutionService.get_receipt(
        session=session,
        execution_id=execution_id,
        workspace_id=workspace.id,
    )


@router.post("/{execution_id}/cancel", response_model=ExecutionRecordResponse, status_code=status.HTTP_200_OK)
async def cancel_execution_record(
    execution_id: str,
    payload: ExecutionCancelRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Cancels a pending or queued execution.
    """
    return await ExecutionService.cancel(
        session=session,
        execution_id=execution_id,
        user=current_user,
        reason=payload.reason,
        workspace_id=workspace.id,
    )


@router.post("/{execution_id}/retry", response_model=ExecutionRecordResponse, status_code=status.HTTP_200_OK)
async def retry_execution_record(
    execution_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Retries an eligible failed execution if retry limit is not exceeded.
    """
    return await ExecutionService.retry(
        session=session,
        execution_id=execution_id,
        user=current_user,
        workspace_id=workspace.id,
    )


@router.get("/{plan_id}/history", response_model=List[ExecutionRecordResponse], status_code=status.HTTP_200_OK)
async def get_plan_execution_history(
    plan_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
):
    """
    Retrieves execution history for a Decision Plan.
    """
    return await ExecutionService.get_history_for_plan(
        session=session,
        plan_id=plan_id,
        workspace_id=workspace.id,
    )
