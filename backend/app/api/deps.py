from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.extraction_service import ExtractionService


async def get_extraction_service() -> ExtractionService:
    return ExtractionService()


DatabaseSession = Depends(get_db)
ExtractionServiceDep = Depends(get_extraction_service)
