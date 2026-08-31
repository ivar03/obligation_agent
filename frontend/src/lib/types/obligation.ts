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
  | "PREPARE_FOR_MEETING"
  | "FOLLOW_UP_AFTER_MEETING"
  | "REVIEW_RESCHEDULED_COMMITMENT"
  | "REVIEW_CANCELLED_MEETING"
  | "REVIEW_CONFLICTING_EVIDENCE"
  | "CONFIRM_COMPLETION_EVIDENCE"
  | "REVIEW_STALE_SIGNAL"
  | "KEEP_ACTIVE"
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

// ==========================================
// PHASE 8: INTEGRATION & CONNECTION TYPES
// ==========================================

export interface IntegrationConnection {
  id: string;
  provider: string;
  external_account_id?: string | null;
  external_account_name?: string | null;
  status: "CONNECTED" | "DISCONNECTED" | "ERROR" | string;
  scopes?: string[];
  capabilities: string[];
  connection_metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface IntegrationListResponse {
  connections: IntegrationConnection[];
  registered_providers: ProviderInfo[];
}

export interface IntegrationTestResponse {
  provider: string;
  success: boolean;
  status: string;
  message: string;
  account_name?: string | null;
  tested_at: string;
}

export interface OAuthConnectResponse {
  provider: string;
  authorization_url: string;
  state: string;
  message: string;
}

// ==========================================
// PHASE 11: CROSS-PROVIDER RECONCILIATION TYPES
// ==========================================

export type ReconciliationStatus =
  | "CONSISTENT"
  | "CONFLICTING"
  | "AMBIGUOUS"
  | "RESOLVED_SUPPORTING"
  | "RESOLVED_CONFLICTING"
  | "DISMISSED";

export type ReconciliationResolutionAction =
  | "CONFIRM_COMPLETION"
  | "CONFIRM_NOT_COMPLETED"
  | "DISMISS_CONTRADICTION"
  | "MARK_AS_STALE"
  | "KEEP_OBLIGATION_ACTIVE"
  | "REOPEN_OBLIGATION";

export interface EvidenceProvenanceDetail {
  evidence_id: string;
  source_type: string;
  source_ref?: string | null;
  provider: string;
  actor?: string | null;
  recipients?: string[];
  semantic_role: EventSemanticRole;
  correlation_confidence: number;
  content: string;
  observed_at: string;
  is_supporting: boolean;
  is_conflicting: boolean;
  reasoning?: string | null;
}

export interface ReconciliationRecord {
  id: string;
  obligation_id: string;
  status: ReconciliationStatus;
  confidence: number;
  consistency_score: number;
  contradiction_score: number;
  supporting_evidence_ids: string[];
  conflicting_evidence_ids: string[];
  supporting_event_ids: string[];
  conflicting_event_ids: string[];
  explanation: string[];
  recommended_action?: string | null;
  resolution?: {
    action: string;
    operator: string;
    notes?: string;
    previous_obligation_status?: string;
    resulting_obligation_status?: string;
    timestamp?: string;
    selected_evidence_id?: string | null;
    reason?: string;
  } | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;

