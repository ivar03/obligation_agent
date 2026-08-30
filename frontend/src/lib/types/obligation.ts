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

export type DeadlineType = "EXPLICIT" | "RELATIVE" | "CONDITIONAL" | "UNKNOWN";

export type EvidenceType = "MESSAGE" | "DOCUMENT" | "FILE" | "EVENT" | "MANUAL" | "SYSTEM";

export type CorrelationStatus = "DETECTED" | "SUGGESTED" | "CONFIRMED" | "REJECTED";

export const EventSemanticRole = {
  COMPLETION_SIGNAL: "COMPLETION_SIGNAL",
  COMMITMENT: "COMMITMENT",
  REQUEST: "REQUEST",
  PROGRESS_UPDATE: "PROGRESS_UPDATE",
  NON_COMPLETION_SIGNAL: "NON_COMPLETION_SIGNAL",
  IRRELEVANT: "IRRELEVANT",
} as const;

export type EventSemanticRole = (typeof EventSemanticRole)[keyof typeof EventSemanticRole];

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type ActionType =
  | "START_WORK"
  | "FOLLOW_UP_OWNER"
  | "RESOLVE_DEPENDENCY"
  | "REVIEW_EVIDENCE"
  | "ASSIGN_OWNER"
  | "MONITOR_CONDITION"
  | "REVIEW_DEADLINE"
  | "NO_ACTION";

export interface FieldConfidence {
  overall: number;
  owner: number;
  beneficiary: number;
  action: number;
  deadline: number;
  conditions: number;
  obligation_type: number;
}

export interface MessageContext {
  message?: string;
  sender?: string;
  recipients?: string[];
  participants?: string[];
  previous_messages?: Array<Record<string, unknown>>;
  reference_time?: string;
  current_user?: string;
}

export interface OwnershipResolution {
  owner: string;
  beneficiary: string;
  confidence: number;
  reasoning: string;
  ambiguous: boolean;
  obligation_type: ObligationType;
  suggested_assignees?: string[];
}

export interface DeadlineResolution {
  deadline_type: DeadlineType;
  resolved_deadline?: string | null;
  condition_trigger?: string | null;
  confidence: number;
  reasoning: string;
  ambiguous: boolean;
  raw_expression?: string | null;
}

export interface AmbiguityDetail {
  field: string;
  reason: string;
  confidence: number;
  suggested_action?: string | null;
}

export interface ResolutionResult {
  ownership: OwnershipResolution;
  deadline: DeadlineResolution;
  review_required: boolean;
  ambiguities: AmbiguityDetail[];
  confidence_summary: Record<string, number>;
}

export interface BlockerDetail {
  obligation_id: string;
  owner: string;
  beneficiary?: string;
  action: string;
  status: ObligationStatus;
  reason: string;
}

export interface BlockReason {
  blocked: boolean;
  blocked_by: BlockerDetail[];
  updated_at?: string | null;
}

export interface ObligationEvidence {
  type?: string;
  text?: string;
  url?: string;
  reason?: string;
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
  block_reason?: BlockReason | Record<string, unknown> | null;
  source_ref: string | null;
  obligation_type: ObligationType;
  confidence: Record<string, unknown> | FieldConfidence | null;
  created_at: string;
  updated_at: string;
  is_at_risk: boolean;
  risk_level?: RiskLevel | null;
  risk_score?: number | null;
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
  deadline_type?: DeadlineType | null;
  resolution?: ResolutionResult | null;
}

export interface ExtractionRequest {
  text: string;
  context?: MessageContext | null;
  reference_datetime?: string | null;
  dry_run?: boolean;
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
  blocked_count?: number;
  pending_evidence_count?: number;
  you_owe_obligations: Obligation[];
  others_owe_obligations: Obligation[];
  at_risk_obligations: Obligation[];
}

export interface ObligationEdgeCreate {
  from_obligation_id: string;
  to_obligation_id: string;
  edge_type: EdgeType;
}

