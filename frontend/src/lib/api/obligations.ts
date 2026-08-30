import {
  Obligation,
  ObligationCreate,
  ObligationUpdate,
  ObligationStatusUpdate,
  ObligationListResponse,
  DashboardSummaryResponse,
  ExtractionRequest,
  ExtractionResponse,
  MessageContext,
  ObligationEdgeCreate,
  ObligationEdge,
  ObligationGraphResponse,
  ExternalEvent,
  EventAnalysisResponse,
  EventIngestionResponse,
  EvidenceResponse,
  RiskAssessmentResponse,
  BulkRiskResponse,
  RiskLevel,
  ObligationType,
  ObligationStatus,
  Intervention,
  InterventionUpdate,
  InterventionApproveRequest,
  InterventionScheduleRequest,
  InterventionOutcomeRequest,
  InterventionListResponse,
  InterventionQueueResponse,
  InterventionStatus,
  InterventionType,
  IngestedEvent,
  IngestedEventListResponse,
  IngestionResultResponse,
  EventSimulateRequest,
  ProviderInfo,
  EventSemanticRole,
  IntegrationConnection,
  IntegrationListResponse,
  IntegrationTestResponse,
  OAuthConnectResponse,
  ReconciliationRecord,
  ReconciliationListResponse,
  ReconciliationResolutionRequest,
  IntelligenceOverviewResponse,
  ObligationPredictionResponse,
  SimilarObligationsResponse,
  OwnerPatternMetric,
  DerivedProvenanceInfo,
  HistoricalPatternsResponse,
  PredictionEvaluationMetrics,
  OutcomeSnapshotResponse,
  AdaptiveOverviewResponse,
  AdaptiveFeaturePatternsResponse,
  AdaptiveCalibrationResponse,
  ModelComparisonResponse,
  PredictionHistoryResponse,
  InterventionEffectivenessMetric,
  Workspace,
  WorkspaceMembership,
  AuthResponse,
  RegisterRequest,
  LoginRequest,
  WorkspaceCreateRequest,
  WorkspaceUpdateRequest,
  AddMemberRequest,
  UpdateMemberRoleRequest,
  AuditEvent,
  AuditListResponse,
  AuditVerificationResponse,
  GovernanceSummaryResponse,
} from "../types/obligation";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

let activeWorkspaceId: string | null = null;
let authToken: string | null = null;

if (typeof window !== "undefined") {
  activeWorkspaceId = localStorage.getItem("obligation_active_workspace_id");
  authToken = localStorage.getItem("obligation_auth_token");
}

export function setApiAuth(token: string | null, workspaceId: string | null) {
  authToken = token;
  activeWorkspaceId = workspaceId;
  if (typeof window !== "undefined") {
    if (token) localStorage.setItem("obligation_auth_token", token);
    else localStorage.removeItem("obligation_auth_token");
    if (workspaceId) localStorage.setItem("obligation_active_workspace_id", workspaceId);
    else localStorage.removeItem("obligation_active_workspace_id");
  }
}

export function getActiveWorkspaceId(): string | null {
  return activeWorkspaceId;
}

async function apiClient<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const authHeaders: Record<string, string> = {};
  if (authToken) {
    authHeaders["Authorization"] = `Bearer ${authToken}`;
  }
  if (activeWorkspaceId) {
    authHeaders["X-Workspace-Id"] = activeWorkspaceId;
  }

  const headers = {
    "Content-Type": "application/json",
    ...authHeaders,
    ...options.headers,
  };

  const response = await fetch(url, {
    credentials: "include",
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = "An unexpected error occurred.";
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch {
      errorDetail = response.statusText;
    }
    throw new Error(errorDetail);
  }

  if (response.status === 204) {
    return null as unknown as T;
  }

  return response.json();
}