  // Enriched fields
  evidence_timeline?: EvidenceProvenanceDetail[];
  obligation_action?: string;
  obligation_owner?: string;
  obligation_beneficiary?: string;
  obligation_status?: ObligationStatus;
}

export interface ReconciliationListResponse {
  items: ReconciliationRecord[];
  total: number;
  conflicting_count: number;
  consistent_count: number;
  ambiguous_count: number;
  resolved_count: number;
}

export interface ReconciliationResolutionRequest {
  action: ReconciliationResolutionAction;
  notes?: string;
  operator?: string;
  selected_evidence_id?: string;
}

// =============================================================================
// PHASE 12: PREDICTIVE PATTERN LEARNING & INTELLIGENCE TYPES
// =============================================================================

export type ObligationOutcomeType =
  | "COMPLETED_ON_TIME"
  | "COMPLETED_LATE"
  | "OVERDUE"
  | "BLOCKED"
  | "CANCELLED"
  | "ABANDONED"
  | "COMPLETED_AFTER_INTERVENTION"
  | "COMPLETED_AFTER_FOLLOW_UP"
  | "COMPLETED_AFTER_DEPENDENCY_RESOLUTION"
  | "CONFLICTED_COMPLETION"
  | "UNKNOWN";

export type PredictiveActionType =
  | "EARLY_FOLLOW_UP"
  | "PREPARE_EVIDENCE_REVIEW"
  | "RESOLVE_DEPENDENCY"
  | "CLARIFY_OWNER"
  | "CLARIFY_DEADLINE"
  | "MONITOR_PROGRESS"
  | "NO_PREVENTATIVE_ACTION";

export interface PredictionReasonItem {
  signal: string;
  impact: number;
  explanation: string;
}

export interface DerivedProvenanceInfo {
  current_risk_evaluated: boolean;
  historical_outcomes_count: number;
  similar_obligations_count: number;
  dependency_history_count: number;
  intervention_history_count: number;
}

export interface ObligationPredictionResponse {
  obligation_id: string;
  action?: string | null;
  owner?: string | null;
  beneficiary?: string | null;
  status?: ObligationStatus | null;
  deadline?: string | null;
  model_version: string;
  failure_probability: number;
  completion_probability: number;
  expected_delay_hours: number;
  intervention_likelihood: number;
  blockage_likelihood: number;
  confidence: number;
  reasons: PredictionReasonItem[];
  preventative_recommendation?: string | null;
  recommended_action_type?: string | null;
  derived_from: DerivedProvenanceInfo;
  current_risk_score?: number | null;
  current_risk_level?: RiskLevel | null;
  predicted_at: string;
}

export interface SimilarObligationItem {
  obligation_id: string;
  action: string;
  owner: string;
  beneficiary: string;
  status: string;
  outcome_type: string;
  delay_hours: number;
  similarity_score: number;
  shared_features: string[];
  completed_at?: string | null;
}

export interface SimilarObligationsResponse {
  obligation_id: string;
  items: SimilarObligationItem[];
  total_similar_count: number;
  historical_summary: string;
}

export interface OwnerPatternMetric {
  owner: string;
  total_obligations: number;
  completed_count: number;
  on_time_count: number;
  late_count: number;
  overdue_count: number;
  blocked_count: number;
  on_time_rate: number;
  late_rate: number;
  avg_delay_hours: number;
  median_delay_hours: number;
  intervention_response_rate: number;
  blocker_frequency: number;
  insights: string[];
}

export interface HistoricalPatternsResponse {
  total_historical_snapshots: number;
  completion_rate: number;
  on_time_completion_rate: number;
  avg_delay_hours: number;
  median_delay_hours: number;
  dependency_bottleneck_rate: number;
  intervention_success_rate: number;
  frequent_blockers: Array<Record<string, unknown>>;
  delay_distribution: Record<string, number>;
  owner_metrics: OwnerPatternMetric[];
}

export interface PredictionEvaluationMetrics {
  total_predictions_evaluated: number;
  status: "EVALUATED" | "INSUFFICIENT_HISTORY";
  mean_absolute_error_hours?: number | null;
  brier_score?: number | null;
  calibration_error?: number | null;
  high_risk_precision?: number | null;
  overdue_recall?: number | null;
  accuracy?: number | null;
  evaluated_at: string;
  message: string;
}

export interface IntelligenceOverviewResponse {
  active_obligations_evaluated: number;
  high_predicted_failure_count: number;
  likely_to_miss_deadline_count: number;
  likely_to_require_intervention_count: number;
  high_blockage_risk_count: number;
  predictions: ObligationPredictionResponse[];
  evaluation_summary: PredictionEvaluationMetrics;
  model_version: string;
}

export interface OutcomeSnapshotResponse {
  id: string;
  obligation_id: string;
  snapshot_time: string;
  status: string;
  outcome_type: string;
  owner: string;
  beneficiary: string;
  action: string;
  deadline?: string | null;
  completed_at?: string | null;
  delay_hours: number;
  risk_score: number;
  risk_level: string;
  dependency_count: number;
  blocker_count: number;
  evidence_count: number;
  intervention_count: number;
  intervention_required: boolean;
  intervention_successful: boolean;
  reconciliation_conflict_occurred: boolean;
  relevant_event_signals?: unknown[] | null;
  created_at: string;
}

// ==============================================================================
// PHASE 13: ADAPTIVE PREDICTION, CALIBRATION & INTELLIGENCE FEEDBACK
// ==============================================================================

export type CalibrationStatus =
  | "INSUFFICIENT_HISTORY"
  | "LOW_SAMPLE"
  | "CALIBRATION_AVAILABLE";

export type FeatureDirection =
  | "INCREASES_RISK"
  | "DECREASES_RISK"
  | "NEUTRAL";

export interface FeatureAttributionItem {
  feature: string;
  raw_value: number;
  normalized_value: number;
  contribution: number;
  direction: "INCREASES_RISK" | "DECREASES_RISK" | "NEUTRAL" | string;
  explanation: string;
}

export interface PredictionFeedbackResponse {
  id: string;
  prediction_snapshot_id: string;
  obligation_id: string;
  prediction_provider: string;
  model_version: string;
  predicted_failure_probability: number;
  predicted_completion_probability: number;
  predicted_expected_delay_hours: number;
  predicted_intervention_likelihood: number;
  predicted_confidence: number;
  feature_attributions?: Record<string, unknown>[] | null;
  observed_outcome: string;
  observed_delay_hours: number;
  absolute_delay_error: number;
  probability_error: number;
  was_high_risk_prediction_correct?: boolean | null;
  intervention_recommended: boolean;
  intervention_taken: boolean;
  intervention_effective?: boolean | null;
  created_at: string;
}

export interface FeatureEffectivenessItem {
  feature: string;
  observation_count: number;
  average_contribution: number;
  predictive_direction: string;
  outcome_association: number;
  reliability_score: number;
  historical_usefulness: string;
  confidence: number;
}

export interface AdaptiveFeaturePatternsResponse {
  total_feedback_evaluated: number;
  learned_weights: Record<string, number>;
  features: FeatureEffectivenessItem[];
}

export interface AdaptiveCalibrationResponse {
  status: CalibrationStatus | string;
  total_evaluations: number;
  minimum_required: number;
  brier_score?: number | null;
  calibration_error?: number | null;
  mean_absolute_delay_error?: number | null;
  high_risk_precision?: number | null;
  high_risk_recall?: number | null;
  false_positive_rate?: number | null;
  false_negative_rate?: number | null;
  evaluated_at: string;
  message: string;
}

export interface ModelComparisonResponse {
  obligation_id: string;
  action?: string | null;
  owner?: string | null;
  predictive_v1: ObligationPredictionResponse;
  adaptive_v1: ObligationPredictionResponse;
  probability_variance: number;
  delay_variance_hours: number;
  adjustment_reasons: string[];
  recommended_provider: string;
}

export interface PredictionHistoryItem {
  prediction_id: string;
  model_version: string;
  predicted_at: string;
  failure_probability: number;
  expected_delay_hours: number;
  confidence: number;
  top_signals: string[];
  observed_outcome?: string | null;
  observed_delay_hours?: number | null;
  prediction_error?: number | null;
}

export interface PredictionHistoryResponse {
  obligation_id: string;
  action?: string | null;
  history: PredictionHistoryItem[];
}

export interface InterventionEffectivenessMetric {
  total_interventions_recommended: number;
  interventions_executed: number;
  completed_after_intervention: number;
  completed_without_intervention: number;
  observed_completion_rate_with_intervention: number;
  observed_completion_rate_without_intervention: number;
  sample_size_status: string;
  insights: string[];
}

export interface AdaptiveOverviewResponse {
  active_evaluations: number;
  calibration_status: string;
  model_comparison_summary: Record<string, unknown>;
  top_effective_features: FeatureEffectivenessItem[];
  intervention_efficacy: InterventionEffectivenessMetric;
  calibration_metrics: AdaptiveCalibrationResponse;
}

// ==============================================================================
// PHASE 14: IDENTITY, WORKSPACE, AUTHENTICATION & AUTHORIZATION TYPES
// ==============================================================================

export type WorkspaceRole = "OWNER" | "ADMIN" | "MEMBER" | "VIEWER";

export interface User {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface WorkspaceMembership {
  id: string;
  user_id: string;
  workspace_id: string;
  email?: string | null;
  display_name?: string | null;
  role: WorkspaceRole;
  joined_at?: string | null;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  role?: WorkspaceRole | string;
  created_at: string;
}

export interface AuthResponse {
  user: User;
  workspaces: Workspace[];
  active_workspace_id: string;
  token?: string | null;
  message?: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  display_name: string;
  workspace_name?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface WorkspaceCreateRequest {
  name: string;
  slug?: string;
}

export interface WorkspaceUpdateRequest {
  name?: string;
  slug?: string;
}

export interface AddMemberRequest {
  email: string;
  role: WorkspaceRole;
}

export interface UpdateMemberRoleRequest {
  role: WorkspaceRole;
}

// ==============================================================================
// PHASE 15: ENTERPRISE AUDIT, GOVERNANCE & COMPLIANCE
// ==============================================================================

export type AuditSeverity = "INFO" | "WARNING" | "ERROR" | "CRITICAL";
export type AuditResult = "SUCCESS" | "DENIED" | "FAILED" | "VIOLATION";
export type AuditSource = "API" | "WEBHOOK" | "SYSTEM_WORKER" | "INTEGRATION_SYNC";

export interface AuditEvent {
  id: string;
  workspace_id: string;
  actor_user_id?: string | null;
  actor_name?: string | null;
  actor_email?: string | null;
  actor_role?: string | null;
  action: string;
  entity_type?: string | null;
  entity_id?: string | null;
  timestamp: string;
  request_id?: string | null;
  source: string;
  ip_address?: string | null;
  user_agent?: string | null;
  before_state?: Record<string, unknown> | null;
  after_state?: Record<string, unknown> | null;
  audit_metadata?: Record<string, unknown> | null;
  reason?: string | null;
  severity: AuditSeverity | string;
  result: AuditResult | string;
  previous_event_hash?: string | null;
  event_hash: string;
}

export interface AuditListResponse {
  items: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditVerificationResponse {
  workspace_id: string;
  chain_valid: boolean;
  status: string;
  verified_event_count: number;
  broken_at_event_id?: string | null;
  expected_hash?: string | null;
  actual_hash?: string | null;
  verified_at: string;
  message: string;
}

export interface TopActorMetric {
  actor_user_id?: string | null;
  actor_name: string;
  actor_email?: string | null;
  mutation_count: number;
}

export interface EntityTypeMetric {
  entity_type: string;
  mutation_count: number;
}

export interface GovernanceSummaryResponse {
  workspace_id: string;
  total_audit_events: number;
  events_today: number;
  mutations_today: number;
  security_events_count: number;
  permission_denials_count: number;
  failed_logins_count: number;
  human_actions_count: number;
  system_events_count: number;
  interventions_approved_count: number;
  interventions_executed_count: number;
  evidence_confirmations_count: number;
  reconciliation_decisions_count: number;
  top_actors: TopActorMetric[];
  most_modified_entities: EntityTypeMetric[];
  recent_security_events: AuditEvent[];
  chain_integrity_status: string;
  evaluated_at: string;
}

// ==============================================================================
// PHASE 14: ROOT-CAUSE ANALYSIS, IMPACT & RESOLUTION PLANNING TYPES
// ==============================================================================

export type CausalFactorType =
  | "DIRECT_CAUSE"
  | "UPSTREAM_CAUSE"
  | "CONTRIBUTING_FACTOR"
  | "UNCERTAINTY";

export type ResolutionStrategyType =
  | "RESOLVE_ROOT_BLOCKER"
  | "FOLLOW_UP_ROOT_OWNER"
  | "REQUEST_MISSING_EVIDENCE"
  | "ASSIGN_OWNER"
  | "CLARIFY_DEADLINE"
  | "REVIEW_CONFLICTING_EVIDENCE"
  | "WAIT_FOR_CONDITION"
  | "REVIEW_DEPENDENCY"
  | "NO_ACTION";

export type SimulationActionType =
  | "COMPLETE_OBLIGATION"
  | "RESOLVE_BLOCKER"
  | "ASSIGN_OWNER"
  | "REMOVE_DEPENDENCY"
  | "CONFIRM_EVIDENCE";

export type ConcentrationType =
  | "BOTTLENECK"
  | "HIGH_IMPACT_OWNER"
  | "CRITICAL_PREREQUISITE"
  | "RISK_CONCENTRATION";

export interface CausalFactorItem {
  factor_type: CausalFactorType | string;
  description: string;
  target_obligation_id?: string | null;
  target_owner?: string | null;
  target_action?: string | null;
  confidence: number;
  evidence_refs?: string[];
  event_refs?: string[];
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
}

export interface RootCauseAnalysisResponse {
  obligation_id: string;
  action?: string | null;
  owner?: string | null;
  status?: string | null;
  overall_explanation: string;
  primary_root_cause: string;
  root_cause_type: CausalFactorType | string;
  confidence: number;
  confidence_level: "HIGH" | "MEDIUM" | "LOW" | string;
  direct_causes: CausalFactorItem[];
  upstream_causes: CausalFactorItem[];
  contributing_factors: CausalFactorItem[];
  uncertainties: CausalFactorItem[];
  affected_obligations: Record<string, unknown>[];
  dependency_path: string[];
  evidence_refs: string[];
  event_refs: string[];
  recommended_resolution?: string | null;
  evaluated_at: string;
}

export interface ImpactAnalysisResponse {
  obligation_id: string;
  action?: string | null;
  owner?: string | null;
  status?: string | null;
  direct_dependents_count: number;
  total_downstream_dependents_count: number;
  maximum_dependency_depth: number;
  critical_path_length: number;
  affected_owners: string[];
  affected_deadlines: string[];
  affected_high_risk_obligations: number;
  impact_score: number;
  impact_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  score_breakdown: Record<string, number>;
  downstream_items: Record<string, unknown>[];
  evaluated_at: string;
}

export interface CriticalPathItem {
  obligation_id: string;
  owner: string;
  action: string;
  status: string;
  deadline?: string | null;
  risk_score: number;
  is_root_blocker: boolean;
  hop_from_root: number;
}

export interface CriticalPathResponse {
  obligation_id: string;
  critical_path: string[];
  critical_path_length: number;
  critical_path_risk: number;
  root_blocker_id?: string | null;
  root_blocker_owner?: string | null;
  root_blocker_action?: string | null;
  path_details: CriticalPathItem[];
  explanation: string;
  evaluated_at: string;
}

export interface ResolutionPlanResponse {
  obligation_id: string;
  action?: string | null;
  owner?: string | null;
  strategy: ResolutionStrategyType | string;
  target_obligation_id: string;
  target_owner: string;
  target_action: string;
  rationale: string;
  expected_impact: string;
  confidence: number;
  supporting_causes: string[];
  suggested_intervention_type?: string | null;
  alternative_strategies: Record<string, unknown>[];
  evaluated_at: string;
}

export interface ResolutionSimulationRequest {
  action: SimulationActionType | string;
  target_obligation_id: string;
  parameters?: Record<string, unknown> | null;
}

export interface ResolutionSimulationResponse {
  simulated_action: SimulationActionType | string;
  target_obligation_id: string;
  current_state: Record<string, unknown>;
  projected_state: Record<string, unknown>;
  affected_obligations: Record<string, unknown>[];
  risk_delta: number;
  unblocked_obligations: Record<string, unknown>[];
  newly_at_risk_obligations: Record<string, unknown>[];
  explanation: string;
  is_simulation_marker: boolean;
  simulated_at: string;
}

export interface BottleneckItem {
  obligation_id: string;
  owner: string;
  action: string;
  status: string;
  downstream_dependents_count: number;
  affected_owners_count: number;
  critical_path_involvement_count: number;
  bottleneck_score: number;
  neutral_summary: string;
}

export interface BottleneckAnalysisResponse {
  workspace_id: string;
  total_bottlenecks: number;
  bottlenecks: BottleneckItem[];
  evaluated_at: string;
}

export interface RiskConcentrationItem {
  concentration_type: ConcentrationType | string;
  target_id: string;
  target_name: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  score: number;
  description: string;
  affected_count: number;
}

export interface RiskConcentrationResponse {
  workspace_id: string;
  total_concentrations: number;
  items: RiskConcentrationItem[];
  evaluated_at: string;
}

// =============================================================================
// PHASE 15: INTELLIGENCE ORCHESTRATOR & DECISION LAYER TYPES
// =============================================================================

export type DecisionPlanStatus =
  | "GENERATED"
  | "PENDING_REVIEW"
  | "APPROVED"
  | "PARTIALLY_EXECUTED"
  | "RESOLVED"
  | "REJECTED"
  | "SUPERSEDED"
  | "EXPIRED"
  | "CANCELLED";

export type HumanDecisionType =
  | "ASSIGN_OWNER"
  | "APPROVE_INTERVENTION"
  | "CONFIRM_EVIDENCE"
  | "CHANGE_DEADLINE"
  | "REMOVE_DEPENDENCY"
  | "APPROVE_ALTERNATIVE_STRATEGY";

export interface HumanDecisionRequirement {
  decision_type: HumanDecisionType | string;
  reason: string;
  affected_obligation_id: string;
  affected_obligation_action?: string | null;
  consequence_of_decision: string;
  supporting_evidence: string[];
  confidence: number;
  proposed_default?: string | null;
  requires_admin: boolean;
}

export interface CandidateStrategyItem {
  strategy_id: string;
  strategy_name: string;
  strategy_type: string;
  target_obligation_id: string;
  target_owner: string;
  target_action: string;
  rationale: string;
  decision_score: number;
  expected_impact: string;
  risk_reduction: number;
  projected_unblocks_count: number;
  simulated_evaluation: Record<string, unknown>;
  human_decisions: HumanDecisionRequirement[];
  is_primary_recommendation: boolean;
  score_breakdown: Record<string, number>;
}

export interface DecisionPlan {
  id: string;
  workspace_id: string;
  target_obligation_id: string;
  target_obligation_action?: string | null;
  target_obligation_owner?: string | null;
  target_obligation_status?: string | null;
  generated_at: string;
  plan_version: number;
  status: DecisionPlanStatus | string;
  overall_urgency: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  overall_risk: number;
  decision_confidence: number;
  primary_objective: string;
  root_cause_obligation_id?: string | null;
  root_cause_summary?: string | null;
  critical_path: Record<string, unknown>[];
  impact_summary: {
    direct_dependents_count?: number;
    total_downstream_dependents_count?: number;
    maximum_dependency_depth?: number;
    affected_owners?: string[];
    affected_deadlines?: string[];
    impact_score?: number;
    impact_level?: string;
  };
  key_risks: string[];
  supporting_evidence: Record<string, unknown>[];
  recommended_actions: CandidateStrategyItem;
  alternative_actions: CandidateStrategyItem[];
  human_decisions_required: HumanDecisionRequirement[];
  assumptions: string[];
  uncertainties: string[];
  simulation_summary: Record<string, unknown>;
  created_from_snapshot_ids: string[];
  created_from_event_ids: string[];
  explainability_narrative: string;
  approved_at?: string | null;
  approved_by_user_id?: string | null;
  rejected_at?: string | null;
  rejected_by_user_id?: string | null;
  superseded_at?: string | null;
  superseded_by_plan_id?: string | null;
  resolution_notes?: string | null;
  is_stale: boolean;
}

export interface DecisionPlanSummary {
  id: string;
  workspace_id: string;
  target_obligation_id: string;
  target_obligation_action: string;
  target_obligation_owner: string;
  target_obligation_status: string;
  plan_version: number;
  status: DecisionPlanStatus | string;
  overall_urgency: string;
  overall_risk: number;
  decision_confidence: number;
  primary_objective: string;
  recommended_strategy_name: string;
  target_owner: string;
  human_decisions_count: number;
  is_stale: boolean;
  generated_at: string;
}

export interface DecisionPlanListResponse {
  items: DecisionPlanSummary[];
  total: number;
}

export interface DecisionPlanApproveRequest {
  selected_strategy_id?: string;
  notes?: string;
}

export interface DecisionPlanRejectRequest {
  reason: string;
}

export interface DecisionPlanSimulateRequest {
  strategy_id?: string;
  custom_action?: string;
  custom_parameters?: Record<string, unknown>;
}

// ==========================================
// PHASE 16: ORGANIZATIONAL MEMORY & HISTORICAL REASONING TYPES
// ==========================================

export type MemoryType =
  | "OBLIGATION_OUTCOME"
  | "EVIDENCE_PATTERN"
  | "INTERVENTION_OUTCOME"
  | "DEPENDENCY_PATTERN"
  | "OWNER_HISTORY"
  | "BLOCKER_PATTERN"
  | "RESOLUTION_PATTERN"
  | "EVENT_CONTEXT"
  | "RECURRING_COMMITMENT";

export type PatternType =
  | "RECURRING_DELAY_PATTERN"
  | "RECURRING_BLOCKER_PATTERN"
  | "RECURRING_DEPENDENCY_PATTERN"
  | "RECURRING_INTERVENTION_RESPONSE"
  | "RECURRING_OBLIGATION_TYPE";

export type PatternMaturity =
  | "INSUFFICIENT_HISTORY"
  | "EMERGING_PATTERN"
  | "ESTABLISHED_PATTERN";

export type RecurrenceInterval =
  | "DAILY"
  | "WEEKLY"
  | "BIWEEKLY"
  | "MONTHLY"
  | "QUARTERLY"
  | "AD_HOC";

export interface SemanticRepresentation {
  action?: string | null;
  deliverable?: string | null;
  entities: string[];
  topics: string[];
  obligation_type?: string | null;
  deadline_characteristic?: string | null;
  blocker_terms: string[];
}

export interface OrganizationalMemory {
  id: string;
  workspace_id: string;
  memory_type: MemoryType | string;
  source_type: string;
  source_ref?: string | null;
  obligation_id?: string | null;
  event_id?: string | null;
  owner_id?: string | null;
  content: string;
  semantic_summary: string;
  semantic_labels: string[];
  entities: string[];
  topics: string[];
  outcome?: string | null;
  observed_at: string;
  created_at: string;
  metadata_json: Record<string, unknown>;
  importance_score: number;
  confidence: number;
  is_active: boolean;
}

export interface MemoryRetrievalItem {
  memory: OrganizationalMemory;
  relevance_score: number;
  match_reasons: string[];
  similarity_breakdown: Record<string, number>;
}

export interface HistoricalPatternItem {
  pattern_type: PatternType | string;
  maturity: PatternMaturity | string;
  observation_count: number;
  confidence: number;
  supporting_memory_ids: string[];
  first_observed_at?: string | null;
  last_observed_at?: string | null;
  description: string;
  neutral_metrics: Record<string, unknown>;
}

export interface HistoricalOwnerAnalytics {
  owner_id: string;
  total_commitments_observed: number;
  completed_count: number;
  completed_late_count: number;
  completed_on_time_count: number;
  completion_rate: number;
  on_time_completion_rate: number;
  median_delay_hours: number;
  late_frequency: number;
  total_interventions_received: number;
  intervention_response_count: number;
  intervention_response_rate: number;
  neutral_summary: string;
  has_sufficient_history: boolean;
  evaluated_at: string;
}

export interface RecurringObligationItem {
  recurrence_type: RecurrenceInterval | string;
  interval_days: number;
  observation_count: number;
  confidence: number;
  last_observed_date?: string | null;
  next_predicted_date?: string | null;
  description: string;
}

export interface MemoryContextResponse {
  obligation_id: string;
  context_status: "AVAILABLE" | "NO_COMPARABLE_HISTORY" | string;
  semantic_representation: SemanticRepresentation;
  similar_obligations: MemoryRetrievalItem[];
  historical_patterns: HistoricalPatternItem[];
  recurring_blockers: HistoricalPatternItem[];
  intervention_history: MemoryRetrievalItem[];
  owner_analytics?: HistoricalOwnerAnalytics | null;
  recurring_commitment?: RecurringObligationItem | null;
  confidence: number;
  explanation: string;
  evaluated_at: string;
}

// ==============================================================================
// PHASE 16: CONTROLLED DECISION EXECUTION & OUTCOME VERIFICATION
// ==============================================================================

export type ExecutionType =
  | "INTERVENTION_MESSAGE"
  | "STATUS_POLL"
  | "BLOCKER_NOTIFICATION"
  | "ESCALATION_NOTICE"
  | "EVIDENCE_REQUEST";

export type ExecutionStatus =
  | "PENDING_AUTHORIZATION"
  | "AUTHORIZED"
  | "QUEUED"
  | "EXECUTING"
  | "DELIVERED"
  | "DELIVERY_FAILED"
  | "RETRY_SCHEDULED"
  | "RESPONSE_PENDING"
  | "OUTCOME_DETECTED"
  | "RESOLVED"
  | "FAILED"
  | "CANCELLED"
  | "EXPIRED";

export type ExecutionOutcome =
  | "ACKNOWLEDGED"
  | "PROGRESS_REPORTED"
  | "COMPLETION_SIGNAL"
  | "NEGATIVE_RESPONSE"
  | "NO_RESPONSE"
  | "CONFLICTING_RESPONSE"
  | "UNKNOWN";

export type ExecutionFailureCode =
  | "INVALID_RECIPIENT"
  | "RATE_LIMITED"
  | "NETWORK_TIMEOUT"
  | "PERMISSION_DENIED"
  | "CONFIGURATION_ERROR"
  | "RETRY_LIMIT_EXCEEDED"
  | "CANCELLED_BY_OPERATOR"
  | "SUPERSEDED_BEFORE_EXECUTION"
  | "PROVIDER_UNAVAILABLE";

export interface ExecutionRecord {
  id: string;
  workspace_id: string;
  decision_plan_id: string;
  intervention_id?: string | null;
  obligation_id: string;
  execution_type: ExecutionType | string;
  provider: string;
  provider_version: string;
  status: ExecutionStatus;
  authorized_by?: string | null;
  authorized_at?: string | null;
  executed_at?: string | null;
  provider_execution_ref?: string | null;
  idempotency_key: string;
  request_payload_hash: string;
  safe_request_metadata: Record<string, unknown>;
  delivery_status?: string | null;
  failure_code?: ExecutionFailureCode | null;
  failure_reason?: string | null;
  retry_count: number;
  max_retries: number;
  next_retry_at?: string | null;
  response_received_at?: string | null;
  response_event_id?: string | null;
  outcome?: ExecutionOutcome | null;
  created_at: string;
  updated_at: string;
}

export interface ExecutionReceipt {
  execution_id: string;
  workspace_id: string;
  decision_plan_id: string;
  plan_version: number;
  intervention_id?: string | null;
  obligation_id: string;
  obligation_action: string;
  target_owner?: string | null;
  provider: string;
  provider_execution_ref?: string | null;
  delivery_status: string;
  status: ExecutionStatus;
  authorized_by?: string | null;
  authorized_at?: string | null;
  executed_at?: string | null;
  retry_count: number;
  failure_code?: string | null;
  failure_reason?: string | null;
  safe_metadata: Record<string, unknown>;
  receipt_generated_at: string;
}

export interface ExecutionQueueItem {
  execution_id: string;
  decision_plan_id: string;
  plan_version: number;
  obligation_id: string;
  obligation_action: string;
  obligation_owner: string;
  plan_urgency: string;
  plan_risk: number;
  provider: string;
  status: ExecutionStatus;
  authorized_by?: string | null;
  authorized_at?: string | null;
  executed_at?: string | null;
  retry_count: number;
  max_retries: number;
  outcome?: ExecutionOutcome | null;
  created_at: string;
}

export interface ExecutionQueueResponse {
  pending_authorization_count: number;
  executing_count: number;
  delivered_count: number;
  awaiting_response_count: number;
  failed_count: number;
  resolved_count: number;
  items: ExecutionQueueItem[];
}

export interface ExecutionAuthorizeRequest {
  strategy_name?: string;
  provider?: string;
  authorized_action?: Record<string, unknown>;
  notes?: string;
}

export interface ExecutionExecuteRequest {
  provider?: string;
  notes?: string;
}

export interface ExecutionCancelRequest {
  reason: string;
}

export interface ExecutionRetryRequest {
  notes?: string;
}

export interface OutcomeReconciliationResponse {
  execution_id: string;
  event_id: string;
  outcome: ExecutionOutcome;
  previous_execution_status: ExecutionStatus;
  updated_execution_status: ExecutionStatus;
  intervention_status?: string | null;
  obligation_status: string;
  evidence_created: boolean;
  evidence_id?: string | null;
  plan_marked_stale: boolean;
  reconciled_at: string;
  reconciliation_notes: string;
}

// ==========================================
// PHASE 17: CONTINUOUS MONITORING & ESCALATION
// ==========================================

export type WatchType =
  | "DEADLINE"
  | "RISK"
  | "DEPENDENCY"
  | "EXECUTION"
  | "RESPONSE"
  | "EVIDENCE"
  | "DECISION_PLAN"
  | "CRITICAL_PATH"
  | "BOTTLENECK";

export type WatchStatus =
  | "ACTIVE"
  | "PAUSED"
  | "TRIGGERED"
  | "RESOLVED"
  | "EXPIRED"
  | "CANCELLED";

export type MonitoringEventType =
  | "DEADLINE_APPROACHING"
  | "DEADLINE_BREACHED"
  | "RISK_ESCALATED"
  | "RISK_DEESCALATED"
  | "DEPENDENCY_BLOCKED"
  | "DEPENDENCY_RESOLVED"
  | "NEW_COMPLETION_EVIDENCE"
  | "NEW_NEGATIVE_SIGNAL"
  | "OWNER_UNRESPONSIVE"
  | "EXECUTION_FAILED"
  | "EXECUTION_STALLED"
  | "EXECUTION_RESPONSE_TIMEOUT"
  | "DECISION_PLAN_STALE"
  | "DECISION_PLAN_RESOLVED"
  | "CRITICAL_PATH_CHANGED"
  | "SYSTEMIC_BOTTLENECK_DETECTED";

export type MonitoringSeverity =
  | "INFO"
  | "NOTICE"
  | "WARNING"
  | "HIGH"
  | "CRITICAL";

export type EscalationStatus =
  | "OPEN"
  | "ACKNOWLEDGED"
  | "RESOLVED"
  | "DISMISSED"
  | "EXPIRED";

export type MonitoringRunStatus =
  | "RUNNING"
  | "COMPLETED"
  | "PARTIAL"
  | "FAILED";

export type TargetType =
  | "OBLIGATION"
  | "EXECUTION"
  | "DECISION_PLAN"
  | "INTERVENTION"
  | "WORKSPACE";

export interface MonitoringWatch {
  id: string;
  workspace_id: string;
  watch_type: WatchType;
  target_type: TargetType;
  target_id: string;
  status: WatchStatus;
  configuration: Record<string, unknown>;
  last_evaluated_at?: string | null;
  next_evaluation_at?: string | null;
  last_observed_state: Record<string, unknown>;
  last_triggered_at?: string | null;
  trigger_count: number;
  cooldown_until?: string | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MonitoringWatchCreate {
  watch_type: WatchType;
  target_type?: TargetType;
  target_id: string;
  configuration?: Record<string, unknown>;
  next_evaluation_at?: string | null;
}

export interface MonitoringWatchUpdate {
  status?: WatchStatus;
  configuration?: Record<string, unknown>;
  next_evaluation_at?: string | null;
}

export interface MonitoringWatchListResponse {
  items: MonitoringWatch[];
  total: number;
}

export interface MonitoringEvent {
  id: string;
  workspace_id: string;
  watch_id?: string | null;
  event_type: MonitoringEventType;
  severity: MonitoringSeverity;
  target_type: TargetType;
  target_id: string;
  previous_state: Record<string, unknown>;
  current_state: Record<string, unknown>;
  detected_at: string;
  explanation: string;
  signals: Record<string, unknown>;
  provenance: Record<string, unknown>;
  deduplication_key: string;
  acknowledged_at?: string | null;
  acknowledged_by?: string | null;
  resolved_at?: string | null;
  resolution_reason?: string | null;
}

export interface MonitoringEventListResponse {
  items: MonitoringEvent[];
  total: number;
}

export interface EscalationCandidate {
  id: string;
  workspace_id: string;
  monitoring_event_id?: string | null;
  target_type: TargetType;
  target_id: string;
  severity: MonitoringSeverity;
  reason: string;
  recommended_next_step: string;
  affected_obligations: string[];
  affected_owners: string[];
  blast_radius: Record<string, unknown>;
  decision_plan_id?: string | null;
  status: EscalationStatus;
  deduplication_key: string;
  created_at: string;
  acknowledged_at?: string | null;
  acknowledged_by?: string | null;
  resolved_at?: string | null;
}

export interface EscalationCandidateListResponse {
  items: EscalationCandidate[];
  total: number;
}

export interface EscalationAcknowledgeRequest {
  notes?: string;
}

export interface EscalationResolveRequest {
  resolution_reason?: string;
}

export interface EscalationDismissRequest {
  reason?: string;
}

export interface MonitoringRun {
  id: string;
  workspace_id: string;
  started_at: string;
  completed_at?: string | null;
  watches_evaluated: number;
  events_created: number;
  escalations_created: number;
  errors: Record<string, unknown>[];
  status: MonitoringRunStatus;
}

export interface MonitoringRunListResponse {
  items: MonitoringRun[];
  total: number;
}

export interface MonitoringRunRequest {
  watch_ids?: string[];
  force_all?: boolean;
}

export interface MonitoringSummaryResponse {
  active_watches_count: number;
  critical_events_count: number;
  high_events_count: number;
  open_escalations_count: number;
  deadline_breaches_count: number;
  risk_escalations_count: number;
  execution_failures_count: number;
  response_timeouts_count: number;
  dependency_blocks_count: number;
  stale_decision_plans_count: number;
  recent_events: MonitoringEvent[];
  open_escalations: EscalationCandidate[];
}
