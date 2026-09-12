"use client";

import React, { useEffect, useState, useCallback, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Clock,
  User,
  ShieldAlert,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  PlayCircle,
  Edit,
  Trash2,
  Plus,
  X,
  GitFork,
  Link as LinkIcon,
  ArrowRight,
  Ban,
  Unlock,
  Check,
  Sparkles,
  Activity,
  Flame,
  Calendar,
  Scale,
  Brain,
  Shield,
  ShieldCheck,
  Route,
  Zap,
  Play,
} from "lucide-react";
import {
  Obligation,
  ObligationStatus,
  ObligationType,
  ObligationGraphResponse,
  EvidenceResponse,
  EdgeType,
  RiskAssessmentResponse,
  Intervention,
  ReconciliationRecord,
  ObligationPredictionResponse,
  SimilarObligationItem,
  OwnerPatternMetric,
  ModelComparisonResponse,
  PredictionHistoryItem,
  AuditEvent,
  RootCauseAnalysisResponse,
  ImpactAnalysisResponse,
  CriticalPathResponse,
  ResolutionPlanResponse,
} from "@/lib/types/obligation";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ConfidenceBadge } from "@/components/ui/ConfidenceBadge";
import { InterventionCard } from "@/components/interventions/InterventionCard";
import { InterventionReviewModal } from "@/components/interventions/InterventionReviewModal";
import { ReconciliationReviewModal } from "@/components/reconciliation/ReconciliationReviewModal";
import { HistoricalContextCard } from "@/components/memory/HistoricalContextCard";
import { obligationsApi, interventionsApi, reconciliationApi, intelligenceApi, auditApi } from "@/lib/api/obligations";
import { useToast } from "@/components/ui/ToastContext";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function ObligationDetailPage({ params }: PageProps) {
  const resolvedParams = use(params);
  const obligationId = resolvedParams.id;

  const router = useRouter();
  const { toast } = useToast();

  const [obligation, setObligation] = useState<Obligation | null>(null);
  const [graph, setGraph] = useState<ObligationGraphResponse | null>(null);
  const [evidenceList, setEvidenceList] = useState<EvidenceResponse[]>([]);
  const [riskAssessment, setRiskAssessment] = useState<RiskAssessmentResponse | null>(null);
  const [interventions, setInterventions] = useState<Intervention[]>([]);
  const [reconciliation, setReconciliation] = useState<ReconciliationRecord | null>(null);
  const [prediction, setPrediction] = useState<ObligationPredictionResponse | null>(null);
  const [similarObligations, setSimilarObligations] = useState<SimilarObligationItem[]>([]);
  const [ownerContext, setOwnerContext] = useState<OwnerPatternMetric | null>(null);
  const [modelComparison, setModelComparison] = useState<ModelComparisonResponse | null>(null);
  const [predictionHistory, setPredictionHistory] = useState<PredictionHistoryItem[]>([]);
  const [auditTrail, setAuditTrail] = useState<AuditEvent[]>([]);
  const [rootCause, setRootCause] = useState<RootCauseAnalysisResponse | null>(null);
  const [impact, setImpact] = useState<ImpactAnalysisResponse | null>(null);
  const [criticalPath, setCriticalPath] = useState<CriticalPathResponse | null>(null);
  const [resolutionPlan, setResolutionPlan] = useState<ResolutionPlanResponse | null>(null);
  const [selectedIntervention, setSelectedIntervention] = useState<Intervention | null>(null);
  const [showInterventionModal, setShowInterventionModal] = useState(false);
  const [showReconciliationModal, setShowReconciliationModal] = useState(false);
  const [planningIntervention, setPlanningIntervention] = useState(false);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);

  // Edit Mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editAction, setEditAction] = useState("");
  const [editOwner, setEditOwner] = useState("");
  const [editBeneficiary, setEditBeneficiary] = useState("");
  const [editDeadline, setEditDeadline] = useState("");
  const [editConditions, setEditConditions] = useState("");
  const [editNextAction, setEditNextAction] = useState("");
  const [editType, setEditType] = useState<ObligationType>("OWED_BY_ME");

  // Evidence attachment modal state
  const [showEvidenceModal, setShowEvidenceModal] = useState(false);
  const [evidenceNote, setEvidenceNote] = useState("");
  const [evidenceUrl, setEvidenceUrl] = useState("");

  // Add Relationship Modal state
  const [showAddEdgeModal, setShowAddEdgeModal] = useState(false);
  const [edgeType, setEdgeType] = useState<EdgeType>("DEPENDS_ON");
  const [targetObligationId, setTargetObligationId] = useState("");
  const [allObligations, setAllObligations] = useState<Obligation[]>([]);
  const [loadingAll, setLoadingAll] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [
        obData,
        graphData,
        evData,
        riskData,
        invData,
        recData,
        dossierData,
        compData,
        histData,
        auditData,
        rcData,
        impData,
        cpData,
        planData,
      ] = await Promise.all([
        obligationsApi.getById(obligationId),
        obligationsApi.getGraph(obligationId),
        obligationsApi.getEvidence(obligationId),
        obligationsApi.getRiskAssessment(obligationId).catch(() => null),
        interventionsApi.list({ obligation_id: obligationId }).catch(() => ({ items: [], total: 0 })),
        reconciliationApi.getByObligationId(obligationId).catch(() => null),
        intelligenceApi.getDossier(obligationId).catch(() => null),
        intelligenceApi.compareModels(obligationId).catch(() => null),
        intelligenceApi.getPredictionHistory(obligationId).catch(() => null),
        auditApi.getEntityHistory("obligation", obligationId).catch(() => []),
        intelligenceApi.getRootCause(obligationId).catch(() => null),
        intelligenceApi.getImpact(obligationId).catch(() => null),
        intelligenceApi.getCriticalPath(obligationId).catch(() => null),
        intelligenceApi.getResolutionPlan(obligationId).catch(() => null),
      ]);
      setObligation(obData);
      setGraph(graphData);
      setEvidenceList(evData);
      setRiskAssessment(riskData);
      setInterventions(invData.items || []);
      setReconciliation(recData);
      setAuditTrail(auditData || []);
      setRootCause(rcData);
      setImpact(impData);
      setCriticalPath(cpData);
      setResolutionPlan(planData);
      if (dossierData) {
        setPrediction(dossierData.prediction);
        setSimilarObligations(dossierData.similar_obligations.items || []);
        setOwnerContext(dossierData.owner_context || null);
      }
      if (compData) setModelComparison(compData);
      if (histData) setPredictionHistory(histData.history || []);

      // Sync edit form
      setEditAction(obData.action);
      setEditOwner(obData.owner);
      setEditBeneficiary(obData.beneficiary);
      setEditDeadline(obData.deadline ? new Date(obData.deadline).toISOString().slice(0, 16) : "");
      setEditConditions(obData.conditions ? String(obData.conditions) : "");
      setEditNextAction(obData.next_action || "");
      setEditType(obData.obligation_type);
    } catch (err) {
      toast({
        type: "error",
        title: "Not Found",
        description: err instanceof Error ? err.message : "Could not load obligation.",
      });
    } finally {
      setLoading(false);
    }
  }, [obligationId, toast]);

  const handlePlanIntervention = async () => {
    try {
      setPlanningIntervention(true);
      const planned = await interventionsApi.plan(obligationId, true);
      toast({
        type: "success",
        title: "Intervention Plan Generated",
        description: "Review generated message draft and target.",
      });
      setSelectedIntervention(planned);
      setShowInterventionModal(true);
      await loadData();
    } catch (err) {
      toast({
        type: "error",
        title: "Planning Failed",
        description: err instanceof Error ? err.message : "Failed to plan intervention.",
      });
    } finally {
      setPlanningIntervention(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [loadData]);

  const loadAllObligationsForModal = async () => {
    try {
      setLoadingAll(true);
      const res = await obligationsApi.list({ limit: 100 });
      // Filter out self
      setAllObligations(res.items.filter((item) => item.id !== obligationId));
    } catch (err) {
      toast({
        type: "error",
        title: "Load Failed",
        description: err instanceof Error ? err.message : "Could not load obligations list.",
      });
    } finally {
      setLoadingAll(false);
    }
  };

  const handleOpenAddEdgeModal = () => {
    setShowAddEdgeModal(true);
    setTargetObligationId("");
    loadAllObligationsForModal();
  };

  const handleCreateEdge = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetObligationId) return;

    try {
      setUpdating(true);
      await obligationsApi.createEdge({
        from_obligation_id: obligationId,
        to_obligation_id: targetObligationId,
        edge_type: edgeType,
      });

      toast({
        type: "success",
        title: "Relationship Added",
        description: `Connected via ${edgeType}.`,
      });

      setShowAddEdgeModal(false);
      setTargetObligationId("");
      await loadData();
    } catch (err) {
      toast({
        type: "error",
        title: "Relationship Failed",
        description: err instanceof Error ? err.message : "Could not create relationship edge.",
      });
    } finally {
      setUpdating(false);
    }
  };

  const handleConfirmEvidence = async (evidenceId: string) => {
    try {
      setUpdating(true);
      const updated = await obligationsApi.confirmEvidence(obligationId, evidenceId);
      setObligation(updated);
      toast({
        type: "success",
        title: "Evidence Confirmed",
        description: "Obligation fulfilled and completed. Downstream dependencies unblocked.",
      });
      await loadData();
    } catch (err) {
      toast({
        type: "error",
        title: "Confirmation Failed",
        description: err instanceof Error ? err.message : "Could not confirm evidence.",
      });
    } finally {
      setUpdating(false);
    }
  };

  const handleRejectEvidence = async (evidenceId: string) => {
    try {
      setUpdating(true);
      await obligationsApi.rejectEvidence(obligationId, evidenceId);
      toast({
        type: "info",
        title: "Evidence Rejected",
        description: "Candidate evidence marked as rejected.",
      });
      await loadData();
    } catch (err) {
      toast({
        type: "error",
        title: "Rejection Failed",
        description: err instanceof Error ? err.message : "Could not reject evidence.",
      });
    } finally {
      setUpdating(false);
    }
  };

  const handleStatusChange = async (newStatus: ObligationStatus, evidencePayload?: Record<string, unknown>) => {
    try {
      setUpdating(true);
      const updated = await obligationsApi.updateStatus(
        obligationId,
        newStatus,
        undefined,
        evidencePayload
      );
      setObligation(updated);
      toast({
        type: "success",
        title: "Status Transitioned",
        description: `Obligation is now ${newStatus}.`,
      });
      setShowEvidenceModal(false);
      setEvidenceNote("");
      setEvidenceUrl("");
      await loadData();
    } catch (err) {
      toast({
        type: "error",
        title: "Transition Rejected",
        description: err instanceof Error ? err.message : "State transition not allowed.",
      });
    } finally {
      setUpdating(false);
    }
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setUpdating(true);
      const updated = await obligationsApi.update(obligationId, {
        action: editAction.trim(),
        owner: editOwner.trim(),
        beneficiary: editBeneficiary.trim(),
        deadline: editDeadline ? new Date(editDeadline).toISOString() : null,
        conditions: editConditions.trim() ? editConditions.trim() : null,
        next_action: editNextAction.trim() ? editNextAction.trim() : null,
        obligation_type: editType,
      });
      setObligation(updated);
      setIsEditing(false);
      toast({
        type: "success",
        title: "Obligation Updated",
      });
      await loadData();
    } catch (err) {
      toast({
        type: "error",
        title: "Update Failed",
        description: err instanceof Error ? err.message : "Could not save edits.",
      });
    } finally {
      setUpdating(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to permanently delete this obligation?")) return;
    try {
      setUpdating(true);
      await obligationsApi.delete(obligationId);
      toast({
        type: "success",
        title: "Obligation Deleted",
      });
      router.push("/");
    } catch (err) {
      toast({
        type: "error",
        title: "Delete Failed",
        description: err instanceof Error ? err.message : "Could not delete.",
      });
      setUpdating(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="h-6 w-32 bg-stone-100 rounded animate-pulse" />
        <div className="h-80 bg-stone-100/60 rounded-2xl animate-pulse" />
      </div>
    );
  }

  if (!obligation) {
    return (
      <div className="max-w-xl mx-auto text-center py-16 space-y-4">
        <AlertCircle className="w-12 h-12 text-rose-400 mx-auto" />
        <h2 className="text-lg font-bold text-stone-950">Obligation Not Found</h2>
        <p className="text-sm text-stone-600">The requested obligation record does not exist or was deleted.</p>
        <Link href="/" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-stone-200 text-stone-950 text-xs">
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </Link>
      </div>
    );
  }

  const isOwedByMe = obligation.obligation_type === "OWED_BY_ME";
  const isBlocked = obligation.status === "BLOCKED" || (graph && graph.blockers.length > 0);
  const pendingSuggestedEvidence = evidenceList.filter((e) => e.correlation_status === "SUGGESTED");

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Navigation Breadcrumb */}
      <div className="flex items-center justify-between">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </Link>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsEditing(!isEditing)}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold transition-colors shadow-2xs"
          >
            <Edit className="w-3.5 h-3.5" />
            <span>{isEditing ? "Cancel Edit" : "Edit Details"}</span>
          </button>

          <button
            onClick={handleDelete}
            disabled={updating}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-rose-200 bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-semibold transition-colors shadow-2xs"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Delete</span>
          </button>
        </div>
      </div>

      {/* FLAGSHIP HEADER: Section 11 Product Specification */}
      <div className="bg-white rounded-3xl border border-slate-200 p-6 sm:p-8 shadow-sm space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4 pb-4 border-b border-slate-100">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
              <span className={`w-2.5 h-2.5 rounded-full ${isOwedByMe ? "bg-orange-500" : "bg-emerald-500"}`} />
              <span>{isOwedByMe ? "Outgoing Commitment (You Owe)" : "Incoming Commitment (Others Owe You)"}</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 leading-snug">
              {obligation.action}
            </h1>
          </div>

          <div className="flex items-center gap-2.5">
            {obligation.is_at_risk && (
              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-200">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                <span>At Risk</span>
              </span>
            )}
            <StatusBadge status={obligation.status} />
          </div>
        </div>

        {/* Core Metadata Row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 space-y-0.5">
            <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wider">Owner (Obligor)</span>
            <div className="font-bold text-slate-900 truncate flex items-center gap-1.5">
              <User className="w-3.5 h-3.5 text-orange-600 shrink-0" />
              <span className="truncate">{obligation.owner}</span>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 space-y-0.5">
            <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wider">Beneficiary (Obligee)</span>
            <div className="font-bold text-slate-900 truncate flex items-center gap-1.5">
              <User className="w-3.5 h-3.5 text-slate-600 shrink-0" />
              <span className="truncate">{obligation.beneficiary}</span>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 space-y-0.5">
            <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wider">Deadline</span>
            <div className="font-bold text-slate-900 truncate flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-amber-600 shrink-0" />
              <span>{obligation.deadline ? new Date(obligation.deadline).toLocaleDateString() : "Flexible"}</span>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 space-y-0.5">
            <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wider">Priority / Risk</span>
            <div className="font-bold text-slate-900 truncate flex items-center gap-1.5">
              <Flame className="w-3.5 h-3.5 text-rose-600 shrink-0" />
              <span>{riskAssessment?.risk_level || (obligation.is_at_risk ? "HIGH" : "NORMAL")}</span>
            </div>
          </div>
        </div>

        {/* CURRENT STATE CALLOUT */}
        {isBlocked ? (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-xs space-y-1.5">
            <div className="flex items-center gap-2 text-rose-800 font-bold">
              <AlertTriangle className="w-4 h-4 text-rose-600" />
              <span>CURRENT STATE: BLOCKED</span>
            </div>
            <p className="text-slate-800 leading-relaxed font-medium">
              {obligation.block_reason && typeof obligation.block_reason === "object" && (obligation.block_reason as Record<string, unknown>).blocked_by
                ? ((obligation.block_reason as Record<string, unknown>).blocked_by as Array<Record<string, unknown>>)?.[0]?.reason as string ||
                  "Finance approval / upstream benchmark is delaying execution."
                : "Upstream prerequisite commitments are unresolved or delayed, preventing progression."}
            </p>
          </div>
        ) : obligation.is_at_risk ? (
          <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-xs space-y-1.5">
            <div className="flex items-center gap-2 text-amber-800 font-bold">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <span>CURRENT STATE: AT RISK</span>
            </div>
            <p className="text-slate-800 leading-relaxed font-medium">
              Commitment deadline is rapidly approaching with remaining incomplete verification steps.
            </p>
          </div>
        ) : (
          <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-xs space-y-1.5">
            <div className="flex items-center gap-2 text-emerald-800 font-bold">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>CURRENT STATE: ON TRACK</span>
            </div>
            <p className="text-slate-800 leading-relaxed font-medium">
              No active blockers detected. Deliverable is progressing according to schedule.
            </p>
          </div>
        )}

        {/* INTERACTIVE TIMELINE PROGRESSION */}
        <div className="pt-2">
          <div className="text-[10px] font-bold text-slate-600 uppercase tracking-wider mb-3">
            Obligation Lifecycle Timeline
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-center text-xs">
            <div className="p-2.5 rounded-xl bg-slate-50 border border-emerald-200 text-emerald-800 font-semibold space-y-1">
              <div className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 mx-auto flex items-center justify-center font-bold text-[10px]">
                ✓
              </div>
              <div className="text-[11px]">Commitment Created</div>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-50 border border-emerald-200 text-emerald-800 font-semibold space-y-1">
              <div className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 mx-auto flex items-center justify-center font-bold text-[10px]">
                ✓
              </div>
              <div className="text-[11px]">Progress Update</div>
            </div>

            <div className={`p-2.5 rounded-xl border font-semibold space-y-1 ${
              isBlocked ? "bg-rose-50 border-rose-300 text-rose-800" : "bg-slate-50 border-slate-200 text-slate-400"
            }`}>
              <div className={`w-5 h-5 rounded-full mx-auto flex items-center justify-center font-bold text-[10px] ${
                isBlocked ? "bg-rose-200 text-rose-800" : "bg-slate-200 text-slate-500"
              }`}>
                {isBlocked ? "!" : "3"}
              </div>
              <div className="text-[11px]">Blocker Detected</div>
            </div>

            <div className={`p-2.5 rounded-xl border font-semibold space-y-1 ${
              obligation.is_at_risk || isBlocked ? "bg-amber-50 border-amber-300 text-amber-800" : "bg-slate-50 border-slate-200 text-slate-400"
            }`}>
              <div className={`w-5 h-5 rounded-full mx-auto flex items-center justify-center font-bold text-[10px] ${
                obligation.is_at_risk || isBlocked ? "bg-amber-200 text-amber-800" : "bg-slate-200 text-slate-500"
              }`}>
                {obligation.is_at_risk || isBlocked ? "▲" : "4"}
              </div>
              <div className="text-[11px]">Risk Increased</div>
            </div>

            <div className="p-2.5 rounded-xl bg-orange-50 border border-orange-300 text-orange-900 font-semibold space-y-1">
              <div className="w-5 h-5 rounded-full bg-orange-200 text-orange-800 mx-auto flex items-center justify-center font-bold text-[10px]">
                ★
              </div>
              <div className="text-[11px]">Action Recommended</div>
            </div>
          </div>
        </div>

        {/* WHY IS THIS AT RISK? (SECTION 11 PROMINENT INTELLIGENCE) */}
        {(isBlocked || obligation.is_at_risk || rootCause) && (
          <div className="p-5 rounded-2xl bg-gradient-to-r from-orange-50/70 via-amber-50/50 to-orange-50/70 border border-orange-200 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-orange-600" />
                <h3 className="text-sm font-bold text-slate-900">Why Is This At Risk?</h3>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-orange-100 text-orange-800 border border-orange-200">
                Gemini Causal Intelligence
              </span>
            </div>

            <p className="text-xs text-slate-800 leading-relaxed font-medium">
              {rootCause?.overall_explanation ||
                (isBlocked
                  ? "Upstream database benchmark metrics required to size migration targets are overdue. Without resolution, downstream production release cannot be authorized."
                  : "Velocity metrics indicate high likelihood of deadline overrun based on cross-team workload and unconfirmed prerequisites.")}
            </p>

            {/* RECOMMENDED NEXT ACTION & HUMAN AUTHORIZATION */}
            <div className="pt-2 border-t border-orange-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="space-y-0.5">
                <span className="text-[10px] font-bold text-orange-800 uppercase tracking-wider">
                  Recommended Next Action
                </span>
                <div className="text-xs font-bold text-slate-900">
                  {obligation.next_action ||
                    rootCause?.recommended_resolution ||
                    "Expedite benchmark on secondary replica before escalating cutover window."}
                </div>
              </div>

              <button
                onClick={handlePlanIntervention}
                disabled={planningIntervention}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-orange-600 hover:bg-orange-700 text-white text-xs font-bold shadow-xs transition-all active:scale-[0.98] shrink-0 disabled:opacity-50"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{planningIntervention ? "Synthesizing Plan..." : "Review Recommendation"}</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* PHASE 4: Suggested Completion Evidence Review Card */}
      {obligation.status !== "COMPLETED" && pendingSuggestedEvidence.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-4 animate-in fade-in">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-stone-900 font-bold text-sm">
              <Sparkles className="w-5 h-5 text-orange-600" />
              <span>Possible Fulfillment / Completion Evidence Detected</span>
            </div>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-orange-50 text-orange-700 border border-orange-200">
              {pendingSuggestedEvidence.length} Candidate(s)
            </span>
          </div>

          <div className="space-y-3">
            {pendingSuggestedEvidence.map((ev) => (
              <div
                key={ev.id}
                className="p-4 rounded-xl bg-stone-50/60 border border-stone-200 space-y-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-stone-800">
                      {ev.actor || "External Actor"}
                    </span>
                    <span className="text-stone-400">•</span>
                    <span className="text-stone-600 capitalize">{ev.source_type}</span>
                    {ev.source_ref && (
                      <span className="text-stone-500 font-mono text-[11px]">({ev.source_ref})</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-orange-700 font-bold text-xs">
                      Match: {Math.round(ev.correlation_confidence * 100)}%
                    </span>
                    <span className="text-stone-500 text-[11px]">
                      {new Date(ev.observed_at).toLocaleString()}
                    </span>
                  </div>
                </div>

                <p className="text-sm text-stone-900 font-medium bg-white p-3 rounded-lg border border-stone-200">
                  &ldquo;{ev.content}&rdquo;
                </p>

                {/* Match Signals Breakdown */}
                {ev.reasoning && Array.isArray(ev.reasoning) && ev.reasoning.length > 0 && (
                  <div className="space-y-1">
                    <span className="text-[11px] font-semibold text-stone-600 uppercase tracking-wider block">
                      Correlation Match Reasoning:
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-xs text-stone-700">
                      {ev.reasoning.map((r, ri) => (
                        <div key={ri} className="flex items-center gap-1.5">
                          <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                          <span className="text-stone-700">{r}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Human Confirmation Buttons */}
                <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-stone-200/80">
                  <button
                    onClick={() => handleRejectEvidence(ev.id)}
                    disabled={updating}
                    className="px-3.5 py-1.5 rounded-lg border border-stone-200 bg-white hover:bg-stone-50 text-stone-700 hover:text-stone-900 text-xs font-medium transition-colors"
                  >
                    Reject Evidence
                  </button>
                  <button
                    onClick={() => handleConfirmEvidence(ev.id)}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold shadow-sm active:scale-95 transition-all"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Confirm Completion</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* PHASE 3: Prominent BLOCKED State Banner */}
      {isBlocked && (
        <div className="bg-rose-50/70 border border-rose-200 rounded-2xl p-6 shadow-sm space-y-3 animate-in fade-in">
          <div className="flex items-center gap-2.5 text-rose-700 font-bold text-sm">
            <Ban className="w-5 h-5 text-rose-600 animate-pulse" />
            <span>This Obligation is BLOCKED</span>
          </div>

          <p className="text-xs text-stone-700 leading-relaxed">
            Progress cannot proceed because one or more prerequisite obligations are unresolved or overdue.
          </p>

          {graph && graph.blockers.length > 0 ? (
            <div className="space-y-2 pt-2">
              <span className="text-[11px] font-semibold text-rose-700 uppercase tracking-wider block">
                Active Blocker(s):
              </span>
              <div className="space-y-2">
                {graph.blockers.map((blocker) => (
                  <div
                    key={blocker.obligation_id}
                    className="p-3.5 rounded-xl bg-white border border-rose-200 flex flex-wrap items-center justify-between gap-3 text-xs"
                  >
                    <div className="space-y-1 max-w-xl">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-stone-900">{blocker.owner}</span>
                        <span className="text-stone-500">•</span>
                        <StatusBadge status={blocker.status} />
                      </div>
                      <div className="text-stone-700 font-medium">{blocker.action}</div>
                      <div className="text-[11px] text-rose-700 italic">{blocker.reason}</div>
                    </div>

                    <Link
                      href={`/obligations/${blocker.obligation_id}`}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-semibold transition-colors"
                    >
                      <span>View Blocker</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* PHASE 5: Proactive Risk & Rescue Inspector Panel */}
      {riskAssessment && (
        <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-6">
          {/* Header Row */}
          <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-stone-200/80">
            <div className="flex items-center gap-3">
              <div
                className={`w-10 h-10 rounded-xl flex items-center justify-center border ${
                  riskAssessment.risk_level === "CRITICAL"
                    ? "bg-rose-50 text-rose-700 border-rose-200"
                    : riskAssessment.risk_level === "HIGH"
                    ? "bg-amber-50 text-amber-700 border-amber-200"
                    : riskAssessment.risk_level === "MEDIUM"
                    ? "bg-orange-50 text-orange-700 border-orange-200"
                    : "bg-emerald-50 text-emerald-700 border-emerald-200"
                }`}
              >
                <Flame className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-stone-950">
                    Proactive Risk &amp; Deadline Rescue Inspector
                  </h2>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider border ${
                      riskAssessment.risk_level === "CRITICAL"
                        ? "bg-rose-50 text-rose-700 border-rose-200"
                        : riskAssessment.risk_level === "HIGH"
                        ? "bg-amber-50 text-amber-700 border-amber-200"
                        : riskAssessment.risk_level === "MEDIUM"
                        ? "bg-orange-50 text-orange-700 border-orange-200"
                        : "bg-emerald-50 text-emerald-700 border-emerald-200"
                    }`}
                  >
                    {riskAssessment.risk_level} Risk · {Math.round(riskAssessment.risk_score * 100)}%
                  </span>
                </div>
                <p className="text-xs text-stone-600 mt-0.5">
                  Multi-signal failure probability analysis & graph cascade evaluation.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="px-3 py-1.5 rounded-lg bg-stone-50 border border-stone-200 text-xs">
                <span className="text-stone-500 font-medium">Priority Score: </span>
                <span className="text-stone-800 font-bold font-mono">
                  {Math.round(riskAssessment.priority_score * 100)} / 100
                </span>
              </div>
              {riskAssessment.dependent_count > 0 && (
                <div className="px-3 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-xs font-semibold text-amber-800">
                  ⚡ Blocks {riskAssessment.dependent_count}{" "}
                  {riskAssessment.dependent_count === 1 ? "task" : "tasks"}
                </div>
              )}
            </div>
          </div>

          {/* Recommended Next Action Banner */}
          <div className="p-4 rounded-xl bg-orange-50/50 border border-orange-200 space-y-2">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-orange-100 text-orange-800 border border-orange-200">
                RECOMMENDED ACTION: {riskAssessment.action_type.replace(/_/g, " ")}
              </span>
            </div>
            <p className="text-sm font-semibold text-stone-900">
              {riskAssessment.recommended_action}
            </p>
          </div>

          {/* Multi-Signal Breakdown Meters */}
          <div className="space-y-3">
            <div className="text-xs uppercase tracking-wider font-semibold text-stone-600">
              Risk Component Breakdown:
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {/* Deadline Pressure */}
              <div className="p-3 rounded-xl bg-stone-50/60 border border-stone-200/80 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-stone-600">Deadline Urgency</span>
                  <span className="font-mono font-bold text-stone-800">
                    +{Math.round(riskAssessment.breakdown.deadline_pressure * 100)}%
                  </span>
                </div>
                <div className="w-full h-1.5 bg-stone-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-yellow-500 to-red-500"
                    style={{
                      width: `${Math.min(100, riskAssessment.breakdown.deadline_pressure * 250)}%`,
                    }}
                  />
                </div>
              </div>

              {/* Dependency Risk */}
              <div className="p-3 rounded-xl bg-stone-50/60 border border-stone-200/80 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-stone-600">Dependency Health</span>
                  <span className="font-mono font-bold text-stone-800">
                    +{Math.round(riskAssessment.breakdown.dependency_risk * 100)}%
                  </span>
                </div>
                <div className="w-full h-1.5 bg-stone-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-amber-500 to-orange-500"
                    style={{
                      width: `${Math.min(100, riskAssessment.breakdown.dependency_risk * 250)}%`,
                    }}
                  />
                </div>
              </div>

              {/* Progress Risk / Recency */}
              <div className="p-3 rounded-xl bg-stone-50/60 border border-stone-200/80 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-stone-600">Progress Evidence</span>
                  <span
                    className={`font-mono font-bold ${
                      riskAssessment.breakdown.progress_risk < 0
                        ? "text-emerald-700"
                        : "text-stone-800"
                    }`}
                  >
                    {riskAssessment.breakdown.progress_risk > 0 ? "+" : ""}
                    {Math.round(riskAssessment.breakdown.progress_risk * 100)}%
                  </span>
                </div>
                <div className="w-full h-1.5 bg-stone-200 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${
                      riskAssessment.breakdown.progress_risk < 0 ? "bg-emerald-500" : "bg-amber-500"
                    }`}
                    style={{
                      width: `${Math.min(
                        100,
                        Math.abs(riskAssessment.breakdown.progress_risk) * 300
                      )}%`,
                    }}
                  />
                </div>
              </div>

              {/* Ownership Clarity */}
              <div className="p-3 rounded-xl bg-stone-50/60 border border-stone-200/80 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-stone-600">Ownership Clarity</span>
                  <span className="font-mono font-bold text-stone-800">
                    +{Math.round(riskAssessment.breakdown.ownership_risk * 100)}%
                  </span>
                </div>
                <div className="w-full h-1.5 bg-stone-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-orange-600"
                    style={{
                      width: `${Math.min(100, riskAssessment.breakdown.ownership_risk * 500)}%`,
                    }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Active Risk Signals */}
          {riskAssessment.signals && riskAssessment.signals.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs uppercase tracking-wider font-semibold text-stone-600">
                Observed Risk Signals:
              </div>
              <div className="space-y-2">
                {riskAssessment.signals.map((sig, si) => (
                  <div
                    key={si}
                    className="p-3 rounded-xl bg-stone-50/60 border border-stone-200 flex flex-wrap items-center justify-between gap-3 text-xs"
                  >
                    <div className="flex items-center gap-2.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${
                          sig.severity === "CRITICAL"
                            ? "bg-rose-50 text-rose-700 border-rose-200"
                            : sig.severity === "HIGH"
                            ? "bg-amber-50 text-amber-700 border-amber-200"
                            : sig.severity === "MEDIUM"
                            ? "bg-orange-50 text-orange-700 border-orange-200"
                            : "bg-emerald-50 text-emerald-700 border-emerald-200"
                        }`}
                      >
                        {sig.severity}
                      </span>
                      <span className="font-mono text-stone-600">{sig.signal_type}</span>
                      <span className="text-stone-800">{sig.explanation}</span>
                    </div>

                    <span className="font-mono text-stone-500 text-[11px]">
                      Weight: {sig.contribution > 0 ? "+" : ""}
                      {sig.contribution.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Main Content Card */}
      {isEditing ? (
        /* Edit Form */
        <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-5">
          <h2 className="text-lg font-bold text-stone-950 pb-3 border-b border-stone-200">
            Edit Obligation
          </h2>
          <form onSubmit={handleSaveEdit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setEditType("OWED_BY_ME")}
                className={`p-3 rounded-xl border text-left text-xs font-semibold ${
                  editType === "OWED_BY_ME"
                    ? "bg-orange-50 border-orange-500 text-orange-950"
                    : "bg-stone-50 border-stone-200 text-stone-600"
                }`}
              >
                You Owe (Outgoing)
              </button>
              <button
                type="button"
                onClick={() => setEditType("OWED_TO_ME")}
                className={`p-3 rounded-xl border text-left text-xs font-semibold ${
                  editType === "OWED_TO_ME"
                    ? "bg-emerald-50 border-emerald-500 text-emerald-950"
                    : "bg-stone-50 border-stone-200 text-stone-600"
                }`}
              >
                Others Owe You (Incoming)
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-stone-700 mb-1">Owner</label>
                <input
                  type="text"
                  value={editOwner}
                  onChange={(e) => setEditOwner(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-stone-50 border border-stone-200 text-sm text-stone-900"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-stone-700 mb-1">Beneficiary</label>
                <input
                  type="text"
                  value={editBeneficiary}
                  onChange={(e) => setEditBeneficiary(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-stone-50 border border-stone-200 text-sm text-stone-900"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-stone-700 mb-1">Action</label>
              <textarea
                rows={2}
                value={editAction}
                onChange={(e) => setEditAction(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-stone-50 border border-stone-200 text-sm text-stone-900"
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-stone-700 mb-1">Deadline</label>
                <input
                  type="datetime-local"
                  value={editDeadline}
                  onChange={(e) => setEditDeadline(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-stone-50 border border-stone-200 text-sm text-stone-900"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-stone-700 mb-1">Conditions</label>
                <input
                  type="text"
                  value={editConditions}
                  onChange={(e) => setEditConditions(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-stone-50 border border-stone-200 text-sm text-stone-900"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-stone-700 mb-1">Next Action</label>
              <input
                type="text"
                value={editNextAction}
                onChange={(e) => setEditNextAction(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-stone-50 border border-stone-200 text-sm text-stone-900"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-stone-200">
              <button
                type="button"
                onClick={() => setIsEditing(false)}
                className="px-4 py-2 rounded-lg text-xs text-stone-600 hover:text-stone-800"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={updating}
                className="px-5 py-2 rounded-xl bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold shadow"
              >
                Save Changes
              </button>
            </div>
          </form>
        </div>
      ) : (
        /* Detailed View */
        <div className="bg-white border border-stone-200 rounded-2xl p-6 sm:p-8 shadow-sm space-y-8">
          {/* Header row */}
          <div className="flex flex-wrap items-start justify-between gap-4 pb-6 border-b border-stone-200">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-medium text-stone-600">
                <span className={`w-2.5 h-2.5 rounded-full ${isOwedByMe ? "bg-orange-500" : "bg-emerald-500"}`} />
                <span>
                  {isOwedByMe ? "Outgoing Commitment (You Owe)" : "Incoming Commitment (Others Owe You)"}
                </span>
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-stone-950 leading-snug">
                {obligation.action}
              </h1>
            </div>

            <div className="flex items-center gap-3">
              {obligation.is_at_risk && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200 animate-pulse">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  At Risk
                </span>
              )}
              <StatusBadge status={obligation.status} />
            </div>
          </div>

          {/* Reciprocal Parties Visualization */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-stone-50 border border-stone-200 space-y-1">
              <span className="text-[11px] font-semibold text-stone-600 uppercase tracking-wider">
                Duty Bearer (Owner)
              </span>
              <div className="text-base font-bold text-stone-900 flex items-center gap-2">
                <User className="w-4 h-4 text-orange-600" />
                <span>{obligation.owner}</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-stone-50 border border-stone-200 space-y-1">
              <span className="text-[11px] font-semibold text-stone-600 uppercase tracking-wider">
                Obligee (Beneficiary)
              </span>
              <div className="text-base font-bold text-stone-900 flex items-center gap-2">
                <User className="w-4 h-4 text-emerald-600" />
                <span>{obligation.beneficiary}</span>
              </div>
            </div>
          </div>

          {/* Temporal & Conditions Block */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-stone-50 border border-stone-200 space-y-1">
              <span className="text-[11px] font-semibold text-stone-600 uppercase tracking-wider">
                Deadline
              </span>
              <div className="text-sm font-semibold text-stone-800 flex items-center gap-2">
                <Clock className="w-4 h-4 text-amber-500" />
                <span>
                  {obligation.deadline
                    ? new Date(obligation.deadline).toLocaleString(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })
                    : "No deadline specified"}
                </span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-stone-50 border border-stone-200 space-y-1">
              <span className="text-[11px] font-semibold text-stone-600 uppercase tracking-wider">
                Conditions / Triggers
              </span>
              <div className="text-sm text-stone-700">
                {obligation.conditions ? (
                  <span className="text-amber-700 font-medium">{String(obligation.conditions)}</span>
                ) : (
                  <span className="text-stone-600 italic">None (Unconditional)</span>
                )}
              </div>
            </div>
          </div>

          {/* Next Action Callout */}
          {obligation.next_action && (
            <div className="p-4 rounded-xl bg-orange-50 border border-orange-200 space-y-1">
              <span className="text-[11px] font-semibold text-orange-700 uppercase tracking-wider">
                Immediate Next Step
              </span>
              <div className="text-sm text-stone-900 font-medium">{obligation.next_action}</div>
            </div>
          )}

          {/* Provenance & Confidence */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-stone-50 border border-stone-200 space-y-1">
              <span className="text-[11px] font-semibold text-stone-600 uppercase tracking-wider">
                Source Reference
              </span>
              <div className="text-xs text-stone-700">{obligation.source_ref || "Manual Input"}</div>
            </div>

            <div className="p-4 rounded-xl bg-stone-50 border border-stone-200 space-y-1">
              <span className="text-[11px] font-semibold text-stone-600 uppercase tracking-wider">
                AI Confidence Breakdown
              </span>
              <div>
                <ConfidenceBadge confidence={obligation.confidence} />
              </div>
            </div>
          </div>

          {/* PHASE 16: ORGANIZATIONAL MEMORY & HISTORICAL CONTEXT */}
          <div className="pt-2">
            <HistoricalContextCard obligationId={obligation.id} />
          </div>

          {/* PHASE 3: RELATIONSHIPS SECTION */}
          <div className="space-y-4 pt-6 border-t border-stone-200">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <h3 className="text-sm font-bold text-stone-950 flex items-center gap-2">
                  <GitFork className="w-4 h-4 text-orange-600" />
                  <span>Obligation Relationships &amp; Dependency Graph</span>
                </h3>
                <p className="text-[11px] text-stone-600">
                  Connected commitments, prerequisite blockers, and reciprocal dependencies.
                </p>
              </div>

              <button
                onClick={handleOpenAddEdgeModal}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-orange-50 hover:bg-orange-100 text-orange-700 border border-orange-200 text-xs font-semibold transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Relationship</span>
              </button>
            </div>

            {/* Prerequisites (Depends On) */}
            <div className="space-y-2">
              <span className="text-[11px] font-bold text-stone-600 uppercase tracking-wider">
                Prerequisites (This depends on):
              </span>
              {!graph || graph.dependencies.length === 0 ? (
                <div className="p-3 rounded-xl bg-stone-50/60 border border-stone-200/60 text-xs text-stone-500 italic">
                  No prerequisite dependencies. This obligation can proceed independently.
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {graph.dependencies.map((dep) => (
                    <Link
                      key={dep.id}
                      href={`/obligations/${dep.id}`}
                      className="p-3.5 rounded-xl bg-stone-50 border border-stone-200 hover:border-stone-300 transition-all space-y-1.5 block group"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-stone-700 group-hover:text-orange-600 transition-colors">
                          {dep.owner}
                        </span>
                        <StatusBadge status={dep.status} />
                      </div>
                      <p className="text-xs text-stone-800 font-medium line-clamp-2">{dep.action}</p>
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {/* Dependents (Completing This Unblocks) */}
            <div className="space-y-2 pt-2">
              <span className="text-[11px] font-bold text-stone-600 uppercase tracking-wider">
                Dependents (Completing this unblocks):
              </span>
              {!graph || graph.dependents.length === 0 ? (
                <div className="p-3 rounded-xl bg-stone-50/60 border border-stone-200/60 text-xs text-stone-500 italic">
                  No other obligations depend on this deliverable.
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {graph.dependents.map((dep) => (
                    <Link
                      key={dep.id}
                      href={`/obligations/${dep.id}`}
                      className="p-3.5 rounded-xl bg-stone-50 border border-stone-200 hover:border-stone-300 transition-all space-y-1.5 block group"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-stone-700 group-hover:text-emerald-400 transition-colors">
                          {dep.owner}
                        </span>
                        <StatusBadge status={dep.status} />
                      </div>
                      <p className="text-xs text-stone-800 font-medium line-clamp-2">{dep.action}</p>
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {/* Linked / Reciprocal Obligations */}
            <div className="space-y-2 pt-2">
              <span className="text-[11px] font-bold text-stone-600 uppercase tracking-wider">
                Linked & Reciprocal Commitments:
              </span>
              {!graph || graph.linked.length === 0 ? (
                <div className="p-3 rounded-xl bg-stone-50/60 border border-stone-200/60 text-xs text-stone-500 italic">
                  No linked reciprocal obligations.
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {graph.linked.map((link) => (
                    <Link
                      key={link.id}
                      href={`/obligations/${link.id}`}
                      className="p-3.5 rounded-xl bg-orange-50/40 border border-orange-200 hover:border-orange-300 transition-all space-y-1.5 block group"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-stone-900 group-hover:text-orange-600 transition-colors flex items-center gap-1.5">
                          <LinkIcon className="w-3 h-3 text-orange-600" />
                          <span>{link.owner}</span>
                        </span>
                        <StatusBadge status={link.status} />
                      </div>
                      <p className="text-xs text-stone-800 font-medium line-clamp-2">{link.action}</p>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* PHASE 6: HUMAN-CONTROLLED INTERVENTIONS & FOLLOW-UP HISTORY */}
          <div className="bg-stone-100/80 border border-stone-200 rounded-2xl p-6 space-y-4 shadow-md">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-0.5">
                <h3 className="text-sm font-bold text-stone-950 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-amber-400" />
                  <span>Interventions & Follow-Up History ({interventions.length})</span>
                </h3>
                <p className="text-[11px] text-stone-600">
                  Human-authorized follow-up drafts, scheduled check-ins, and execution tracking.
                </p>
              </div>

              {obligation.status !== "COMPLETED" && (
                <button
                  onClick={handlePlanIntervention}
                  disabled={planningIntervention}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-stone-50 text-xs font-bold transition-all shadow-md shadow-amber-500/20 active:scale-95 disabled:opacity-50"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{planningIntervention ? "Planning..." : "⚡ Plan Follow-Up"}</span>
                </button>
              )}
            </div>

            {interventions.length === 0 ? (
              <div className="p-4 rounded-xl bg-stone-50/60 border border-stone-200/60 text-xs text-stone-600 italic">
                No interventions planned or executed yet for this commitment.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3">
                {interventions.map((inv) => (
                  <InterventionCard
                    key={inv.id}
                    intervention={inv}
                    onReview={(targetInv) => {
                      setSelectedIntervention(targetInv);
                      setShowInterventionModal(true);
                    }}
                    onExecute={async (targetInv) => {
                      try {
                        const updated = await interventionsApi.execute(targetInv.id);
                        toast({
                          type: "success",
                          title: "Executed in Simulation Mode",
                          description: `Follow-up simulated (Ref: ${updated.execution_reference}). No external messages sent.`,
                        });
                        loadData();
                      } catch (err) {
                        toast({
                          type: "error",
                          title: "Execution Failed",
                          description: err instanceof Error ? err.message : "Failed to execute.",
                        });
                      }
                    }}
                  />
                ))}
              </div>
            )}
          </div>

          {/* PHASE 10: TEMPORAL CONTEXT & RELATED MEETINGS */}
          {(() => {
            const calendarEvs = evidenceList.filter(
              (e) =>
                e.source_type === "google_calendar" ||
                (e.extra_metadata && (e.extra_metadata as Record<string, unknown>).source_provider === "google_calendar")
            );
            if (calendarEvs.length === 0) return null;

            return (
              <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="space-y-0.5">
                    <h3 className="text-sm font-bold text-stone-950 flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-orange-600" />
                      <span>Temporal Context &amp; Related Meetings ({calendarEvs.length})</span>
                    </h3>
                    <p className="text-[11px] text-stone-600">
                      Observed Google Calendar meetings correlating with this commitment.
                    </p>
                  </div>
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-orange-50 text-orange-700 border border-orange-200">
                    Temporal Intelligence Active
                  </span>
                </div>

                <div className="grid grid-cols-1 gap-3">
                  {calendarEvs.map((cev) => {
                    const cmeta = (cev.extra_metadata as Record<string, unknown>) || {};
                    const mStatus = (cmeta.meeting_status as string) || "MEETING_SCHEDULED";
                    const startTime = cmeta.start_time as string | undefined;
                    const attendees = (cmeta.attendees as string[]) || [];
                    const summary = (cmeta.summary as string) || "Calendar Event";
                    const organizer = (cmeta.organizer as string) || "Unknown";

                    return (
                      <div
                        key={cev.id}
                        className="p-4 rounded-xl bg-stone-50/70 border border-stone-200 space-y-2.5 text-xs"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span
                              className={`px-2 py-0.5 rounded-full font-bold uppercase text-[10px] ${
                                mStatus === "MEETING_COMPLETED"
                                  ? "bg-slate-100 text-slate-700 border border-slate-200"
                                  : mStatus === "MEETING_CANCELLED"
                                  ? "bg-rose-50 text-rose-700 border border-rose-200"
                                  : mStatus === "MEETING_RESCHEDULED"
                                  ? "bg-amber-50 text-amber-700 border border-amber-200"
                                  : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              }`}
                            >
                              {mStatus.replace("MEETING_", "")}
                            </span>
                            <span className="font-semibold text-stone-800">
                              {summary}
                            </span>
                          </div>

                          {startTime && (
                            <span className="text-stone-600 flex items-center gap-1 font-mono text-[11px]">
                              <Clock className="w-3 h-3 text-stone-500" />
                              {new Date(startTime).toLocaleString(undefined, {
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </span>
                          )}
                        </div>

                        <p className="text-stone-700 bg-white p-2.5 rounded-lg border border-stone-200">
                          {cev.content}
                        </p>

                        <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-stone-600">
                          <span>
                            Organizer: <strong className="text-stone-700">{cev.actor || organizer}</strong>
                          </span>
                          {attendees.length > 0 && (
                            <span>
                              Attendees: <strong className="text-stone-700">{attendees.join(", ")}</strong>
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>

                <p className="text-[11px] text-stone-600 italic">
                  Note: Calendar meetings provide temporal context and meeting proximity signals to the Risk Engine. They do not automatically overwrite this obligation&apos;s deadline or mark it completed without human approval.
                </p>
              </div>
            );
          })()}

          {/* PHASE 11: CROSS-PROVIDER EVIDENCE RECONCILIATION */}
          {reconciliation && (
            <div
              className={`border rounded-2xl p-6 space-y-4 shadow-sm transition-all ${
                reconciliation.status === "CONFLICTING"
                  ? "bg-rose-50/40 border-rose-200"
                  : reconciliation.status === "CONSISTENT"
                  ? "bg-emerald-50/40 border-emerald-200"
                  : "bg-white border-stone-200"
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <h3 className="text-sm font-bold text-stone-950 flex items-center gap-2">
                    <Scale className="w-4 h-4 text-orange-600" />
                    <span>Cross-Provider Reconciliation &amp; Contradiction Status</span>
                  </h3>
                  <p className="text-[11px] text-stone-600">
                    Continuous cross-source consistency analysis synthesized across Slack, Gmail, and Google Calendar.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${
                      reconciliation.status === "CONFLICTING"
                        ? "bg-rose-50 text-rose-700 border border-rose-200"
                        : reconciliation.status === "CONSISTENT"
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : "bg-amber-50 text-amber-700 border border-amber-200"
                    }`}
                  >
                    {reconciliation.status.replace("_", " ")}
                  </span>
                  <button
                    onClick={() => setShowReconciliationModal(true)}
                    className="px-3 py-1 bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-all"
                  >
                    Adjudicate Decision
                  </button>
                </div>
              </div>

              {/* Consistency vs Contradiction Meters */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                <div className="p-3 bg-stone-50 rounded-xl border border-stone-200 space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-stone-600">Consistency Score</span>
                    <span className="text-emerald-700 font-bold">
                      {(reconciliation.consistency_score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="w-full bg-stone-200 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-emerald-500 h-1.5 rounded-full"
                      style={{ width: `${Math.min(100, reconciliation.consistency_score * 100)}%` }}
                    />
                  </div>
                </div>

                <div className="p-3 bg-stone-50 rounded-xl border border-stone-200 space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-stone-600">Contradiction Score</span>
                    <span className="text-rose-700 font-bold">
                      {(reconciliation.contradiction_score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="w-full bg-stone-200 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-rose-500 h-1.5 rounded-full"
                      style={{ width: `${Math.min(100, reconciliation.contradiction_score * 100)}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Finding notes */}
              {reconciliation.explanation && reconciliation.explanation.length > 0 && (
                <div className="p-3 bg-stone-50 rounded-xl border border-stone-200 text-xs text-stone-700 space-y-1">
                  <span className="text-stone-600 font-medium text-[11px] uppercase tracking-wider block mb-1">
                    Intelligence Findings:
                  </span>
                  {reconciliation.explanation.map((exp: string, idx: number) => (
                    <p key={idx} className="text-stone-700 flex items-start gap-1.5">
                      <span className="text-orange-600 font-mono">•</span>
                      <span>{exp}</span>
                    </p>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between text-xs text-stone-600 pt-1">
                <span>
                  Recommended Action: <strong className="text-stone-900 font-semibold">{reconciliation.recommended_action || "REVIEW"}</strong>
                </span>
                <Link
                  href={`/reconciliation/${reconciliation.id}`}
                  className="text-orange-600 hover:text-orange-700 font-medium flex items-center gap-1"
                >
                  <span>Full Evidence Timeline &rarr;</span>
                </Link>
              </div>
            </div>
          )}

          {/* PHASE 12: PREDICTIVE INTELLIGENCE & PATTERN LEARNING */}
          {prediction && (
            <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-6 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="w-8 h-8 rounded-lg bg-orange-50 border border-orange-200 flex items-center justify-center text-orange-600">
                      <Brain className="w-4 h-4" />
                    </span>
                    <div>
                      <h3 className="text-sm font-bold text-stone-950 flex items-center gap-2">
                        <span>Predictive Intelligence &amp; Pattern Learning</span>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-orange-50 text-orange-700 border border-orange-200">
                          {prediction.model_version}
                        </span>
                      </h3>
                      <p className="text-[11px] text-stone-600">
                        Historical pattern learning, explainable delay forecasting, and calibrated predictive signals.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-xl font-bold font-mono text-stone-900">
                    {Math.round(prediction.failure_probability * 100)}% Failure Prob.
                  </div>
                  <div className="text-[11px] text-stone-600">
                    Confidence: {Math.round(prediction.confidence * 100)}%
                  </div>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-medium text-stone-600">
                  <span className="text-emerald-700 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Completion Likelihood: {Math.round(prediction.completion_probability * 100)}%
                  </span>
                  <span className="text-rose-700 flex items-center gap-1">
                    <AlertCircle className="w-3.5 h-3.5" />
                    Failure / Delay Likelihood: {Math.round(prediction.failure_probability * 100)}%
                  </span>
                </div>
                <div className="w-full bg-stone-200 rounded-full h-2 overflow-hidden flex">
                  <div
                    className="bg-rose-500 h-full transition-all duration-500"
                    style={{ width: `${Math.round(prediction.failure_probability * 100)}%` }}
                  />
                </div>
              </div>

              {/* Projections Matrix */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3 bg-stone-50/60 rounded-xl border border-stone-200 space-y-1">
                  <div className="text-[11px] text-stone-600">Expected Delay Latency</div>
                  <div className="text-base font-bold text-amber-700 font-mono">
                    {prediction.expected_delay_hours > 0 ? `+${prediction.expected_delay_hours}h` : "On Schedule"}
                  </div>
                  <div className="text-[10px] text-stone-500">Derived from historical priors</div>
                </div>

                <div className="p-3 bg-stone-50/60 rounded-xl border border-stone-200 space-y-1">
                  <div className="text-[11px] text-stone-600">Intervention Likelihood</div>
                  <div className="text-base font-bold text-orange-600 font-mono">
                    {Math.round(prediction.intervention_likelihood * 100)}%
                  </div>
                  <div className="text-[10px] text-stone-500">Likely to need check-in</div>
                </div>

                <div className="p-3 bg-stone-50/60 rounded-xl border border-stone-200 space-y-1">
                  <div className="text-[11px] text-stone-600">Blockage Risk</div>
                  <div className="text-base font-bold text-rose-700 font-mono">
                    {Math.round(prediction.blockage_likelihood * 100)}%
                  </div>
                  <div className="text-[10px] text-stone-500">Prerequisite bottleneck risk</div>
                </div>
              </div>

              {/* Explainable Causal Reasons */}
              {prediction.reasons && prediction.reasons.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-stone-700 uppercase tracking-wider">
                    Explainable Predictive Signals (Why?):
                  </div>
                  <div className="space-y-1.5">
                    {prediction.reasons.map((r, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2.5 p-2.5 rounded-lg bg-stone-50 border border-stone-200 text-xs"
                      >
                        <span
                          className={`font-mono text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0 ${
                            r.impact > 0 ? "bg-orange-50 text-orange-700 border border-orange-200" : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          }`}
                        >
                          {r.impact > 0 ? `+${r.impact}` : r.impact}
                        </span>
                        <span className="text-stone-700 leading-relaxed">{r.explanation}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Owner Context Insights */}
              {ownerContext && ownerContext.total_obligations >= 2 && (
                <div className="p-3 bg-stone-50/40 rounded-xl border border-stone-200 text-xs space-y-1.5">
                  <div className="flex items-center justify-between text-stone-700">
                    <span className="font-semibold">Owner Delivery Profile ({ownerContext.owner}):</span>
                    <span className="text-[10px] text-stone-600">
                      {Math.round(ownerContext.on_time_rate * 100)}% On-Time • Avg Delay: ~{ownerContext.avg_delay_hours}h
                    </span>
                  </div>
                  <p className="text-stone-600 text-[11px]">{ownerContext.insights[0]}</p>
                </div>
              )}

              {/* Similar Past Obligations */}
              {similarObligations.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-stone-200/80">
                  <div className="text-xs font-semibold text-stone-700 uppercase tracking-wider flex items-center justify-between">
                    <span>Historically Similar Commitments ({similarObligations.length}):</span>
                    <span className="text-[10px] text-stone-500 font-normal">Ranked by feature similarity</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {similarObligations.map((sim) => (
                      <div
                        key={sim.obligation_id}
                        className="p-3 bg-stone-50/40 rounded-lg border border-stone-200 text-xs space-y-1.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-stone-800 truncate max-w-[180px]">
                            {sim.owner}
                          </span>
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                              sim.outcome_type.includes("ON_TIME")
                                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                : "bg-amber-50 text-amber-700 border-amber-200"
                            }`}
                          >
                            {sim.outcome_type.replace(/_/g, " ")}
                          </span>
                        </div>
                        <p className="text-stone-600 line-clamp-1">{sim.action}</p>
                        <div className="text-[10px] text-stone-500">
                          Similarity: {Math.round(sim.similarity_score * 100)}% • {sim.shared_features[0] || "Shared pattern"}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* PHASE 13: MODEL COMPARISON BREAKDOWN */}
              {modelComparison && (
                <div className="space-y-3 pt-3 border-t border-stone-200">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold text-stone-800 uppercase tracking-wider flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-orange-600" />
                      <span>Model Comparison: predictive-v1 vs adaptive-v1</span>
                    </h4>
                    <span className="text-[11px] font-mono text-orange-700 bg-orange-50 px-2 py-0.5 rounded border border-orange-200">
                      Variance: {modelComparison.probability_variance >= 0 ? `+${(modelComparison.probability_variance * 100).toFixed(1)}%` : `${(modelComparison.probability_variance * 100).toFixed(1)}%`}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="p-3 bg-stone-50 rounded-xl border border-stone-200 space-y-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-semibold text-stone-700">predictive-v1 (Baseline)</span>
                        <span className="font-mono text-stone-600">
                          {Math.round(modelComparison.predictive_v1.failure_probability * 100)}% Failure
                        </span>
                      </div>
                      <div className="text-[11px] text-stone-500">
                        Expected Delay: ~{modelComparison.predictive_v1.expected_delay_hours}h • Conf: {Math.round(modelComparison.predictive_v1.confidence * 100)}%
                      </div>
                    </div>

                    <div className="p-3 bg-orange-50/50 rounded-xl border border-orange-200 space-y-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-semibold text-orange-700">adaptive-v1 (Calibrated)</span>
                        <span className="font-mono text-orange-600 font-bold">
                          {Math.round(modelComparison.adaptive_v1.failure_probability * 100)}% Failure
                        </span>
                      </div>
                      <div className="text-[11px] text-stone-600">
                        Expected Delay: ~{modelComparison.adaptive_v1.expected_delay_hours}h • Conf: {Math.round(modelComparison.adaptive_v1.confidence * 100)}%
                      </div>
                    </div>
                  </div>

                  {modelComparison.adjustment_reasons.length > 0 && (
                    <div className="p-2.5 bg-stone-50 rounded-lg text-[11px] text-stone-600 space-y-0.5 border border-stone-200">
                      {modelComparison.adjustment_reasons.map((r, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-stone-700">
                          <span className="text-orange-600">•</span>
                          <span>{r}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* PHASE 13: PREDICTION HISTORY TIMELINE */}
              {predictionHistory.length > 0 && (
                <div className="space-y-3 pt-3 border-t border-stone-200">
                  <h4 className="text-xs font-semibold text-stone-800 uppercase tracking-wider flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-orange-600" />
                    <span>Prediction & Feedback History ({predictionHistory.length})</span>
                  </h4>

                  <div className="space-y-2">
                    {predictionHistory.map((item) => (
                      <div
                        key={item.prediction_id}
                        className="p-3 bg-stone-50/40 rounded-xl border border-stone-200 text-xs flex flex-wrap items-center justify-between gap-2"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-stone-800 font-semibold">{item.model_version}</span>
                            <span className="text-stone-500 text-[10px]">
                              {new Date(item.predicted_at).toLocaleString()}
                            </span>
                          </div>
                          <div className="text-[11px] text-stone-600 mt-0.5">
                            Failure Prob: <span className="text-stone-800 font-mono font-semibold">{Math.round(item.failure_probability * 100)}%</span> •
                            Exp Delay: <span className="text-amber-700 font-mono">~{item.expected_delay_hours}h</span>
                          </div>
                        </div>

                        {item.observed_outcome && (
                          <div className="text-right text-[11px]">
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-stone-200 text-stone-700">
                              Observed: {item.observed_outcome}
                            </span>
                            {item.prediction_error !== null && item.prediction_error !== undefined && (
                              <div className="text-[10px] text-stone-500 mt-0.5">
                                Error: {item.prediction_error.toFixed(2)}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Preventative Advisory Recommendation */}
              <div className="p-3.5 bg-[#FFF7ED] rounded-xl border border-[#FED7AA] flex items-start gap-3 text-xs">
                <ShieldAlert className="w-4 h-4 text-orange-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-stone-900">
                    Recommended Preventative Action:
                  </div>
                  <div className="text-stone-800 mt-0.5">
                    {prediction.preventative_recommendation || "Maintain standard monitoring."}
                  </div>
                  <div className="text-[10px] text-stone-500 mt-1 italic">
                    Safety Invariant: Predictive intelligence is strictly advisory. It never automatically completes obligations or alters lifecycle states.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* PHASE 4: EVIDENCE & CONTINUITY TIMELINE */}
          <div className="space-y-4 pt-6 border-t border-stone-200">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <h3 className="text-sm font-bold text-stone-950 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  <span>Evidence & Continuity Timeline ({evidenceList.length})</span>
                </h3>
                <p className="text-[11px] text-stone-600">
                  Chronological record of observed messages, progress updates, and completion evidence.
                </p>
              </div>

              {obligation.status !== "COMPLETED" && (
                <button
                  onClick={() => setShowEvidenceModal(true)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-800 text-xs font-semibold transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Attach Manual Note</span>
                </button>
              )}
            </div>

            {evidenceList.length === 0 ? (
              <div className="p-4 rounded-xl bg-stone-50/60 border border-stone-200/60 text-xs text-stone-600 italic">
                No observations or evidence recorded yet. External messages correlating with this task will appear here.
              </div>
            ) : (
              <div className="space-y-3 relative before:absolute before:left-3 before:top-3 before:bottom-3 before:w-0.5 before:bg-stone-200">
                {evidenceList.map((ev) => (
                  <div
                    key={ev.id}
                    className="pl-8 relative space-y-1.5 text-xs"
                  >
                    {/* Timeline dot */}
                    <div
                      className={`absolute left-1.5 top-1.5 w-3 h-3 rounded-full border-2 bg-stone-50 ${
                        ev.correlation_status === "CONFIRMED"
                          ? "border-emerald-400"
                          : ev.correlation_status === "REJECTED"
                          ? "border-rose-400"
                          : "border-amber-500"
                      }`}
                    />

                    <div className="p-3.5 rounded-xl bg-stone-50 border border-stone-200 space-y-2">
                      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded font-bold uppercase text-[10px] ${
                              ev.correlation_status === "CONFIRMED"
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : ev.correlation_status === "REJECTED"
                                ? "bg-rose-50 text-rose-700 border border-rose-200"
                                : "bg-orange-50 text-orange-700 border border-orange-200"
                            }`}
                          >
                            {ev.correlation_status}
                          </span>
                          <span className="text-stone-700 font-semibold">{ev.actor || "Actor"}</span>
                          <span className="text-stone-500">•</span>
                          <span className="text-stone-600 capitalize">{ev.source_type}</span>
                        </div>
                        <span className="text-stone-500">
                          {new Date(ev.observed_at).toLocaleString(undefined, {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>

                      <p className="text-stone-800 font-medium">&ldquo;{ev.content}&rdquo;</p>

                      {ev.reasoning && Array.isArray(ev.reasoning) && ev.reasoning.length > 0 && (
                        <div className="text-[11px] text-stone-600 space-y-0.5 pt-1 border-t border-stone-100">
                          {ev.reasoning.map((r, idx) => (
                            <div key={idx} className="flex items-center gap-1.5">
                              <span className="text-stone-400">•</span>
                              <span>{r}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* PHASE 14: ROOT-CAUSE ANALYSIS, IMPACT BLAST RADIUS & RESOLUTION PLANNING */}
          {rootCause && (
            <div className="space-y-4 pt-6 border-t border-stone-200">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="space-y-0.5">
                  <h3 className="text-sm font-bold text-stone-950 flex items-center gap-2">
                    <Brain className="w-4 h-4 text-orange-600" />
                    <span>Causal Root-Cause & Blast Radius Intelligence</span>
                  </h3>
                  <p className="text-[11px] text-stone-600">
                    Upstream graph causality, multi-signal attribution, and critical path risk reasoning.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-orange-50 text-orange-700 border border-orange-200">
                    Causal Confidence: {Math.round(rootCause.confidence * 100)}% ({rootCause.confidence_level})
                  </span>
                </div>
              </div>

              {/* Primary Cause Card */}
              <div className="p-4 rounded-xl bg-white border border-stone-200 space-y-2 shadow-sm">
                <div className="flex items-center justify-between">
                  <div className="text-[11px] font-semibold text-orange-600 uppercase tracking-wider flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5" />
                    <span>Primary Root Cause</span>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-orange-50 text-orange-700 border border-orange-200">
                    {rootCause.root_cause_type}
                  </span>
                </div>
                <div className="text-sm font-bold text-stone-950">{rootCause.primary_root_cause}</div>
                <p className="text-xs text-stone-600 leading-relaxed">{rootCause.overall_explanation}</p>
              </div>

              {/* Impact & Blast Radius Grid */}
              {impact && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3 rounded-xl bg-white border border-stone-200 space-y-0.5 shadow-sm">
                    <div className="text-[10px] text-stone-500 uppercase tracking-wider">Impact Score</div>
                    <div className="text-xl font-bold font-mono text-orange-600">
                      {impact.impact_score.toFixed(2)}
                    </div>
                    <div className="text-[10px] text-stone-600 uppercase">{impact.impact_level} Blast Radius</div>
                  </div>

                  <div className="p-3 rounded-xl bg-white border border-stone-200 space-y-0.5 shadow-sm">
                    <div className="text-[10px] text-stone-500 uppercase tracking-wider">Downstream Total</div>
                    <div className="text-xl font-bold font-mono text-stone-900">
                      {impact.total_downstream_dependents_count}
                    </div>
                    <div className="text-[10px] text-stone-600">Commitments affected</div>
                  </div>

                  <div className="p-3 rounded-xl bg-white border border-stone-200 space-y-0.5 shadow-sm">
                    <div className="text-[10px] text-stone-500 uppercase tracking-wider">Max Depth</div>
                    <div className="text-xl font-bold font-mono text-stone-900">
                      {impact.maximum_dependency_depth}
                    </div>
                    <div className="text-[10px] text-stone-600">Hops downstream</div>
                  </div>

                  <div className="p-3 rounded-xl bg-white border border-stone-200 space-y-0.5 shadow-sm">
                    <div className="text-[10px] text-stone-500 uppercase tracking-wider">Affected Owners</div>
                    <div className="text-xl font-bold font-mono text-stone-900">
                      {impact.affected_owners.length}
                    </div>
                    <div className="text-[10px] text-stone-600">Team members</div>
                  </div>
                </div>
              )}

              {/* Critical Path & Highest-Leverage Resolution */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* Critical Path Card */}
                {criticalPath && (
                  <div className="p-4 rounded-xl bg-white border border-stone-200 space-y-2 shadow-sm">
                    <div className="text-xs font-bold text-stone-800 flex items-center gap-1.5">
                      <Route className="w-3.5 h-3.5 text-orange-600" />
                      <span>Critical Dependency Path ({criticalPath.critical_path_length} hops)</span>
                    </div>
                    <p className="text-[11px] text-stone-600">{criticalPath.explanation}</p>
                    {criticalPath.root_blocker_action && (
                      <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-[11px] space-y-0.5">
                        <div className="text-[10px] font-bold text-rose-700 uppercase tracking-wider">Root Upstream Blocker</div>
                        <div className="text-stone-900 font-semibold">{criticalPath.root_blocker_action}</div>
                        <div className="text-stone-600 text-[10px]">Owner: {criticalPath.root_blocker_owner}</div>
                      </div>
                    )}
                  </div>
                )}

                {/* Resolution Recommendation */}
                {resolutionPlan && (
                  <div className="p-4 rounded-xl bg-orange-50 border border-orange-200 space-y-2 shadow-sm">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-bold text-orange-900 flex items-center gap-1.5">
                        <Play className="w-3.5 h-3.5 text-orange-600" />
                        <span>Upstream Resolution Plan</span>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-white text-orange-700 border border-orange-200">
                        {resolutionPlan.strategy}
                      </span>
                    </div>
                    <div className="text-xs font-semibold text-stone-900">
                      Target: {resolutionPlan.target_action} ({resolutionPlan.target_owner})
                    </div>
                    <p className="text-[11px] text-stone-700 leading-relaxed">{resolutionPlan.rationale}</p>
                    <div className="text-[10px] text-orange-700 font-mono font-medium">
                      Expected Impact: {resolutionPlan.expected_impact}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* PHASE 15: ENTERPRISE AUDIT & GOVERNANCE PROVENANCE TIMELINE */}
          <div className="space-y-4 pt-6 border-t border-stone-200">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <h3 className="text-sm font-bold text-stone-950 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-orange-600" />
                  <span>Authoritative Audit &amp; Provenance History ({auditTrail.length})</span>
                </h3>
                <p className="text-[11px] text-stone-600">
                  Cryptographic SHA-256 hash-chained lifecycle record with operator attribution &amp; zero-secret state diffs.
                </p>
              </div>

              <Link
                href="/audit"
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-stone-200 hover:bg-stone-300 text-stone-700 hover:text-stone-950 text-xs font-semibold transition-colors"
              >
                <span>Governance Center</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>

            {auditTrail.length === 0 ? (
              <div className="p-4 rounded-xl bg-stone-50/60 border border-stone-200/60 text-xs text-stone-500 italic">
                No audit events recorded for this obligation yet.
              </div>
            ) : (
              <div className="space-y-3 relative before:absolute before:left-3 before:top-3 before:bottom-3 before:w-0.5 before:bg-stone-200">
                {auditTrail.map((item) => (
                  <div key={item.id} className="pl-8 relative space-y-2 text-xs">
                    {/* Timeline dot */}
                    <div className="absolute left-1.5 top-2 -translate-x-1/2 w-3.5 h-3.5 rounded-full border-2 border-orange-500 bg-white" />

                    <div className="p-4 rounded-xl bg-stone-50/80 border border-stone-200/80 space-y-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-stone-100 text-stone-700 border border-stone-200 font-mono">
                            {item.action}
                          </span>
                          <span className="text-stone-600 font-semibold">
                            {item.actor_name || (item.source === "SYSTEM_WORKER" ? "System Worker" : "Anonymous")}
                          </span>
                          {item.actor_role && (
                            <span className="px-1.5 py-0.2 rounded text-[10px] bg-stone-200 text-stone-600 border border-stone-300">
                              {item.actor_role}
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-2 font-mono text-[11px] text-stone-500">
                          <Clock className="w-3 h-3" />
                          <span>{new Date(item.timestamp).toLocaleString()}</span>
                        </div>
                      </div>

                      {item.reason && (
                        <p className="text-stone-700 italic text-[11px]">&ldquo;{item.reason}&rdquo;</p>
                      )}

                      {/* State Changes Diff (if present) */}
                      {(item.before_state || item.after_state) && (
                        <div className="p-2.5 rounded-lg bg-stone-100/90 border border-stone-200/60 space-y-1.5 text-[11px] font-mono">
                          {item.before_state && (
                            <div className="text-stone-600">
                              <span className="text-stone-500 font-sans">Before: </span>
                              <span>{JSON.stringify(item.before_state)}</span>
                            </div>
                          )}
                          {item.after_state && (
                            <div className="text-emerald-400">
                              <span className="text-stone-500 font-sans">After: </span>
                              <span>{JSON.stringify(item.after_state)}</span>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Cryptographic SHA-256 Provenance Proof */}
                      <div className="flex items-center justify-between pt-1 border-t border-stone-100 text-[10px] font-mono text-stone-500">
                        <div className="flex items-center gap-1.5 text-emerald-400/80">
                          <Shield className="w-3 h-3" />
                          <span>Hash: {item.event_hash.slice(0, 16)}...</span>
                        </div>
                        {item.request_id && (
                          <span>Req: {item.request_id.slice(0, 12)}...</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Controlled Status Transition Action Bar */}
          <div className="pt-6 border-t border-stone-200 space-y-3">
            <span className="text-[11px] font-semibold text-stone-600 uppercase tracking-wider block">
              Controlled State Machine Actions
            </span>

            <div className="flex flex-wrap items-center gap-2.5">
              {/* If CONFIRMED */}
              {obligation.status === "CONFIRMED" && (
                <>
                  <button
                    onClick={() => handleStatusChange("IN_PROGRESS")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold shadow-sm active:scale-95 transition-all"
                  >
                    <PlayCircle className="w-4 h-4" />
                    <span>Start Work (In Progress)</span>
                  </button>
                  <button
                    onClick={() => setShowEvidenceModal(true)}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-sm active:scale-95 transition-all"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Complete &amp; Attach Evidence</span>
                  </button>
                  <button
                    onClick={() => handleStatusChange("BLOCKED")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-stone-100 hover:bg-stone-200 border border-stone-200 text-stone-700 text-xs font-medium transition-colors"
                  >
                    <span>Mark Blocked</span>
                  </button>
                  <button
                    onClick={() => handleStatusChange("CANCELLED")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-stone-100 hover:bg-stone-200 border border-stone-200 text-stone-600 hover:text-stone-800 text-xs font-medium transition-colors"
                  >
                    <span>Cancel Obligation</span>
                  </button>
                </>
              )}

              {/* If IN_PROGRESS */}
              {obligation.status === "IN_PROGRESS" && (
                <>
                  <button
                    onClick={() => setShowEvidenceModal(true)}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-sm active:scale-95 transition-all"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Complete &amp; Attach Evidence</span>
                  </button>
                  <button
                    onClick={() => handleStatusChange("BLOCKED")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-stone-100 hover:bg-stone-200 border border-stone-200 text-stone-700 text-xs font-medium transition-colors"
                  >
                    <span>Mark Blocked</span>
                  </button>
                  <button
                    onClick={() => handleStatusChange("CANCELLED")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-stone-100 hover:bg-stone-200 border border-stone-200 text-stone-600 hover:text-stone-800 text-xs font-medium transition-colors"
                  >
                    <span>Cancel Obligation</span>
                  </button>
                </>
              )}

              {/* If BLOCKED */}
              {obligation.status === "BLOCKED" && (
                <>
                  <button
                    onClick={() => handleStatusChange("IN_PROGRESS")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold shadow-sm transition-all"
                  >
                    <PlayCircle className="w-4 h-4" />
                    <span>Override &amp; Resume (In Progress)</span>
                  </button>
                  <button
                    onClick={() => handleStatusChange("CONFIRMED")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-stone-100 hover:bg-stone-200 border border-stone-200 text-stone-700 text-xs font-medium transition-colors"
                  >
                    <Unlock className="w-3.5 h-3.5" />
                    <span>Return to Confirmed</span>
                  </button>
                </>
              )}

              {/* If OVERDUE */}
              {obligation.status === "OVERDUE" && (
                <>
                  <button
                    onClick={() => handleStatusChange("IN_PROGRESS")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold shadow-sm transition-all"
                  >
                    <PlayCircle className="w-4 h-4" />
                    <span>Work on Overdue Item</span>
                  </button>
                  <button
                    onClick={() => setShowEvidenceModal(true)}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-sm transition-all"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Complete Now</span>
                  </button>
                </>
              )}

              {/* If COMPLETED */}
              {obligation.status === "COMPLETED" && (
                <button
                  onClick={() => handleStatusChange("IN_PROGRESS")}
                  disabled={updating}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-stone-200 hover:bg-stone-300 text-stone-700 text-xs font-medium transition-colors"
                >
                  <span>Reopen Obligation (In Progress)</span>
                </button>
              )}

              {/* If CANCELLED */}
              {obligation.status === "CANCELLED" && (
                <button
                  onClick={() => handleStatusChange("CONFIRMED")}
                  disabled={updating}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-stone-200 hover:bg-stone-300 text-stone-700 text-xs font-medium transition-colors"
                >
                  <span>Reactivate Obligation</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Add Relationship Modal */}
      {showAddEdgeModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-white border border-stone-200 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <h3 className="text-base font-bold text-stone-950 flex items-center gap-2">
                <GitFork className="w-5 h-5 text-orange-600" />
                <span>Connect Obligation Relationship</span>
              </h3>
              <button
                onClick={() => setShowAddEdgeModal(false)}
                className="text-stone-500 hover:text-stone-950 p-1 rounded-lg hover:bg-stone-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateEdge} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-stone-700 mb-2">
                  Relationship Type
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setEdgeType("DEPENDS_ON")}
                    className={`p-3 rounded-xl border text-left text-xs space-y-1 ${
                      edgeType === "DEPENDS_ON"
                        ? "bg-amber-50 border-amber-400 text-amber-900"
                        : "bg-stone-50 border-stone-200 text-stone-600"
                    }`}
                  >
                    <div className="font-bold flex items-center gap-1.5">
                      <span>DEPENDS ON</span>
                    </div>
                    <p className="text-[11px] opacity-80">
                      This obligation cannot proceed until the chosen prerequisite completes.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setEdgeType("LINKED")}
                    className={`p-3 rounded-xl border text-left text-xs space-y-1 ${
                      edgeType === "LINKED"
                        ? "bg-orange-50 border-orange-500 text-orange-950"
                        : "bg-stone-50 border-stone-200 text-stone-600"
                    }`}
                  >
                    <div className="font-bold flex items-center gap-1.5">
                      <LinkIcon className="w-3.5 h-3.5" />
                      <span>LINKED</span>
                    </div>
                    <p className="text-[11px] opacity-80">
                      Connects related/reciprocal obligations without causing blocking.
                    </p>
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-stone-700 mb-1">
                  Select Target Obligation
                </label>
                {loadingAll ? (
                  <div className="text-xs text-stone-600 py-3 text-center">Loading ledger...</div>
                ) : (
                  <select
                    value={targetObligationId}
                    onChange={(e) => setTargetObligationId(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-stone-50 border border-stone-200 text-xs text-stone-900 focus:outline-none focus:border-orange-500"
                    required
                  >
                    <option value="">-- Choose an obligation from the ledger --</option>
                    {allObligations.map((item) => (
                      <option key={item.id} value={item.id}>
                        [{item.owner}] {item.action.slice(0, 50)}... ({item.status})
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-stone-200">
                <button
                  type="button"
                  onClick={() => setShowAddEdgeModal(false)}
                  className="px-3 py-1.5 rounded-lg text-xs text-stone-600 hover:text-stone-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updating || !targetObligationId}
                  className="px-4 py-2 rounded-xl bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold shadow transition-all disabled:opacity-50"
                >
                  Create Edge
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Manual Evidence Attachment Modal */}
      {showEvidenceModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-white border border-stone-200 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <h3 className="text-base font-bold text-stone-950 flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                <span>Complete Obligation</span>
              </h3>
              <button
                onClick={() => setShowEvidenceModal(false)}
                className="text-stone-500 hover:text-stone-950 p-1 rounded-lg hover:bg-stone-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-stone-600">
              Attach optional verification evidence or audit notes before completing this obligation.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-stone-700 mb-1">
                  Evidence Note / Summary
                </label>
                <textarea
                  rows={2}
                  value={evidenceNote}
                  onChange={(e) => setEvidenceNote(e.target.value)}
                  placeholder="e.g. Sent report via email to client, confirmed received."
                  className="w-full px-3 py-2 rounded-xl bg-stone-50 border border-stone-200 text-xs text-stone-900 focus:outline-none focus:border-orange-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-stone-700 mb-1">
                  Artifact Link / URL (Optional)
                </label>
                <input
                  type="url"
                  value={evidenceUrl}
                  onChange={(e) => setEvidenceUrl(e.target.value)}
                  placeholder="https://..."
                  className="w-full px-3 py-2 rounded-xl bg-stone-50 border border-stone-200 text-xs text-stone-900 focus:outline-none focus:border-orange-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-stone-200">
              <button
                onClick={() => setShowEvidenceModal(false)}
                className="px-3 py-1.5 rounded-lg text-xs text-stone-600 hover:text-stone-800"
              >
                Cancel
              </button>
              <button
                onClick={() =>
                  handleStatusChange(
                    "COMPLETED",
                    evidenceNote || evidenceUrl
                      ? { text: evidenceNote, url: evidenceUrl, type: "completion_record" }
                      : undefined
                  )
                }
                disabled={updating}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow transition-all"
              >
                Confirm Completion
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Phase 6: Intervention Review & Authorization Modal */}
      <InterventionReviewModal
        intervention={selectedIntervention}
        isOpen={showInterventionModal}
        onClose={() => {
          setShowInterventionModal(false);
          setSelectedIntervention(null);
        }}
        onUpdated={() => {
          loadData();
        }}
      />

      {/* Phase 11: Reconciliation Review & Adjudication Modal */}
      {reconciliation && (
        <ReconciliationReviewModal
          reconciliation={reconciliation}
          isOpen={showReconciliationModal}
          onClose={() => setShowReconciliationModal(false)}
          onResolved={() => {
            loadData();
          }}
        />
      )}
    </div>
  );
}
