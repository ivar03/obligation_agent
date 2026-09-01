from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.database import get_db
from app.models.auth import WorkspaceMembership, User
from app.core.auth_deps import get_current_membership, get_current_user, require_permission
from app.services.csv_import_service import CsvImportService
from app.schemas.import_export import (
    CsvImportPreviewResponse,
    CsvImportCommitRequest,
    CsvImportCommitResponse,
)

router = APIRouter(prefix="/obligations/import", tags=["Data Ingestion & CSV Import"])


@router.get("/csv/template")
async def download_csv_template():
    """
    Provides a standardized, downloadable CSV template with expected headers and sample rows.
    """
    template_content = CsvImportService.get_template_csv()
    return Response(
        content=template_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="obligations_template.csv"'},
    )



@router.post("/csv/preview", response_model=CsvImportPreviewResponse)
async def preview_csv_import(
    file: Optional[UploadFile] = File(None),
    csv_content: Optional[str] = Form(None),
    membership: WorkspaceMembership = Depends(require_permission("IMPORT_OBLIGATIONS")),
    session: AsyncSession = Depends(get_db),
):
    """
    Parses and validates CSV content.
    Returns row-level validation errors, duplicate detections, and import preview before commit.
    """
    text_data = ""
    if file:
        content_bytes = await file.read()
        text_data = content_bytes.decode("utf-8", errors="replace")
    elif csv_content:
        text_data = csv_content
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a CSV file or csv_content text.",
        )

    return await CsvImportService.preview_csv(
        session=session,
        workspace_id=membership.workspace_id,
        csv_text=text_data,
    )


@router.post("/csv/commit", response_model=CsvImportCommitResponse)
async def commit_csv_import(
    req: CsvImportCommitRequest,
    user: User = Depends(get_current_user),
    membership: WorkspaceMembership = Depends(require_permission("IMPORT_OBLIGATIONS")),
    session: AsyncSession = Depends(get_db),
):
    """
    Atomically ingests the validated rows and connects dependency relationships.
    """
    if not req.rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No rows provided for import.",
        )

    return await CsvImportService.commit_import(
        session=session,
        workspace_id=membership.workspace_id,
        user_id=user.id,
        rows=req.rows,
        skip_duplicates=req.skip_duplicates,
    )
