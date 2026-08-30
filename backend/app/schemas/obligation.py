from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.core.status_machine import ObligationStatus, ObligationType, EdgeType


class FieldConfidence(BaseModel):
    overall: float = Field(default=1.0, ge=0.0, le=1.0)
    owner: float = Field(default=1.0, ge=0.0, le=1.0)
    beneficiary: float = Field(default=1.0, ge=0.0, le=1.0)
    action: float = Field(default=1.0, ge=0.0, le=1.0)
    deadline: float = Field(default=1.0, ge=0.0, le=1.0)
    conditions: float = Field(default=1.0, ge=0.0, le=1.0)
    obligation_type: float = Field(default=1.0, ge=0.0, le=1.0)


class ObligationCandidate(BaseModel):
    owner: str
    beneficiary: str
    action: str
    deadline: Optional[datetime] = None
    conditions: Optional[Any] = None
    obligation_type: ObligationType
    next_action: Optional[str] = None
    source_ref: Optional[str] = None
    confidence: FieldConfidence = Field(default_factory=FieldConfidence)


class ExtractionRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw message or text to extract obligation from")


class ExtractionResponse(BaseModel):
    detected: bool
    obligation: Optional[ObligationCandidate] = None
    reason: Optional[str] = None
    raw_text: Optional[str] = None


class ObligationCreate(BaseModel):
    owner: str = Field(..., min_length=1)
    beneficiary: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    deadline: Optional[datetime] = None
    conditions: Optional[Any] = None
    evidence: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    status: ObligationStatus = Field(default=ObligationStatus.CONFIRMED)
    next_action: Optional[str] = None
    source_ref: Optional[str] = None
    obligation_type: ObligationType
    confidence: Optional[Dict[str, Any]] = None


class ObligationUpdate(BaseModel):
    owner: Optional[str] = None
    beneficiary: Optional[str] = None
    action: Optional[str] = None
    deadline: Optional[datetime] = None
    conditions: Optional[Any] = None
    evidence: Optional[List[Dict[str, Any]]] = None
    next_action: Optional[str] = None
    source_ref: Optional[str] = None
    obligation_type: Optional[ObligationType] = None
    confidence: Optional[Dict[str, Any]] = None


class ObligationStatusUpdate(BaseModel):
    status: ObligationStatus
    reason: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None


class ObligationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner: str
    beneficiary: str
    action: str
    deadline: Optional[datetime] = None
    conditions: Optional[Any] = None
    evidence: Optional[List[Dict[str, Any]]] = None
    status: ObligationStatus
    next_action: Optional[str] = None
    source_ref: Optional[str] = None
    obligation_type: ObligationType
    confidence: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    is_at_risk: bool = False


class ObligationListResponse(BaseModel):
    items: List[ObligationResponse]
    total: int


class DashboardSummaryResponse(BaseModel):
    you_owe_count: int
    others_owe_count: int
    at_risk_count: int
    completed_count: int
    you_owe_obligations: List[ObligationResponse]
    others_owe_obligations: List[ObligationResponse]
    at_risk_obligations: List[ObligationResponse]


class ObligationEdgeCreate(BaseModel):
    from_obligation_id: str
    to_obligation_id: str
    edge_type: EdgeType = Field(default=EdgeType.LINKED)


class ObligationEdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    from_obligation_id: str
    to_obligation_id: str
    edge_type: EdgeType
    created_at: datetime
