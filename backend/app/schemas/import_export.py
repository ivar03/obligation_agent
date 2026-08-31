"""
Phase 18 Bulk CSV Ingestion & Export Schemas.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class CsvRowValidation(BaseModel):
    row_index: int
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    parsed_data: Optional[Dict[str, Any]] = None


class CsvImportPreviewResponse(BaseModel):
    total_rows: int
    valid_rows_count: int
    invalid_rows_count: int
    validation_results: List[CsvRowValidation]
    detected_duplicates: List[str] = Field(default_factory=list)
    can_commit: bool


class CsvImportCommitRequest(BaseModel):
    rows: List[Dict[str, Any]]
    skip_duplicates: bool = True


class CsvImportCommitResponse(BaseModel):
    imported_count: int
    created_obligation_ids: List[str]
    created_edge_count: int
    errors: List[str] = Field(default_factory=list)