export interface ObligationEdge {
  id: string;
  from_obligation_id: string;
  to_obligation_id: string;
  edge_type: EdgeType;
  created_at: string;
}

export interface ObligationGraphResponse {
  obligation: Obligation;
  dependencies: Obligation[];
  dependents: Obligation[];
  linked: Obligation[];
  blockers: BlockerDetail[];
  is_blocked: boolean;
  unblocks_on_completion: Obligation[];
}

// ==========================================
// PHASE 4: EVIDENCE & EVENT CORRELATION TYPES
// ==========================================

export interface ExternalEvent {
  source_type: string;
  source_ref?: string | null;
  sender?: string | null;
  recipients: string[];
  timestamp?: string | null;
  content: string;
  metadata?: Record<string, unknown>;
}

export interface CorrelationMatch {
  obligation_id: string;
  owner: string;
  beneficiary: string;
  action: string;
  status: ObligationStatus;
  correlation_confidence: number;
  confidence_level: "HIGH" | "MEDIUM" | "LOW";
  semantic_role: EventSemanticRole;
  is_completion_candidate: boolean;
  matched_signals: string[];
  unmatched_signals: string[];
  reasoning: string[];
  review_required: boolean;
}

export interface EventAnalysisResponse {
  semantic_role: EventSemanticRole;
  matches: CorrelationMatch[];
  best_match?: CorrelationMatch | null;
  summary: string;
}

export interface EvidenceResponse {
  id: string;
  obligation_id: string;
  evidence_type: EvidenceType;
  source_type: string;
  source_ref?: string | null;
  content: string;
  correlation_status: CorrelationStatus;
  correlation_confidence: number;
  semantic_role: EventSemanticRole;
  reasoning?: string[] | null;
  extra_metadata?: Record<string, unknown> | null;
  actor?: string | null;
  observed_at: string;
  created_at: string;
}

export interface EvidenceListResponse {
  items: EvidenceResponse[];
  total: number;
}

export interface EventIngestionResponse {
  ingested: boolean;
  semantic_role: EventSemanticRole;
  evidence_records: EvidenceResponse[];
  matches: CorrelationMatch[];
  message: string;
}

// ==========================================
// PHASE 5: PROACTIVE RISK & RECOMMENDATION TYPES
// ==========================================

export interface RiskSignal {
  signal_type: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  contribution: number;
  explanation: string;
}

export interface RiskBreakdown {
  deadline_pressure: number;
  dependency_risk: number;
  progress_risk: number;
  ownership_risk: number;
  evidence_risk: number;
}

export interface RiskAssessmentResponse {
  obligation_id: string;
  owner: string;
  beneficiary: string;
  action: string;
  status: ObligationStatus;
  obligation_type: ObligationType;
  deadline?: string | null;
  risk_score: number;
  risk_level: RiskLevel;
  is_at_risk: boolean;
  priority_score: number;
  dependent_count: number;
  reasons: string[];
  signals: RiskSignal[];
  breakdown: RiskBreakdown;
  recommended_action: string;
  action_type: ActionType;
  assessed_at: string;
}

export interface BulkRiskResponse {
  total_at_risk: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  items: RiskAssessmentResponse[];
}

// ==========================================
// PHASE 6: HUMAN-CONTROLLED INTERVENTION TYPES
// ==========================================

export type InterventionType =
  | "FOLLOW_UP_OWNER"
  | "REQUEST_STATUS_UPDATE"
  | "REQUEST_MISSING_DELIVERABLE"
  | "RESOLVE_DEPENDENCY"
  | "REVIEW_EVIDENCE"
  | "ASSIGN_OWNER"
  | "CLARIFY_DEADLINE"
  | "MONITOR_CONDITION"
  | "NO_INTERVENTION";

