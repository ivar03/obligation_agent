export type ObligationStatus =
  | "DETECTED"
  | "CONFIRMED"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "OVERDUE"
  | "CANCELLED"
  | "BLOCKED";

export type ObligationType = "OWED_BY_ME" | "OWED_TO_ME";

export type EdgeType = "DEPENDS_ON" | "LINKED";

export interface FieldConfidence {
  overall: number;
  owner: number;
  beneficiary: number;
  action: number;
  deadline: number;
  conditions: number;
  obligation_type: number;
}

export interface ObligationEvidence {
  type?: string;
  text?: string;
  url?: string;
  recorded_at?: string;
  status_transition?: string;
  [key: string]: unknown;
}

export interface Obligation {
  id: string;
  owner: string;
  beneficiary: string;
  action: string;
  deadline: string | null;
  conditions: string | Record<string, unknown> | null;
  evidence: ObligationEvidence[] | null;
  status: ObligationStatus;
  next_action: string | null;
  source_ref: string | null;
  obligation_type: ObligationType;
  confidence: Record<string, unknown> | FieldConfidence | null;
  created_at: string;
  updated_at: string;
  is_at_risk: boolean;
}

export interface ObligationCandidate {
  owner: string;
  beneficiary: string;
  action: string;
  deadline: string | null;
  conditions: string | Record<string, unknown> | null;
  obligation_type: ObligationType;
  next_action: string | null;
  source_ref: string | null;
  confidence: FieldConfidence;
}

export interface ExtractionRequest {
  text: string;
}

export interface ExtractionResponse {
  detected: boolean;
  obligation: ObligationCandidate | null;
  reason: string | null;
  raw_text: string | null;
}

export interface ObligationCreate {
  owner: string;
  beneficiary: string;
  action: string;
  deadline?: string | null;
  conditions?: string | Record<string, unknown> | null;
  evidence?: ObligationEvidence[];
  status?: ObligationStatus;
  next_action?: string | null;
  source_ref?: string | null;
  obligation_type: ObligationType;
  confidence?: Record<string, unknown> | null;
}

export interface ObligationUpdate {
  owner?: string;
  beneficiary?: string;
  action?: string;
  deadline?: string | null;
  conditions?: string | Record<string, unknown> | null;
  evidence?: ObligationEvidence[];
  next_action?: string | null;
  source_ref?: string | null;
  obligation_type?: ObligationType;
  confidence?: Record<string, unknown> | null;
}

export interface ObligationStatusUpdate {
  status: ObligationStatus;
  reason?: string;
  evidence?: Record<string, unknown>;
}

export interface ObligationListResponse {
  items: Obligation[];
  total: number;
}

export interface DashboardSummaryResponse {
  you_owe_count: number;
  others_owe_count: number;
  at_risk_count: number;
  completed_count: number;
  you_owe_obligations: Obligation[];
  others_owe_obligations: Obligation[];
  at_risk_obligations: Obligation[];
}
