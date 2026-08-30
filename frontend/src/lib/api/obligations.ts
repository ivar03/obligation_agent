import { apiClient } from "./client";
import {
  ExtractionRequest,
  ExtractionResponse,
  Obligation,
  ObligationCreate,
  ObligationUpdate,
  ObligationStatusUpdate,
  ObligationListResponse,
  DashboardSummaryResponse,
  ObligationType,
  ObligationStatus,
} from "../types/obligation";

export const obligationsApi = {
  // Health Check
  checkHealth: async (): Promise<{ status: string; service: string; version: string }> => {
    return apiClient("/api/health");
  },

  // Extraction Pipeline (Human-in-the-loop candidate extraction)
  extractCandidate: async (text: string): Promise<ExtractionResponse> => {
    const payload: ExtractionRequest = { text };
    return apiClient("/api/obligations/extract", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // Create confirmed obligation
  create: async (data: ObligationCreate): Promise<Obligation> => {
    return apiClient("/api/obligations", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  // List obligations with filters
  list: async (params?: {
    obligation_type?: ObligationType;
    status?: ObligationStatus;
    search?: string;
    is_at_risk?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<ObligationListResponse> => {
    return apiClient("/api/obligations", {
      method: "GET",
      params: {
        obligation_type: params?.obligation_type,
        status: params?.status,
        search: params?.search,
        is_at_risk: params?.is_at_risk,
        limit: params?.limit,
        offset: params?.offset,
      },
    });
  },

  // Get single obligation by ID
  getById: async (id: string): Promise<Obligation> => {
    return apiClient(`/api/obligations/${id}`, {
      method: "GET",
    });
  },

  // Update obligation details
  update: async (id: string, data: ObligationUpdate): Promise<Obligation> => {
    return apiClient(`/api/obligations/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  // Controlled status update
  updateStatus: async (
    id: string,
    status: ObligationStatus,
    reason?: string,
    evidence?: Record<string, unknown>
  ): Promise<Obligation> => {
    const payload: ObligationStatusUpdate = { status, reason, evidence };
    return apiClient(`/api/obligations/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  // Delete obligation
  delete: async (id: string): Promise<void> => {
    return apiClient(`/api/obligations/${id}`, {
      method: "DELETE",
    });
  },

  // Dashboard summary metrics
  getDashboardSummary: async (): Promise<DashboardSummaryResponse> => {
    return apiClient("/api/dashboard/summary", {
      method: "GET",
    });
  },
};
