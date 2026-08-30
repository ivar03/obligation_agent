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
} from "../types/obligation";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

async function apiClient<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  const response = await fetch(url, {
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
