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
} from "@/lib/types/obligation";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ConfidenceBadge } from "@/components/ui/ConfidenceBadge";
import { InterventionCard } from "@/components/interventions/InterventionCard";
import { InterventionReviewModal } from "@/components/interventions/InterventionReviewModal";
import { obligationsApi, interventionsApi } from "@/lib/api/obligations";
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
  const [selectedIntervention, setSelectedIntervention] = useState<Intervention | null>(null);
  const [showInterventionModal, setShowInterventionModal] = useState(false);
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
      const [obData, graphData, evData, riskData, invData] = await Promise.all([
        obligationsApi.getById(obligationId),
        obligationsApi.getGraph(obligationId),
        obligationsApi.getEvidence(obligationId),
        obligationsApi.getRiskAssessment(obligationId).catch(() => null),
        interventionsApi.list({ obligation_id: obligationId }).catch(() => ({ items: [], total: 0 })),
      ]);
      setObligation(obData);
      setGraph(graphData);
      setEvidenceList(evData);
      setRiskAssessment(riskData);
      setInterventions(invData.items || []);

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
        <div className="h-6 w-32 bg-zinc-900 rounded animate-pulse" />
        <div className="h-80 bg-zinc-900/60 rounded-2xl animate-pulse" />
      </div>
    );
  }

  if (!obligation) {
    return (
      <div className="max-w-xl mx-auto text-center py-16 space-y-4">
        <AlertCircle className="w-12 h-12 text-rose-400 mx-auto" />
        <h2 className="text-lg font-bold text-white">Obligation Not Found</h2>
        <p className="text-sm text-zinc-400">The requested obligation record does not exist or was deleted.</p>
        <Link href="/" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800 text-white text-xs">
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
          href="/"
          className="inline-flex items-center gap-2 text-xs font-semibold text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </Link>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsEditing(!isEditing)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900/80 hover:bg-zinc-800 text-zinc-200 text-xs font-medium transition-colors"
          >
            <Edit className="w-3.5 h-3.5" />
            <span>{isEditing ? "Cancel Edit" : "Edit Details"}</span>
          </button>

          <button
            onClick={handleDelete}
            disabled={updating}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-rose-500/30 bg-rose-950/20 hover:bg-rose-950/40 text-rose-300 text-xs font-medium transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Delete</span>
          </button>
        </div>
      </div>

      {/* PHASE 4: Suggested Completion Evidence Review Card */}
      {obligation.status !== "COMPLETED" && pendingSuggestedEvidence.length > 0 && (
        <div className="bg-emerald-950/30 border border-emerald-500/40 rounded-2xl p-6 shadow-xl space-y-4 animate-in fade-in">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-emerald-300 font-bold text-sm">
              <Sparkles className="w-5 h-5 text-emerald-400 animate-pulse" />
              <span>Possible Fulfillment / Completion Evidence Detected</span>
            </div>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              {pendingSuggestedEvidence.length} Candidate(s)
            </span>
          </div>

          <div className="space-y-3">
            {pendingSuggestedEvidence.map((ev) => (
              <div
                key={ev.id}
                className="p-4 rounded-xl bg-zinc-950/80 border border-emerald-500/30 space-y-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-zinc-200">
                      {ev.actor || "External Actor"}
                    </span>
                    <span className="text-zinc-500">•</span>
                    <span className="text-zinc-400 capitalize">{ev.source_type}</span>
                    {ev.source_ref && (
                      <span className="text-zinc-500 font-mono text-[11px]">({ev.source_ref})</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-emerald-400 font-bold text-xs">
                      Match: {Math.round(ev.correlation_confidence * 100)}%
                    </span>
                    <span className="text-zinc-500 text-[11px]">
                      {new Date(ev.observed_at).toLocaleString()}
                    </span>
                  </div>
                </div>

                <p className="text-sm text-zinc-100 font-medium bg-zinc-900/60 p-3 rounded-lg border border-zinc-800/80">
                  &ldquo;{ev.content}&rdquo;
                </p>

                {/* Match Signals Breakdown */}
                {ev.reasoning && Array.isArray(ev.reasoning) && ev.reasoning.length > 0 && (
                  <div className="space-y-1">
                    <span className="text-[11px] font-semibold text-emerald-400/90 uppercase tracking-wider block">
                      Correlation Match Reasoning:
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-xs text-zinc-300">
                      {ev.reasoning.map((r, ri) => (
                        <div key={ri} className="flex items-center gap-1.5">
                          <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                          <span className="text-zinc-300">{r}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Human Confirmation Buttons */}
                <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-zinc-800/80">
                  <button
                    onClick={() => handleRejectEvidence(ev.id)}
                    disabled={updating}
                    className="px-3.5 py-1.5 rounded-lg border border-zinc-800 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 text-xs font-medium transition-colors"
                  >
                    Reject Evidence
                  </button>
                  <button
                    onClick={() => handleConfirmEvidence(ev.id)}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-md shadow-emerald-600/20 active:scale-95 transition-all"
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
        <div className="bg-rose-950/40 border border-rose-500/40 rounded-2xl p-6 shadow-xl space-y-3 animate-in fade-in">
          <div className="flex items-center gap-2.5 text-rose-300 font-bold text-sm">
            <Ban className="w-5 h-5 text-rose-400 animate-pulse" />
            <span>This Obligation is BLOCKED</span>
          </div>

          <p className="text-xs text-rose-200/90 leading-relaxed">
            Progress cannot proceed because one or more prerequisite obligations are unresolved or overdue.
          </p>

          {graph && graph.blockers.length > 0 ? (
            <div className="space-y-2 pt-2">
              <span className="text-[11px] font-semibold text-rose-400 uppercase tracking-wider block">
                Active Blocker(s):
              </span>
              <div className="space-y-2">
                {graph.blockers.map((blocker) => (
                  <div
                    key={blocker.obligation_id}
                    className="p-3.5 rounded-xl bg-zinc-950/80 border border-rose-500/30 flex flex-wrap items-center justify-between gap-3 text-xs"
                  >
                    <div className="space-y-1 max-w-xl">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-zinc-100">{blocker.owner}</span>
                        <span className="text-zinc-500">•</span>
                        <StatusBadge status={blocker.status} />
                      </div>
                      <div className="text-zinc-300 font-medium">{blocker.action}</div>
                      <div className="text-[11px] text-rose-300/80 italic">{blocker.reason}</div>
                    </div>

                    <Link
                      href={`/obligations/${blocker.obligation_id}`}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 border border-rose-500/30 text-xs font-semibold transition-colors"
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
        <div
          className={`rounded-2xl border p-6 shadow-xl space-y-6 ${
            riskAssessment.risk_level === "CRITICAL"
              ? "bg-red-950/20 border-red-500/40 shadow-red-950/20"
              : riskAssessment.risk_level === "HIGH"
              ? "bg-amber-950/20 border-amber-500/40 shadow-amber-950/20"
              : riskAssessment.risk_level === "MEDIUM"
              ? "bg-blue-950/20 border-blue-500/30 shadow-blue-950/10"
              : "bg-zinc-900/60 border-zinc-800"
          }`}
        >
          {/* Header Row */}
          <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-zinc-800/80">
            <div className="flex items-center gap-3">
              <div
                className={`w-10 h-10 rounded-xl flex items-center justify-center border ${
                  riskAssessment.risk_level === "CRITICAL"
                    ? "bg-red-500/20 text-red-400 border-red-500/30"
                    : riskAssessment.risk_level === "HIGH"
                    ? "bg-amber-500/20 text-amber-400 border-amber-500/30"
                    : riskAssessment.risk_level === "MEDIUM"
                    ? "bg-blue-500/20 text-blue-400 border-blue-500/30"
                    : "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                }`}
              >
                <Flame className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-white">
                    Proactive Risk & Deadline Rescue Inspector
                  </h2>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider border ${
                      riskAssessment.risk_level === "CRITICAL"
                        ? "bg-red-500/20 text-red-300 border-red-500/40"
                        : riskAssessment.risk_level === "HIGH"
                        ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                        : riskAssessment.risk_level === "MEDIUM"
                        ? "bg-blue-500/20 text-blue-300 border-blue-500/40"
                        : "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                    }`}
                  >
                    {riskAssessment.risk_level} Risk · {Math.round(riskAssessment.risk_score * 100)}%
                  </span>
                </div>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Multi-signal failure probability analysis & graph cascade evaluation.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="px-3 py-1.5 rounded-lg bg-zinc-950/80 border border-zinc-800 text-xs">
                <span className="text-zinc-500 font-medium">Priority Score: </span>
                <span className="text-zinc-200 font-bold font-mono">
                  {Math.round(riskAssessment.priority_score * 100)} / 100
                </span>
              </div>
              {riskAssessment.dependent_count > 0 && (
                <div className="px-3 py-1.5 rounded-lg bg-amber-950/40 border border-amber-500/30 text-xs font-semibold text-amber-300">
                  ⚡ Blocks {riskAssessment.dependent_count}{" "}
                  {riskAssessment.dependent_count === 1 ? "task" : "tasks"}
                </div>
              )}
            </div>
          </div>

          {/* Recommended Next Action Banner */}
          <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800 space-y-2">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-blue-600/20 text-blue-300 border border-blue-500/30">
                RECOMMENDED ACTION: {riskAssessment.action_type.replace(/_/g, " ")}
              </span>
            </div>
            <p className="text-sm font-semibold text-zinc-100">
              {riskAssessment.recommended_action}
            </p>
          </div>

          {/* Multi-Signal Breakdown Meters */}
          <div className="space-y-3">
            <div className="text-xs uppercase tracking-wider font-semibold text-zinc-400">
              Risk Component Breakdown:
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {/* Deadline Pressure */}
              <div className="p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Deadline Urgency</span>
                  <span className="font-mono font-bold text-zinc-200">
                    +{Math.round(riskAssessment.breakdown.deadline_pressure * 100)}%
                  </span>
                </div>
                <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-yellow-500 to-red-500"
                    style={{
                      width: `${Math.min(100, riskAssessment.breakdown.deadline_pressure * 250)}%`,
                    }}
                  />
                </div>
              </div>

              {/* Dependency Risk */}
              <div className="p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Dependency Health</span>
                  <span className="font-mono font-bold text-zinc-200">
                    +{Math.round(riskAssessment.breakdown.dependency_risk * 100)}%
                  </span>
                </div>
                <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-purple-500 to-rose-500"
                    style={{
                      width: `${Math.min(100, riskAssessment.breakdown.dependency_risk * 250)}%`,
                    }}
                  />
                </div>
              </div>

              {/* Progress Risk / Recency */}
              <div className="p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Progress Evidence</span>
                  <span
                    className={`font-mono font-bold ${
                      riskAssessment.breakdown.progress_risk < 0
                        ? "text-emerald-400"
                        : "text-zinc-200"
                    }`}
                  >
                    {riskAssessment.breakdown.progress_risk > 0 ? "+" : ""}
                    {Math.round(riskAssessment.breakdown.progress_risk * 100)}%
                  </span>
                </div>
                <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
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
              <div className="p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/80 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Ownership Clarity</span>
                  <span className="font-mono font-bold text-zinc-200">
                    +{Math.round(riskAssessment.breakdown.ownership_risk * 100)}%
                  </span>
                </div>
                <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500"
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
              <div className="text-xs uppercase tracking-wider font-semibold text-zinc-400">
                Observed Risk Signals:
              </div>
              <div className="space-y-2">
                {riskAssessment.signals.map((sig, si) => (
                  <div
                    key={si}
                    className="p-3 rounded-xl bg-zinc-950/60 border border-zinc-800 flex flex-wrap items-center justify-between gap-3 text-xs"
                  >
                    <div className="flex items-center gap-2.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${
                          sig.severity === "CRITICAL"
                            ? "bg-red-500/20 text-red-300 border-red-500/40"
                            : sig.severity === "HIGH"
                            ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                            : sig.severity === "MEDIUM"
                            ? "bg-blue-500/20 text-blue-300 border-blue-500/40"
                            : "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                        }`}
                      >
                        {sig.severity}
                      </span>
                      <span className="font-mono text-zinc-400">{sig.signal_type}</span>
                      <span className="text-zinc-200">{sig.explanation}</span>
                    </div>

                    <span className="font-mono text-zinc-500 text-[11px]">
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
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-5">
          <h2 className="text-lg font-bold text-white pb-3 border-b border-zinc-800">
            Edit Obligation
          </h2>
          <form onSubmit={handleSaveEdit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setEditType("OWED_BY_ME")}
                className={`p-3 rounded-xl border text-left text-xs font-medium ${
                  editType === "OWED_BY_ME"
                    ? "bg-blue-600/20 border-blue-500 text-white"
                    : "bg-zinc-950 border-zinc-800 text-zinc-400"
                }`}
              >
                You Owe (Outgoing)
              </button>
              <button
                type="button"
                onClick={() => setEditType("OWED_TO_ME")}
                className={`p-3 rounded-xl border text-left text-xs font-medium ${
                  editType === "OWED_TO_ME"
                    ? "bg-emerald-600/20 border-emerald-500 text-white"
                    : "bg-zinc-950 border-zinc-800 text-zinc-400"
                }`}
              >
                Others Owe You (Incoming)
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">Owner</label>
                <input
                  type="text"
                  value={editOwner}
                  onChange={(e) => setEditOwner(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm text-zinc-100"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">Beneficiary</label>
                <input
                  type="text"
                  value={editBeneficiary}
                  onChange={(e) => setEditBeneficiary(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm text-zinc-100"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-1">Action</label>
              <textarea
                rows={2}
                value={editAction}
                onChange={(e) => setEditAction(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm text-zinc-100"
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">Deadline</label>
                <input
                  type="datetime-local"
                  value={editDeadline}
                  onChange={(e) => setEditDeadline(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm text-zinc-100"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">Conditions</label>
                <input
                  type="text"
                  value={editConditions}
                  onChange={(e) => setEditConditions(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm text-zinc-100"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-1">Next Action</label>
              <input
                type="text"
                value={editNextAction}
                onChange={(e) => setEditNextAction(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm text-zinc-100"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-zinc-800">
              <button
                type="button"
                onClick={() => setIsEditing(false)}
                className="px-4 py-2 rounded-lg text-xs text-zinc-400 hover:text-zinc-200"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={updating}
                className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold"
              >
                Save Changes
              </button>
            </div>
          </form>
        </div>
      ) : (
        /* Detailed View */
        <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-6 sm:p-8 shadow-xl space-y-8">
          {/* Header row */}
          <div className="flex flex-wrap items-start justify-between gap-4 pb-6 border-b border-zinc-800">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-medium text-zinc-400">
                <span className={`w-2.5 h-2.5 rounded-full ${isOwedByMe ? "bg-blue-400" : "bg-emerald-400"}`} />
                <span>
                  {isOwedByMe ? "Outgoing Commitment (You Owe)" : "Incoming Commitment (Others Owe You)"}
                </span>
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-white leading-snug">
                {obligation.action}
              </h1>
            </div>

            <div className="flex items-center gap-3">
              {obligation.is_at_risk && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30 animate-pulse">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  At Risk
                </span>
              )}
              <StatusBadge status={obligation.status} />
            </div>
          </div>

          {/* Reciprocal Parties Visualization */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                Duty Bearer (Owner)
              </span>
              <div className="text-base font-bold text-zinc-100 flex items-center gap-2">
                <User className="w-4 h-4 text-blue-400" />
                <span>{obligation.owner}</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                Obligee (Beneficiary)
              </span>
              <div className="text-base font-bold text-zinc-100 flex items-center gap-2">
                <User className="w-4 h-4 text-emerald-400" />
                <span>{obligation.beneficiary}</span>
              </div>
            </div>
          </div>

          {/* Temporal & Conditions Block */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                Deadline
              </span>
              <div className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                <Clock className="w-4 h-4 text-amber-400" />
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

            <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                Conditions / Triggers
              </span>
              <div className="text-sm text-zinc-300">
                {obligation.conditions ? (
                  <span className="text-amber-300 font-medium">{String(obligation.conditions)}</span>
                ) : (
                  <span className="text-zinc-400 italic">None (Unconditional)</span>
                )}
              </div>
            </div>
          </div>

          {/* Next Action Callout */}
          {obligation.next_action && (
            <div className="p-4 rounded-xl bg-blue-950/30 border border-blue-500/30 space-y-1">
              <span className="text-[11px] font-semibold text-blue-400 uppercase tracking-wider">
                Immediate Next Step
              </span>
              <div className="text-sm text-zinc-200 font-medium">{obligation.next_action}</div>
            </div>
          )}

          {/* Provenance & Confidence */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                Source Reference
              </span>
              <div className="text-xs text-zinc-300">{obligation.source_ref || "Manual Input"}</div>
            </div>

            <div className="p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 space-y-1">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                AI Confidence Breakdown
              </span>
              <div>
                <ConfidenceBadge confidence={obligation.confidence} />
              </div>
            </div>
          </div>

          {/* PHASE 3: RELATIONSHIPS SECTION */}
          <div className="space-y-4 pt-6 border-t border-zinc-800">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <GitFork className="w-4 h-4 text-blue-400" />
                  <span>Obligation Relationships & Dependency Graph</span>
                </h3>
                <p className="text-[11px] text-zinc-400">
                  Connected commitments, prerequisite blockers, and reciprocal dependencies.
                </p>
              </div>

              <button
                onClick={handleOpenAddEdgeModal}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 text-xs font-semibold transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Relationship</span>
              </button>
            </div>

            {/* Prerequisites (Depends On) */}
            <div className="space-y-2">
              <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">
                Prerequisites (This depends on):
              </span>
              {!graph || graph.dependencies.length === 0 ? (
                <div className="p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/60 text-xs text-zinc-500 italic">
                  No prerequisite dependencies. This obligation can proceed independently.
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {graph.dependencies.map((dep) => (
                    <Link
                      key={dep.id}
                      href={`/obligations/${dep.id}`}
                      className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 hover:border-zinc-700 transition-all space-y-1.5 block group"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-zinc-300 group-hover:text-blue-400 transition-colors">
                          {dep.owner}
                        </span>
                        <StatusBadge status={dep.status} />
                      </div>
                      <p className="text-xs text-zinc-200 font-medium line-clamp-2">{dep.action}</p>
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {/* Dependents (Completing This Unblocks) */}
            <div className="space-y-2 pt-2">
              <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">
                Dependents (Completing this unblocks):
              </span>
              {!graph || graph.dependents.length === 0 ? (
                <div className="p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/60 text-xs text-zinc-500 italic">
                  No other obligations depend on this deliverable.
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {graph.dependents.map((dep) => (
                    <Link
                      key={dep.id}
                      href={`/obligations/${dep.id}`}
                      className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 hover:border-zinc-700 transition-all space-y-1.5 block group"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-zinc-300 group-hover:text-emerald-400 transition-colors">
                          {dep.owner}
                        </span>
                        <StatusBadge status={dep.status} />
                      </div>
                      <p className="text-xs text-zinc-200 font-medium line-clamp-2">{dep.action}</p>
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {/* Linked / Reciprocal Obligations */}
            <div className="space-y-2 pt-2">
              <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">
                Linked & Reciprocal Commitments:
              </span>
              {!graph || graph.linked.length === 0 ? (
                <div className="p-3 rounded-xl bg-zinc-950/60 border border-zinc-800/60 text-xs text-zinc-500 italic">
                  No linked reciprocal obligations.
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {graph.linked.map((link) => (
                    <Link
                      key={link.id}
                      href={`/obligations/${link.id}`}
                      className="p-3.5 rounded-xl bg-purple-950/10 border border-purple-500/20 hover:border-purple-500/40 transition-all space-y-1.5 block group"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-purple-300 group-hover:text-purple-200 transition-colors flex items-center gap-1.5">
                          <LinkIcon className="w-3 h-3 text-purple-400" />
                          <span>{link.owner}</span>
                        </span>
                        <StatusBadge status={link.status} />
                      </div>
                      <p className="text-xs text-zinc-200 font-medium line-clamp-2">{link.action}</p>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* PHASE 6: HUMAN-CONTROLLED INTERVENTIONS & FOLLOW-UP HISTORY */}
          <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-6 space-y-4 shadow-md">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-0.5">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-amber-400" />
                  <span>Interventions & Follow-Up History ({interventions.length})</span>
                </h3>
                <p className="text-[11px] text-zinc-400">
                  Human-authorized follow-up drafts, scheduled check-ins, and execution tracking.
                </p>
              </div>

              {obligation.status !== "COMPLETED" && (
                <button
                  onClick={handlePlanIntervention}
                  disabled={planningIntervention}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-zinc-950 text-xs font-bold transition-all shadow-md shadow-amber-500/20 active:scale-95 disabled:opacity-50"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{planningIntervention ? "Planning..." : "⚡ Plan Follow-Up"}</span>
                </button>
              )}
            </div>

            {interventions.length === 0 ? (
              <div className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800/60 text-xs text-zinc-400 italic">
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

          {/* PHASE 4: EVIDENCE & CONTINUITY TIMELINE */}
          <div className="space-y-4 pt-6 border-t border-zinc-800">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  <span>Evidence & Continuity Timeline ({evidenceList.length})</span>
                </h3>
                <p className="text-[11px] text-zinc-400">
                  Chronological record of observed messages, progress updates, and completion evidence.
                </p>
              </div>

              {obligation.status !== "COMPLETED" && (
                <button
                  onClick={() => setShowEvidenceModal(true)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Attach Manual Note</span>
                </button>
              )}
            </div>

            {evidenceList.length === 0 ? (
              <div className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800/60 text-xs text-zinc-400 italic">
                No observations or evidence recorded yet. External messages correlating with this task will appear here.
              </div>
            ) : (
              <div className="space-y-3 relative before:absolute before:left-3 before:top-3 before:bottom-3 before:w-0.5 before:bg-zinc-800">
                {evidenceList.map((ev) => (
                  <div
                    key={ev.id}
                    className="pl-8 relative space-y-1.5 text-xs"
                  >
                    {/* Timeline dot */}
                    <div
                      className={`absolute left-1.5 top-1.5 w-3 h-3 rounded-full border-2 bg-zinc-950 ${
                        ev.correlation_status === "CONFIRMED"
                          ? "border-emerald-400"
                          : ev.correlation_status === "REJECTED"
                          ? "border-rose-400"
                          : "border-blue-400"
                      }`}
                    />

                    <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-2">
                      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded font-bold uppercase text-[10px] ${
                              ev.correlation_status === "CONFIRMED"
                                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                                : ev.correlation_status === "REJECTED"
                                ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                                : "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                            }`}
                          >
                            {ev.correlation_status}
                          </span>
                          <span className="text-zinc-300 font-semibold">{ev.actor || "Actor"}</span>
                          <span className="text-zinc-500">•</span>
                          <span className="text-zinc-400 capitalize">{ev.source_type}</span>
                        </div>
                        <span className="text-zinc-500">
                          {new Date(ev.observed_at).toLocaleString(undefined, {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>

                      <p className="text-zinc-200 font-medium">&ldquo;{ev.content}&rdquo;</p>

                      {ev.reasoning && Array.isArray(ev.reasoning) && ev.reasoning.length > 0 && (
                        <div className="text-[11px] text-zinc-400 space-y-0.5 pt-1 border-t border-zinc-900">
                          {ev.reasoning.map((r, idx) => (
                            <div key={idx} className="flex items-center gap-1.5">
                              <span className="text-zinc-600">•</span>
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

          {/* Controlled Status Transition Action Bar */}
          <div className="pt-6 border-t border-zinc-800 space-y-3">
            <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">
              Controlled State Machine Actions
            </span>

            <div className="flex flex-wrap items-center gap-2.5">
              {/* If CONFIRMED */}
              {obligation.status === "CONFIRMED" && (
                <>
                  <button
                    onClick={() => handleStatusChange("IN_PROGRESS")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold shadow-md shadow-amber-600/20 active:scale-95 transition-all"
                  >
                    <PlayCircle className="w-4 h-4" />
                    <span>Start Work (In Progress)</span>
                  </button>
                  <button
                    onClick={() => setShowEvidenceModal(true)}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-600/20 active:scale-95 transition-all"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Complete & Attach Evidence</span>
                  </button>
                  <button
                    onClick={() => handleStatusChange("BLOCKED")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium transition-colors"
                  >
                    <span>Mark Blocked</span>
                  </button>
                  <button
                    onClick={() => handleStatusChange("CANCELLED")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 text-xs font-medium transition-colors"
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
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-600/20 active:scale-95 transition-all"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Complete & Attach Evidence</span>
                  </button>
                  <button
                    onClick={() => handleStatusChange("BLOCKED")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium transition-colors"
                  >
                    <span>Mark Blocked</span>
                  </button>
                  <button
                    onClick={() => handleStatusChange("CANCELLED")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 text-xs font-medium transition-colors"
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
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold transition-all"
                  >
                    <PlayCircle className="w-4 h-4" />
                    <span>Override & Resume (In Progress)</span>
                  </button>
                  <button
                    onClick={() => handleStatusChange("CONFIRMED")}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium transition-colors"
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
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold transition-all"
                  >
                    <PlayCircle className="w-4 h-4" />
                    <span>Work on Overdue Item</span>
                  </button>
                  <button
                    onClick={() => setShowEvidenceModal(true)}
                    disabled={updating}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-all"
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
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium transition-colors"
                >
                  <span>Reopen Obligation (In Progress)</span>
                </button>
              )}

              {/* If CANCELLED */}
              {obligation.status === "CANCELLED" && (
                <button
                  onClick={() => handleStatusChange("CONFIRMED")}
                  disabled={updating}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium transition-colors"
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
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <GitFork className="w-5 h-5 text-blue-400" />
                <span>Connect Obligation Relationship</span>
              </h3>
              <button
                onClick={() => setShowAddEdgeModal(false)}
                className="text-zinc-400 hover:text-white p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateEdge} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-2">
                  Relationship Type
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setEdgeType("DEPENDS_ON")}
                    className={`p-3 rounded-xl border text-left text-xs space-y-1 ${
                      edgeType === "DEPENDS_ON"
                        ? "bg-amber-600/20 border-amber-500 text-amber-200"
                        : "bg-zinc-950 border-zinc-800 text-zinc-400"
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
                        ? "bg-purple-600/20 border-purple-500 text-purple-200"
                        : "bg-zinc-950 border-zinc-800 text-zinc-400"
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
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Select Target Obligation
                </label>
                {loadingAll ? (
                  <div className="text-xs text-zinc-400 py-3 text-center">Loading ledger...</div>
                ) : (
                  <select
                    value={targetObligationId}
                    onChange={(e) => setTargetObligationId(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100"
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

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setShowAddEdgeModal(false)}
                  className="px-3 py-1.5 rounded-lg text-xs text-zinc-400 hover:text-zinc-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updating || !targetObligationId}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-all disabled:opacity-50"
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
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <span>Complete Obligation</span>
              </h3>
              <button
                onClick={() => setShowEvidenceModal(false)}
                className="text-zinc-400 hover:text-white p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-zinc-400">
              Attach optional verification evidence or audit notes before completing this obligation.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Evidence Note / Summary
                </label>
                <textarea
                  rows={2}
                  value={evidenceNote}
                  onChange={(e) => setEvidenceNote(e.target.value)}
                  placeholder="e.g. Sent report via email to client, confirmed received."
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Artifact Link / URL (Optional)
                </label>
                <input
                  type="url"
                  value={evidenceUrl}
                  onChange={(e) => setEvidenceUrl(e.target.value)}
                  placeholder="https://..."
                  className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-100"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-800">
              <button
                onClick={() => setShowEvidenceModal(false)}
                className="px-3 py-1.5 rounded-lg text-xs text-zinc-400 hover:text-zinc-200"
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
                className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-all"
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
    </div>
  );
}