export type InterventionStatus =
  | "DRAFT"
  | "PENDING_REVIEW"
  | "APPROVED"
  | "SCHEDULED"
  | "READY_TO_EXECUTE"
  | "EXECUTED"
  | "ACKNOWLEDGED"
  | "RESOLVED"
  | "CANCELLED"
  | "EXPIRED";

export type InterventionOutcome =
  | "ACKNOWLEDGED"
  | "PROGRESS_REPORTED"
  | "COMPLETED"
  | "NO_RESPONSE"
  | "NEGATIVE_RESPONSE"
  | "REJECTED"
  | "NOT_NEEDED"
  | "UNKNOWN";

export interface InterventionAuditEntry {
  event: string;
  actor: string;
  timestamp: string;
  details?: Record<string, unknown> | null;
}

export interface Intervention {
  id: string;
  obligation_id: string;
  intervention_type: InterventionType;
  target_owner: string;
  target_beneficiary: string;
  title: string;
  rationale: string;
  message_draft: string;
  approved_message?: string | null;
  context_data?: Record<string, unknown> | null;
  urgency: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  status: InterventionStatus;
  outcome?: InterventionOutcome | null;
  requires_approval: boolean;
  approved_at?: string | null;
  approved_by?: string | null;
  scheduled_for?: string | null;
  executed_at?: string | null;
  execution_reference?: string | null;
  execution_mode: string;
  follow_up_at?: string | null;
  cooldown_until?: string | null;
  chain_depth: number;
  audit_trail: InterventionAuditEntry[];
  created_at: string;
  updated_at: string;
}

export interface InterventionUpdate {
  target_owner?: string;
  target_beneficiary?: string;
  title?: string;
  approved_message?: string;
  scheduled_for?: string | null;
  urgency?: string;
  context_data?: Record<string, unknown>;
}

export interface InterventionApproveRequest {
  approved_by?: string;
  approved_message?: string;
}

export interface InterventionScheduleRequest {
  scheduled_for: string;
  approved_message?: string;
  approved_by?: string;
}

export interface InterventionOutcomeRequest {
  outcome: InterventionOutcome;
  notes?: string;
}

export interface InterventionListResponse {
  items: Intervention[];
  total: number;
}

export interface InterventionQueueResponse {
  pending_review_count: number;
  ready_to_execute_count: number;
  scheduled_count: number;
  total_action_required: number;
  items: Intervention[];
}

// ==========================================
// PHASE 7: CONTINUOUS EVENT INGESTION TYPES
// ==========================================

export interface ProviderInfo {
  name: string;
  version: string;
  capabilities: string[];
  is_connected: boolean;
}

export interface IngestRawEventRequest {
  provider: string;
  payload: Record<string, unknown>;
}

export interface EventSimulateRequest {
  scenario: string;
  sender?: string;
  recipients?: string[];
  content?: string;
  metadata?: Record<string, unknown>;
}

export interface IngestedEvent {
  id: string;
  provider: string;
  source_type: string;
  source_ref?: string | null;
  sender?: string | null;
  recipients?: string[];
  content: string;
  semantic_role: EventSemanticRole;
  processing_status: "PROCESSED" | "DUPLICATE" | "REJECTED" | "NO_MATCH" | string;
  candidate_obligation_ids?: string[];
  correlated_obligation_id?: string | null;
  evidence_id?: string | null;
  correlation_confidence?: number | null;
  match_explanation?: string | null;
  action_taken?: string | null;
  resolved_intervention_id?: string | null;
  raw_payload?: Record<string, unknown> | null;
  received_at: string;
  created_at: string;
}

export interface IngestedEventListResponse {
  items: IngestedEvent[];
  total: number;
}

export interface IngestionResultResponse {
  status: "PROCESSED" | "DUPLICATE" | "REJECTED" | "NO_MATCH" | string;
  event_id: string;
  provider: string;
  semantic_role: EventSemanticRole;
  matches: CorrelationMatch[];
  evidence_records: EvidenceResponse[];
  affected_obligation_ids: string[];
  updated_intervention_ids: string[];
  message: string;
}

