from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class IntegrationConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    external_account_id: Optional[str] = None
    external_account_name: Optional[str] = None
    status: str  # CONNECTED, DISCONNECTED, ERROR
    scopes: Optional[List[str]] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    connection_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class IntegrationListResponse(BaseModel):
    connections: List[IntegrationConnectionResponse] = Field(default_factory=list)
    registered_providers: List[Dict[str, Any]] = Field(default_factory=list)


class IntegrationTestResponse(BaseModel):
    provider: str
    success: bool
    status: str
    message: str
    account_name: Optional[str] = None
    tested_at: datetime


class OAuthConnectResponse(BaseModel):
    provider: str
    authorization_url: str
    state: str
    message: str


class SlackWebhookChallengeResponse(BaseModel):
    challenge: str