export const obligationsApi = {
  // Phase 1: Core CRUD & Health
  checkHealth: async (): Promise<{ status: string; version: string }> => {
    return apiClient("/api/health", {
      method: "GET",
    });
  },

  extract: async (
    textOrPayload: string | ExtractionRequest,
    context?: MessageContext,
    dryRun: boolean = false
  ): Promise<ExtractionResponse> => {
    let payload: ExtractionRequest;
    if (typeof textOrPayload === "string") {
      payload = {
        text: textOrPayload,
        context,
        dry_run: dryRun,
      };
    } else {
      payload = textOrPayload;
    }
    return apiClient("/api/obligations/extract", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  extractCandidate: async (
    textOrPayload: string | ExtractionRequest,
    context?: MessageContext | null,
    referenceDatetime?: string | null
  ): Promise<ExtractionResponse> => {
    let payload: ExtractionRequest;
    if (typeof textOrPayload === "string") {
      payload = {
        text: textOrPayload,
        context: context || undefined,
        reference_datetime: referenceDatetime || undefined,
      };
    } else {
      payload = textOrPayload;
    }
    return apiClient("/api/obligations/extract", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getAll: async (params?: {
    owner?: string;
    beneficiary?: string;
    status?: string;
    obligation_type?: string;
    search?: string;
    is_at_risk?: boolean;
    is_blocked?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<ObligationListResponse> => {
    const query = new URLSearchParams();
    if (params?.owner) query.append("owner", params.owner);
    if (params?.beneficiary) query.append("beneficiary", params.beneficiary);
    if (params?.status) query.append("status", params.status);
    if (params?.obligation_type) query.append("obligation_type", params.obligation_type);
    if (params?.search) query.append("search", params.search);
    if (params?.is_at_risk !== undefined) query.append("is_at_risk", String(params.is_at_risk));
    if (params?.is_blocked !== undefined) query.append("is_blocked", String(params.is_blocked));
    if (params?.limit) query.append("limit", String(params.limit));
    if (params?.offset) query.append("offset", String(params.offset));

    const qs = query.toString();
    return apiClient(`/api/obligations${qs ? `?${qs}` : ""}`, {
      method: "GET",
    });
  },

  list: async (params?: {
    owner?: string;
    beneficiary?: string;
    status?: string;
    obligation_type?: string;
    search?: string;
    is_at_risk?: boolean;
    is_blocked?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<ObligationListResponse> => {
    return obligationsApi.getAll(params);
  },

  getById: async (id: string): Promise<Obligation> => {
    return apiClient(`/api/obligations/${id}`, {
      method: "GET",
    });
  },

  create: async (obligation: ObligationCreate): Promise<Obligation> => {
    return apiClient("/api/obligations", {
      method: "POST",
      body: JSON.stringify(obligation),
    });
  },

  update: async (id: string, obligation: ObligationUpdate): Promise<Obligation> => {
    return apiClient(`/api/obligations/${id}`, {
      method: "PUT",
      body: JSON.stringify(obligation),
    });
  },

  updateStatus: async (
    id: string,
    statusOrPayload: ObligationStatus | ObligationStatusUpdate,
    reason?: string,
    evidence?: Record<string, unknown>
  ): Promise<Obligation> => {
    let payload: ObligationStatusUpdate;
    if (typeof statusOrPayload === "string") {
      payload = {
        status: statusOrPayload,
        reason,
        evidence,
      };
    } else {
      payload = statusOrPayload;
    }
    return apiClient(`/api/obligations/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  delete: async (id: string): Promise<void> => {
    return apiClient(`/api/obligations/${id}`, {
      method: "DELETE",
    });
  },

  getDashboardSummary: async (): Promise<DashboardSummaryResponse> => {
    return apiClient("/api/dashboard/summary", {
      method: "GET",
    });
  },

  // Phase 3: Graph & Cascade
  getGraph: async (obligationId: string): Promise<ObligationGraphResponse> => {
    return apiClient(`/api/obligations/${obligationId}/graph`, {
      method: "GET",
    });
  },

  addEdge: async (edge: ObligationEdgeCreate): Promise<ObligationEdge> => {
    return apiClient("/api/obligations/edges", {
      method: "POST",
      body: JSON.stringify(edge),
    });
  },

  createEdge: async (edge: ObligationEdgeCreate): Promise<ObligationEdge> => {
    return obligationsApi.addEdge(edge);
  },

  deleteEdge: async (edgeId: string): Promise<void> => {
    return apiClient(`/api/obligations/edges/${edgeId}`, {
      method: "DELETE",
    });
  },

  // Phase 4: Evidence & Correlation
  analyzeEvent: async (event: ExternalEvent): Promise<EventAnalysisResponse> => {
    return apiClient("/api/events/analyze", {
      method: "POST",
      body: JSON.stringify(event),
    });
  },

  ingestEvent: async (event: ExternalEvent): Promise<EventIngestionResponse> => {
    return apiClient("/api/events", {
      method: "POST",
      body: JSON.stringify(event),
    });
  },

  getEvidence: async (obligationId: string): Promise<EvidenceResponse[]> => {
    return apiClient(`/api/obligations/${obligationId}/evidence`, {
      method: "GET",
    });
  },

  confirmEvidence: async (
    obligationId: string,
    evidenceId: string,
    notes?: string
  ): Promise<Obligation> => {
    return apiClient(`/api/obligations/${obligationId}/evidence/${evidenceId}/confirm`, {
      method: "POST",
      body: JSON.stringify({ notes }),
    });
  },

  rejectEvidence: async (
    obligationId: string,
    evidenceId: string
  ): Promise<EvidenceResponse> => {
    return apiClient(`/api/obligations/${obligationId}/evidence/${evidenceId}/reject`, {
      method: "POST",
    });
  },

  // Phase 5: Risk Engine
  getRiskAssessment: async (obligationId: string): Promise<RiskAssessmentResponse> => {
    return apiClient(`/api/obligations/${obligationId}/risk`, {
      method: "GET",
    });
  },

  getBulkRisks: async (params?: {
    risk_level?: RiskLevel;
    owner?: string;
    obligation_type?: ObligationType;
    status?: ObligationStatus;
    limit?: number;
    offset?: number;
  }): Promise<BulkRiskResponse> => {
    const query = new URLSearchParams();
    if (params?.risk_level) query.append("risk_level", params.risk_level);
    if (params?.owner) query.append("owner", params.owner);
    if (params?.obligation_type) query.append("obligation_type", params.obligation_type);
    if (params?.status) query.append("status", params.status);
    if (params?.limit) query.append("limit", String(params.limit));
    if (params?.offset) query.append("offset", String(params.offset));

    const qs = query.toString();
    return apiClient(`/api/risk${qs ? `?${qs}` : ""}`, {
      method: "GET",
    });
  },
};

// ==========================================
// PHASE 6: INTERVENTIONS API
// ==========================================

export const interventionsApi = {
  plan: async (obligationId: string, force: boolean = false): Promise<Intervention> => {
    return apiClient("/api/interventions/plan", {
      method: "POST",
      body: JSON.stringify({ obligation_id: obligationId, force }),
    });
  },

  list: async (params?: {
    status?: InterventionStatus;
    intervention_type?: InterventionType;
    obligation_id?: string;
    urgency?: string;
    limit?: number;
    offset?: number;
  }): Promise<InterventionListResponse> => {
    const query = new URLSearchParams();
    if (params?.status) query.append("status", params.status);
    if (params?.intervention_type) query.append("intervention_type", params.intervention_type);
    if (params?.obligation_id) query.append("obligation_id", params.obligation_id);
    if (params?.urgency) query.append("urgency", params.urgency);
    if (params?.limit) query.append("limit", String(params.limit));
    if (params?.offset) query.append("offset", String(params.offset));

    const qs = query.toString();
    return apiClient(`/api/interventions${qs ? `?${qs}` : ""}`, {
      method: "GET",
    });
  },

  getQueue: async (limit: number = 50): Promise<InterventionQueueResponse> => {
    return apiClient(`/api/interventions/queue?limit=${limit}`, {
      method: "GET",
    });
  },

  getById: async (id: string): Promise<Intervention> => {
    return apiClient(`/api/interventions/${id}`, {
      method: "GET",
    });
  },

  update: async (id: string, payload: InterventionUpdate): Promise<Intervention> => {
    return apiClient(`/api/interventions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  approve: async (id: string, payload?: InterventionApproveRequest): Promise<Intervention> => {
    return apiClient(`/api/interventions/${id}/approve`, {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
  },

  schedule: async (id: string, payload: InterventionScheduleRequest): Promise<Intervention> => {
    return apiClient(`/api/interventions/${id}/schedule`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  execute: async (id: string): Promise<Intervention> => {
    return apiClient(`/api/interventions/${id}/execute`, {
      method: "POST",
    });
  },

  recordOutcome: async (id: string, payload: InterventionOutcomeRequest): Promise<Intervention> => {
    return apiClient(`/api/interventions/${id}/outcome`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  cancel: async (id: string, reason?: string): Promise<Intervention> => {
    const qs = reason ? `?reason=${encodeURIComponent(reason)}` : "";
    return apiClient(`/api/interventions/${id}/cancel${qs}`, {
      method: "POST",
    });
  },

  resolve: async (id: string, reason?: string): Promise<Intervention> => {
    const qs = reason ? `?reason=${encodeURIComponent(reason)}` : "";
    return apiClient(`/api/interventions/${id}/resolve${qs}`, {
      method: "POST",
    });
  },
};

// ==========================================
// PHASE 7: CONTINUOUS EVENT INGESTION API
// ==========================================

export const eventsApi = {
  ingestRaw: async (provider: string, payload: Record<string, unknown>): Promise<IngestionResultResponse> => {
    return apiClient("/api/events/ingest", {
      method: "POST",
      body: JSON.stringify({ provider, payload }),
    });
  },

  simulate: async (payload: EventSimulateRequest): Promise<IngestionResultResponse> => {
    return apiClient("/api/events/simulate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  list: async (params?: {
    provider?: string;
    semantic_role?: EventSemanticRole;
    processing_status?: string;
    source_ref?: string;
    limit?: number;
    offset?: number;
  }): Promise<IngestedEventListResponse> => {
    const query = new URLSearchParams();
    if (params?.provider) query.append("provider", params.provider);
    if (params?.semantic_role) query.append("semantic_role", params.semantic_role);
    if (params?.processing_status) query.append("processing_status", params.processing_status);
    if (params?.source_ref) query.append("source_ref", params.source_ref);
    if (params?.limit) query.append("limit", String(params.limit));
    if (params?.offset) query.append("offset", String(params.offset));

    const qs = query.toString();
    return apiClient(`/api/events${qs ? `?${qs}` : ""}`, {
      method: "GET",
    });
  },

  getById: async (id: string): Promise<IngestedEvent> => {
    return apiClient(`/api/events/${id}`, {
      method: "GET",
    });
  },

  listProviders: async (): Promise<ProviderInfo[]> => {
    return apiClient("/api/events/providers", {
      method: "GET",
    });
  },

  analyze: async (event: ExternalEvent): Promise<EventAnalysisResponse> => {
    return apiClient("/api/events/analyze", {
      method: "POST",
      body: JSON.stringify(event),
    });
  },
};

// ==========================================
// PHASE 8: INTEGRATION SERVICE CLIENT
// ==========================================

export const integrationsApi = {
  list: async (): Promise<IntegrationListResponse> => {
    return apiClient("/api/integrations", {
      method: "GET",
    });
  },

  get: async (provider: string): Promise<IntegrationConnection> => {
    return apiClient(`/api/integrations/${provider}`, {
      method: "GET",
    });
  },

  connect: async (provider: string, redirectUri?: string): Promise<OAuthConnectResponse> => {
    const qs = redirectUri ? `?redirect_uri=${encodeURIComponent(redirectUri)}` : "";
    return apiClient(`/api/integrations/${provider}/connect${qs}`, {
      method: "GET",
    });
  },

  test: async (provider: string): Promise<IntegrationTestResponse> => {
    return apiClient(`/api/integrations/${provider}/test`, {
      method: "POST",
    });
  },

  disconnect: async (provider: string): Promise<IntegrationConnection> => {
    return apiClient(`/api/integrations/${provider}/disconnect`, {
      method: "POST",
    });
  },
};

// ==========================================
// PHASE 11: RECONCILIATION API CLIENT
// ==========================================

export const reconciliationApi = {
  list: async (params?: {
    status?: string;
    obligation_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<ReconciliationListResponse> => {
    const query = new URLSearchParams();
    if (params?.status && params.status !== "ALL") query.append("status", params.status);
    if (params?.obligation_id) query.append("obligation_id", params.obligation_id);
    if (params?.limit) query.append("limit", params.limit.toString());
    if (params?.offset) query.append("offset", params.offset.toString());
    const qs = query.toString() ? `?${query.toString()}` : "";
    return apiClient(`/api/reconciliation${qs}`, {
      method: "GET",
    });
  },

  getById: async (id: string): Promise<ReconciliationRecord> => {
    return apiClient(`/api/reconciliation/${id}`, {
      method: "GET",
    });
  },

  getByObligationId: async (obligationId: string): Promise<ReconciliationRecord | null> => {
    return apiClient(`/api/obligations/${obligationId}/reconciliation`, {
      method: "GET",
    });
  },

  resolve: async (
    id: string,
    payload: ReconciliationResolutionRequest
  ): Promise<ReconciliationRecord> => {
    return apiClient(`/api/reconciliation/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  dismiss: async (
    id: string,
    payload?: { reason?: string; operator?: string }
  ): Promise<ReconciliationRecord> => {
    return apiClient(`/api/reconciliation/${id}/dismiss`, {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
  },
};

// ==========================================
// PHASE 12: INTELLIGENCE & PREDICTIONS API
// ==========================================

export const intelligenceApi = {
  getOverview: async (): Promise<IntelligenceOverviewResponse> => {
    return apiClient("/api/intelligence/overview", {
      method: "GET",
    });
  },

  getDossier: async (
    obligationId: string
  ): Promise<{
    prediction: ObligationPredictionResponse;
    similar_obligations: SimilarObligationsResponse;
    owner_context?: OwnerPatternMetric | null;
    derived_provenance: DerivedProvenanceInfo;
  }> => {
    return apiClient(`/api/intelligence/obligations/${obligationId}`, {
      method: "GET",
    });
  },

  getPrediction: async (
    obligationId: string
  ): Promise<ObligationPredictionResponse> => {
    return apiClient(`/api/intelligence/obligations/${obligationId}/prediction`, {
      method: "GET",
    });
  },

  getSimilar: async (
    obligationId: string,
    limit: number = 6
  ): Promise<SimilarObligationsResponse> => {
    return apiClient(
      `/api/intelligence/obligations/${obligationId}/similar?limit=${limit}`,
      {
        method: "GET",
      }
    );
  },

  getPatterns: async (): Promise<HistoricalPatternsResponse> => {
    return apiClient("/api/intelligence/patterns", {
      method: "GET",
    });
  },

  getOwners: async (): Promise<OwnerPatternMetric[]> => {
    return apiClient("/api/intelligence/owners", {
      method: "GET",
    });
  },

  getEvaluation: async (
    modelVersion: string = "predictive-v1"
  ): Promise<PredictionEvaluationMetrics> => {
    return apiClient(
      `/api/intelligence/evaluation?model_version=${encodeURIComponent(
        modelVersion
      )}`,
      {
        method: "GET",
      }
    );
  },

  getHistory: async (
    obligationId: string
  ): Promise<OutcomeSnapshotResponse[]> => {
    return apiClient(`/api/intelligence/history/${obligationId}`, {
      method: "GET",
    });
  },

  getAdaptiveOverview: async (): Promise<AdaptiveOverviewResponse> => {
    return apiClient("/api/intelligence/adaptive/overview", {
      method: "GET",
    });
  },

  getAdaptiveFeatures: async (): Promise<AdaptiveFeaturePatternsResponse> => {
    return apiClient("/api/intelligence/adaptive/features", {
      method: "GET",
    });
  },

  getAdaptiveCalibration: async (
    modelVersion?: string
  ): Promise<AdaptiveCalibrationResponse> => {
    const query = modelVersion
      ? `?model_version=${encodeURIComponent(modelVersion)}`
      : "";
    return apiClient(`/api/intelligence/adaptive/calibration${query}`, {
      method: "GET",
    });
  },

  compareModels: async (
    obligationId: string
  ): Promise<ModelComparisonResponse> => {
    return apiClient(`/api/intelligence/compare/${obligationId}`, {
      method: "GET",
    });
  },

  getPredictionHistory: async (
    obligationId: string
  ): Promise<PredictionHistoryResponse> => {
    return apiClient(
      `/api/intelligence/obligations/${obligationId}/prediction-history`,
      {
        method: "GET",
      }
    );
  },

  getInterventionEffectiveness: async (): Promise<InterventionEffectivenessMetric> => {
    return apiClient("/api/intelligence/intervention-effectiveness", {
      method: "GET",
    });
  },
};

export const authApi = {
  register: async (payload: RegisterRequest): Promise<AuthResponse> => {
    return apiClient("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  login: async (payload: LoginRequest): Promise<AuthResponse> => {
    return apiClient("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  logout: async (): Promise<{ message: string }> => {
    return apiClient("/api/auth/logout", {
      method: "POST",
    });
  },

  getMe: async (): Promise<AuthResponse> => {
    return apiClient("/api/auth/me", {
      method: "GET",
    });
  },
};

export const workspacesApi = {
  list: async (): Promise<Workspace[]> => {
    return apiClient("/api/workspaces", {
      method: "GET",
    });
  },

  create: async (payload: WorkspaceCreateRequest): Promise<Workspace> => {
    return apiClient("/api/workspaces", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  get: async (workspaceId: string): Promise<Workspace> => {
    return apiClient(`/api/workspaces/${workspaceId}`, {
      method: "GET",
    });
  },

  update: async (workspaceId: string, payload: WorkspaceUpdateRequest): Promise<Workspace> => {
    return apiClient(`/api/workspaces/${workspaceId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  listMembers: async (workspaceId: string): Promise<WorkspaceMembership[]> => {
    return apiClient(`/api/workspaces/${workspaceId}/members`, {
      method: "GET",
    });
  },

  addMember: async (workspaceId: string, payload: AddMemberRequest): Promise<WorkspaceMembership> => {
    return apiClient(`/api/workspaces/${workspaceId}/members`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateMemberRole: async (
    workspaceId: string,
    memberId: string,
    payload: UpdateMemberRoleRequest
  ): Promise<WorkspaceMembership> => {
    return apiClient(`/api/workspaces/${workspaceId}/members/${memberId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  removeMember: async (workspaceId: string, memberId: string): Promise<void> => {
    return apiClient(`/api/workspaces/${workspaceId}/members/${memberId}`, {
      method: "DELETE",
    });
  },
};

export const auditApi = {
  list: async (params?: {
    action?: string;
    actor_user_id?: string;
    entity_type?: string;
    entity_id?: string;
    severity?: string;
    result?: string;
    request_id?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<AuditListResponse> => {
    const query = new URLSearchParams();
    if (params?.action) query.append("action", params.action);
    if (params?.actor_user_id) query.append("actor_user_id", params.actor_user_id);
    if (params?.entity_type) query.append("entity_type", params.entity_type);
    if (params?.entity_id) query.append("entity_id", params.entity_id);
    if (params?.severity) query.append("severity", params.severity);
    if (params?.result) query.append("result", params.result);
    if (params?.request_id) query.append("request_id", params.request_id);
    if (params?.date_from) query.append("date_from", params.date_from);
    if (params?.date_to) query.append("date_to", params.date_to);
    if (params?.limit) query.append("limit", String(params.limit));
    if (params?.offset) query.append("offset", String(params.offset));

    const qs = query.toString();
    return apiClient(`/api/audit${qs ? `?${qs}` : ""}`, {
      method: "GET",
    });
  },

  getSummary: async (): Promise<GovernanceSummaryResponse> => {
    return apiClient("/api/audit/summary", {
      method: "GET",
    });
  },

  verify: async (): Promise<AuditVerificationResponse> => {
    return apiClient("/api/audit/verify", {
      method: "GET",
    });
  },

  listSecurityEvents: async (params?: { limit?: number; offset?: number }): Promise<AuditListResponse> => {
    const query = new URLSearchParams();
    if (params?.limit) query.append("limit", String(params.limit));
    if (params?.offset) query.append("offset", String(params.offset));
    const qs = query.toString();
    return apiClient(`/api/audit/security${qs ? `?${qs}` : ""}`, {
      method: "GET",
    });
  },

  getEntityHistory: async (entityType: string, entityId: string): Promise<AuditEvent[]> => {
    return apiClient(`/api/audit/entity/${entityType}/${entityId}`, {
      method: "GET",
    });
  },

  getById: async (auditId: string): Promise<AuditEvent> => {
    return apiClient(`/api/audit/${auditId}`, {
      method: "GET",
    });
  },

  getExportUrl: (format: "json" | "csv", params?: { action?: string; entity_type?: string; severity?: string }): string => {
    const query = new URLSearchParams();
    query.append("format", format);
    if (params?.action) query.append("action", params.action);
    if (params?.entity_type) query.append("entity_type", params.entity_type);
    if (params?.severity) query.append("severity", params.severity);
    return `/api/audit/export?${query.toString()}`;
  },
};



